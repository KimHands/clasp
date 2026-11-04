import os

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from conftest import add_scanned, read, write
from models.schema import ActionBatch, ActionLog, Classification
from services import action_service
from services.action_service import apply_organize, get_folder_history, undo_organize


def _classify(db, file, scan_id, category):
    db.add(Classification(
        file_id=file.id, scan_id=scan_id, category=category,
        tag=None, tier_used=1, confidence_score=0.7, is_manual=False,
    ))
    db.commit()


def _state(db, folder):
    return get_folder_history(db, folder)[0]["undo_state"]


def _organize_one(home, db, relative="b.txt"):
    src = write(f"{home}/r/{relative}", "원본")
    file = add_scanned(db, src)
    result = apply_organize(db, "scan_t", "rename", f"{home}/r")
    return src, file, result["action_log_id"]


def test_undo_restores_file_and_path(home, db):
    src, file, log_id = _organize_one(home, db)
    out = undo_organize(db, log_id)
    assert out["restored"] == 1
    assert read(src) == "원본"
    db.refresh(file)
    assert file.path == src
    assert _state(db, f"{home}/r") == "undone"


def test_undo_does_not_clobber_new_file(home, db):
    src, _, log_id = _organize_one(home, db)
    write(src, "새로 만든 파일")
    out = undo_organize(db, log_id)
    assert read(src) == "새로 만든 파일"
    assert read(f"{home}/r/문서/b.txt") == "원본"
    assert out["unrestorable"][0]["reason"] == "source_occupied"


def test_old_batch_undo_does_not_move_other_file(home, db):
    x = add_scanned(db, write(f"{home}/r/a.txt", "X"), scan_id="s1")
    batch_a = apply_organize(db, "s1", "rename", f"{home}/r")["action_log_id"]
    _classify(db, x, "s2", "기타폴더")
    apply_organize(db, "s2", "rename", f"{home}/r")
    add_scanned(db, write(f"{home}/r/sub/a.txt", "Y"), scan_id="s3")
    apply_organize(db, "s3", "rename", f"{home}/r")

    out = undo_organize(db, batch_a)

    assert out["unrestorable"][0]["reason"] == "identity_mismatch"
    assert read(f"{home}/r/문서/a.txt") == "Y"
    assert read(f"{home}/r/기타폴더/a.txt") == "X"
    assert not os.path.exists(f"{home}/r/a.txt")


def test_undo_refuses_source_folder_outside_root(home, db):
    _, _, log_id = _organize_one(home, db, "sub/a.txt")
    os.rmdir(f"{home}/r/sub")
    os.makedirs(f"{home}/outside")
    os.symlink(f"{home}/outside", f"{home}/r/sub")
    out = undo_organize(db, log_id)
    assert out["unrestorable"][0]["reason"] == "source_outside_root"
    assert read(f"{home}/r/문서/a.txt") == "원본"
    assert os.listdir(f"{home}/outside") == []


def test_undo_after_in_place_edit_restores(home, db):
    src, _, log_id = _organize_one(home, db)
    write(f"{home}/r/문서/b.txt", "제자리에서 수정한 내용")
    assert undo_organize(db, log_id)["restored"] == 1
    assert read(src) == "제자리에서 수정한 내용"


def test_partial_undo_state_and_retry(home, db):
    first = write(f"{home}/r/a.txt", "A")
    add_scanned(db, first)
    add_scanned(db, write(f"{home}/r/b.txt", "B"))
    log_id = apply_organize(db, "scan_t", "rename", f"{home}/r")["action_log_id"]
    write(first, "자리를 막은 파일")

    out = undo_organize(db, log_id)
    assert (out["restored"], out["failed"]) == (1, 1)
    assert _state(db, f"{home}/r") == "partial"
    assert db.query(ActionBatch).one().is_undone is False

    os.remove(first)
    out = undo_organize(db, log_id)
    assert out["restored"] == 1
    assert read(first) == "A"
    assert _state(db, f"{home}/r") == "undone"
    assert db.query(ActionBatch).one().is_undone is True


def test_second_undo_after_complete_raises_conflict(home, db):
    _, _, log_id = _organize_one(home, db)
    undo_organize(db, log_id)
    with pytest.raises(HTTPException) as raised:
        undo_organize(db, log_id)
    assert raised.value.status_code == 409


def test_missing_destination_is_reported(home, db):
    add_scanned(db, write(f"{home}/r/a.txt", "A"))
    add_scanned(db, write(f"{home}/r/b.txt", "B"))
    log_id = apply_organize(db, "scan_t", "rename", f"{home}/r")["action_log_id"]
    os.remove(f"{home}/r/문서/a.txt")
    out = undo_organize(db, log_id)
    assert out["unrestorable"] == [{"filename": "a.txt", "reason": "destination_file_not_found"}]
    assert _state(db, f"{home}/r") == "partial"


def test_stale_row_on_source_is_occupied(home, db):
    src, _, log_id = _organize_one(home, db)
    add_scanned(db, src, scan_id="scan_new")
    out = undo_organize(db, log_id)
    assert out["unrestorable"][0]["reason"] == "source_occupied"
    assert read(f"{home}/r/문서/b.txt") == "원본"


def test_undo_marks_undo_pending_before_move(home, db, monkeypatch):
    _, _, log_id = _organize_one(home, db)
    seen = []
    real_move = action_service.move_no_clobber

    def observe(src, dst):
        seen.append(db.query(ActionLog).one().action_type)
        real_move(src, dst)

    monkeypatch.setattr(action_service, "move_no_clobber", observe)
    undo_organize(db, log_id)
    assert seen == ["undo_pending"]
    assert db.query(ActionLog).one().action_type == "move"


def test_undo_final_commit_failure_keeps_undo_pending(home, db, monkeypatch):
    src, _, log_id = _organize_one(home, db)

    def commit_failed(*args):
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(action_service, "_finalize_undo", commit_failed)
    out = undo_organize(db, log_id)
    assert out["unrestorable"][0]["reason"] == "move_failed"
    assert read(src) == "원본"
    assert db.query(ActionLog).one().action_type == "undo_pending"


def test_move_error_reverts_log_to_move(home, db, monkeypatch):
    _, _, log_id = _organize_one(home, db)

    def denied(src, dst):
        raise PermissionError("denied")

    monkeypatch.setattr(action_service, "move_no_clobber", denied)
    out = undo_organize(db, log_id)
    assert out["unrestorable"][0]["reason"] == "move_failed"
    assert db.query(ActionLog).one().action_type == "move"


def test_history_state_is_none_before_undo(home, db):
    _organize_one(home, db)
    assert _state(db, f"{home}/r") == "none"


def test_history_finds_raw_and_normalized_path(home, db):
    _organize_one(home, db)
    os.symlink(f"{home}/r", f"{home}/link")
    db.add(ActionBatch(action_log_id="log_old", folder_path=f"{home}/link", scan_id="s"))
    db.commit()
    history = get_folder_history(db, f"{home}/link")
    assert len(history) == 2
    assert {h["undo_state"] for h in history} == {"none"}


def test_history_time_is_marked_as_utc(home, db):
    _organize_one(home, db)
    assert get_folder_history(db, f"{home}/r")[0]["executed_at"].endswith("Z")
