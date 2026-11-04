import errno
import hashlib
import os

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from conftest import add_scanned, read, write
from models.schema import ActionLog, File
from services import action_service
from services.action_service import apply_organize
from services.safe_move import inode_of


def _hashes(root):
    return sorted(
        hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest()
        for d, _, files in os.walk(root) for f in files
    )


def _log_types(db):
    return [log.action_type for log in db.query(ActionLog).all()]


def test_overwrite_rejected(client, home):
    response = client.post("/apply", json={
        "scan_id": "s", "conflict_resolution": "overwrite", "folder_path": home,
    })
    assert response.status_code == 400


def test_moves_file_and_updates_path(home, db):
    file = add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["moved"] == 1
    assert read(f"{home}/r/문서/a.txt") == "본문"
    db.refresh(file)
    assert file.path == f"{home}/r/문서/a.txt"
    assert _log_types(db) == ["move"]


def test_scanned_conflict_renames_and_keeps_both(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "새 파일"))
    add_scanned(db, write(f"{home}/r/문서/a.txt", "기존 파일"), scan_id="scan_old")
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert read(f"{home}/r/문서/a.txt") == "기존 파일"
    assert read(f"{home}/r/문서/a_1.txt") == "새 파일"
    assert result["failed"] == 0


def test_conflict_skip_leaves_files(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "새 파일"))
    write(f"{home}/r/문서/a.txt", "기존 파일")
    result = apply_organize(db, "scan_t", "skip", f"{home}/r")
    assert result["skipped"] == 1
    assert read(f"{home}/r/a.txt") == "새 파일"
    assert read(f"{home}/r/문서/a.txt") == "기존 파일"
    assert _log_types(db) == ["skip"]


def test_stale_row_path_gets_number(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "새 파일"))
    add_scanned(db, f"{home}/r/문서/a.txt", scan_id="scan_old")
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["moved"] == 1
    assert read(f"{home}/r/문서/a_1.txt") == "새 파일"


def test_low_confidence_excluded(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "본문"), confidence=0.30)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result == {**result, "moved": 0, "skipped": 1}
    assert read(f"{home}/r/a.txt") == "본문"


def test_symlink_row_is_skipped(home, db):
    target = write(f"{home}/r/target.txt", "대상")
    os.symlink(target, f"{home}/r/a.txt")
    add_scanned(db, f"{home}/r/a.txt")
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["skipped"] == 1
    assert os.path.islink(f"{home}/r/a.txt")


def test_replaced_after_scan_is_skipped(home, db):
    path = write(f"{home}/r/a.txt", "스캔한 파일")
    add_scanned(db, path)
    os.remove(path)
    write(path, "스캔 후 새로 생긴 다른 파일")
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["skipped"] == 1
    assert read(path) == "스캔 후 새로 생긴 다른 파일"


def test_missing_scan_metadata_skips_comparison(home, db):
    file = add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    file.size = None
    file.modified_at = None
    db.commit()
    assert apply_organize(db, "scan_t", "rename", f"{home}/r")["moved"] == 1


def test_two_files_same_name_both_survive(home, db):
    add_scanned(db, write(f"{home}/r/x/a.txt", "X"))
    add_scanned(db, write(f"{home}/r/y/a.txt", "Y"))
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["moved"] == 2
    assert {read(f"{home}/r/문서/a.txt"), read(f"{home}/r/문서/a_1.txt")} == {"X", "Y"}


def test_category_path_is_regular_file(home, db):
    write(f"{home}/r/문서", "폴더 자리에 있는 일반 파일")
    add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["failed"] == 1
    assert read(f"{home}/r/a.txt") == "본문"
    assert _log_types(db) == ["failed"]


def test_symlink_folder_escape_fails_without_writing(home, db):
    os.makedirs(f"{home}/outside")
    os.makedirs(f"{home}/r")
    os.symlink(f"{home}/outside", f"{home}/r/문서")
    add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["failed"] == 1
    assert os.listdir(f"{home}/outside") == []
    assert read(f"{home}/r/a.txt") == "본문"


def test_hardlink_unsupported_reports_failure(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "본문"))

    def unsupported(*args, **kwargs):
        raise OSError(errno.ENOTSUP, "hard links unsupported")

    monkeypatch.setattr(os, "link", unsupported)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["failed"] == 1
    assert read(f"{home}/r/a.txt") == "본문"
    assert _log_types(db) == ["failed"]


def test_missing_file_reports_failure(home, db):
    os.makedirs(f"{home}/r")
    add_scanned(db, f"{home}/r/없는파일.txt")
    assert apply_organize(db, "scan_t", "rename", f"{home}/r")["failed"] == 1


def test_one_failure_does_not_stop_rest(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "A"))
    add_scanned(db, write(f"{home}/r/b.txt", "B"))
    real_move = action_service.move_no_clobber

    def fail_for_a(src, dst):
        if src.endswith("a.txt"):
            raise PermissionError(errno.EACCES, "denied")
        real_move(src, dst)

    monkeypatch.setattr(action_service, "move_no_clobber", fail_for_a)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert (result["moved"], result["failed"]) == (1, 1)
    assert read(f"{home}/r/a.txt") == "A"
    assert read(f"{home}/r/문서/b.txt") == "B"


def test_destination_appearing_mid_move_is_failed_not_retried(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    calls = []

    def appeared(src, dst):
        calls.append(dst)
        raise FileExistsError(errno.EEXIST, "exists")

    monkeypatch.setattr(action_service, "move_no_clobber", appeared)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["failed"] == 1
    assert len(calls) == 1
    assert read(f"{home}/r/a.txt") == "본문"


def test_pending_and_identity_logged_before_move(home, db, monkeypatch):
    path = write(f"{home}/r/a.txt", "본문")
    add_scanned(db, path)
    expected_inode = inode_of(path)
    seen = {}
    real_move = action_service.move_no_clobber
    other = sessionmaker(bind=db.get_bind())()

    def observe(src, dst):
        log = other.query(ActionLog).one()
        seen["type"] = log.action_type
        seen["inode"] = log.identity.inode
        real_move(src, dst)

    monkeypatch.setattr(action_service, "move_no_clobber", observe)
    apply_organize(db, "scan_t", "rename", f"{home}/r")
    other.close()
    assert seen == {"type": "pending", "inode": expected_inode}


def test_finalize_failure_keeps_pending(home, db, monkeypatch):
    file = add_scanned(db, write(f"{home}/r/a.txt", "본문"))

    def commit_failed(*args):
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(action_service, "_finalize_move", commit_failed)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["failed"] == 1
    assert _log_types(db) == ["pending"]
    assert read(f"{home}/r/문서/a.txt") == "본문"
    assert db.query(File).filter(File.id == file.id).one().path == f"{home}/r/a.txt"


def test_cannot_lose_content(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "새 파일"))
    add_scanned(db, write(f"{home}/r/문서/a.txt", "기존 파일"), scan_id="scan_old")
    add_scanned(db, write(f"{home}/r/sub/a.txt", "하위 파일"))
    before = _hashes(f"{home}/r")
    apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert _hashes(f"{home}/r") == before
