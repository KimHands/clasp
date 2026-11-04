import os
import sys
import unicodedata

import pytest
from sqlalchemy.exc import SQLAlchemyError

from conftest import add_scanned, read, write
from models.schema import ActionBatch, ActionLog, File
from services.action_service import apply_organize, get_folder_history, undo_organize
from services.move_recovery import reconcile_pending
from services.scan_service import _collect_files
from utils.paths import validate_folder_path

macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="APFS 정규화 동작")


def _nfd(path):
    return unicodedata.normalize("NFD", path)


def _fail_commit_when(db, monkeypatch, predicate):
    real_commit = db.commit

    def commit():
        if any(predicate(obj) for obj in list(db.dirty) + list(db.new)):
            raise SQLAlchemyError("commit failed")
        real_commit()

    monkeypatch.setattr(db, "commit", commit)


def _is_log(action_type):
    return lambda obj: isinstance(obj, ActionLog) and obj.action_type == action_type


def _organize_two(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "A"))
    add_scanned(db, write(f"{home}/r/b.txt", "B"))
    return apply_organize(db, "scan_t", "rename", f"{home}/r")["action_log_id"]


# ── 한글 경로 정규화 ──

@macos_only
def test_file_already_in_nfd_folder_is_not_moved(home, db):
    path = write(_nfd(f"{home}/r/문서/a.txt"), "본문")
    add_scanned(db, path)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert result["moved"] == 0
    assert sorted(os.listdir(_nfd(f"{home}/r/문서"))) == ["a.txt"]


@macos_only
def test_nfd_request_folder_does_not_move_placed_file(home, db):
    add_scanned(db, write(f"{home}/r/문서/a.txt", "본문"))
    result = apply_organize(db, "scan_t", "rename", _nfd(f"{home}/r"))
    assert result["moved"] == 0
    assert os.listdir(f"{home}/r/문서") == ["a.txt"]


@macos_only
def test_collect_returns_one_form_on_macos(home):
    write(_nfd(f"{home}/r/문서/한글.txt"), "본문")
    collected = _collect_files(f"{home}/r")
    assert collected == [unicodedata.normalize("NFC", f"{home}/r/문서/한글.txt")]


@macos_only
def test_validate_returns_one_form_on_macos(home):
    assert validate_folder_path(_nfd(f"{home}/문서")) == unicodedata.normalize("NFC", f"{home}/문서")


@macos_only
def test_history_found_with_other_normalization(home, db):
    add_scanned(db, write(f"{home}/폴더/a.txt", "본문"))
    apply_organize(db, "scan_t", "rename", f"{home}/폴더")
    assert len(get_folder_history(db, _nfd(f"{home}/폴더"))) == 1


# ── 이력 ──

def test_undo_pending_keeps_state_partial(home, db, monkeypatch):
    log_id = _organize_two(home, db)
    first, second = db.query(ActionLog).order_by(ActionLog.id).all()
    first.is_undone = True
    second.action_type = "undo_pending"
    db.commit()
    assert get_folder_history(db, f"{home}/r")[0]["undo_state"] == "partial"


def test_history_counts_come_from_logs(home, db):
    _organize_two(home, db)
    batch = db.query(ActionBatch).one()
    batch.moved_count = 0
    db.commit()
    assert get_folder_history(db, f"{home}/r")[0]["moved_count"] == 2


def test_history_is_undone_comes_from_logs(home, db):
    log_id = _organize_two(home, db)
    for log in db.query(ActionLog).all():
        log.is_undone = True
    db.commit()
    assert get_folder_history(db, f"{home}/r")[0]["is_undone"] is True


# ── 커밋 실패가 500이 되지 않음 ──

def test_undo_pending_commit_failure_reports_each_file(home, db, monkeypatch):
    log_id = _organize_two(home, db)
    _fail_commit_when(db, monkeypatch, _is_log("undo_pending"))
    out = undo_organize(db, log_id)
    assert [u["reason"] for u in out["unrestorable"]] == ["move_failed", "move_failed"]
    assert read(f"{home}/r/문서/a.txt") == "A"


def test_undo_revert_commit_failure_leaves_undo_pending(home, db, monkeypatch):
    log_id = _organize_two(home, db)
    os.chmod(f"{home}/r", 0o555)
    try:
        real_commit = db.commit
        calls = []

        def commit():
            logs = [o for o in db.dirty if isinstance(o, ActionLog) and o.action_type == "move"]
            if logs and not logs[0].is_undone:
                calls.append(1)
                raise SQLAlchemyError("commit failed")
            real_commit()

        monkeypatch.setattr(db, "commit", commit)
        out = undo_organize(db, log_id)
    finally:
        os.chmod(f"{home}/r", 0o755)
    assert calls
    assert out["failed"] == 2
    monkeypatch.undo()
    assert reconcile_pending(db) == 0
    assert read(f"{home}/r/문서/a.txt") == "A"
    assert {log.action_type for log in db.query(ActionLog).all()} == {"move"}


def test_failed_log_commit_failure_does_not_stop_rest(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "A"))
    os.makedirs(f"{home}/r/x")
    add_scanned(db, write(f"{home}/r/b.txt", "B"), category="문서")
    write(f"{home}/r/기타", "폴더 자리의 일반 파일")
    file = db.query(File).filter(File.filename == "a.txt").one()
    file.classifications[0].category = "기타"
    db.commit()
    _fail_commit_when(db, monkeypatch, _is_log("failed"))
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert (result["moved"], result["failed"]) == (1, 1)
    assert read(f"{home}/r/a.txt") == "A"


def test_skip_log_commit_failure_does_not_stop_rest(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "A"))
    write(f"{home}/r/문서/a.txt", "기존")
    add_scanned(db, write(f"{home}/r/b.txt", "B"))
    _fail_commit_when(db, monkeypatch, _is_log("skip"))
    result = apply_organize(db, "scan_t", "skip", f"{home}/r")
    assert (result["moved"], result["skipped"]) == (1, 1)


def test_batch_summary_commit_failure_returns_result(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "A"))
    _fail_commit_when(db, monkeypatch, lambda o: isinstance(o, ActionBatch) and o.moved_count)
    assert apply_organize(db, "scan_t", "rename", f"{home}/r")["moved"] == 1


# ── 조정 시 권한 오류 ──

def test_permission_error_stays_unresolved(home, db, monkeypatch):
    dst = write(f"{home}/문서/a.txt", "본문")
    file = add_scanned(db, f"{home}/a.txt")
    from models.schema import ActionLogIdentity
    db.add(ActionBatch(action_log_id="log_t", folder_path=home, scan_id="s"))
    log = ActionLog(
        action_log_id="log_t", action_type="pending", source_path=file.path,
        destination_path=dst, is_undone=False,
        identity=ActionLogIdentity(inode=str(os.lstat(dst).st_ino)),
    )
    db.add(log)
    db.commit()
    real_lstat = os.lstat

    def denied(path, **kwargs):
        if path == dst:
            raise PermissionError("denied")
        return real_lstat(path, **kwargs)

    monkeypatch.setattr(os, "lstat", denied)
    assert reconcile_pending(db) == 1
    assert log.action_type == "pending"
    monkeypatch.undo()
    assert reconcile_pending(db) == 0
    assert log.action_type == "move"
