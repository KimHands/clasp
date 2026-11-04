import asyncio
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from conftest import add_scanned, read, write
from models.schema import ActionBatch, ActionLog, ActionLogIdentity, File
from services import action_service, move_recovery, scan_service
from services.action_service import apply_organize, undo_organize
from services.move_recovery import reconcile_pending, repoint_file
from services.safe_move import inode_of


def _log(db, src, dst, inode, action_type="pending"):
    if not db.query(ActionBatch).filter_by(action_log_id="log_t").first():
        db.add(ActionBatch(action_log_id="log_t", folder_path="/", scan_id="s"))
    log = ActionLog(
        action_log_id="log_t", action_type=action_type,
        source_path=src, destination_path=dst, is_undone=False,
        identity=ActionLogIdentity(inode=inode) if inode else None,
    )
    db.add(log)
    db.commit()
    return log


def _paths(home):
    return f"{home}/a.txt", f"{home}/문서/a.txt"


def test_pending_dest_match_source_gone_becomes_move(home, db):
    src, dst = _paths(home)
    file = add_scanned(db, src)
    log = _log(db, src, write(dst, "본문"), inode_of(dst))
    assert reconcile_pending(db) == 0
    assert log.action_type == "move"
    assert db.query(File).filter_by(id=file.id).one().path == dst
    assert db.query(ActionBatch).one().moved_count == 1


def test_pending_hardlink_midway_removes_dest_only(home, db):
    src, dst = _paths(home)
    write(src, "본문")
    os.makedirs(os.path.dirname(dst))
    os.link(src, dst)
    log = _log(db, src, dst, inode_of(src))
    reconcile_pending(db)
    assert log.action_type == "failed"
    assert read(src) == "본문"
    assert not os.path.lexists(dst)
    assert db.query(ActionBatch).one().failed_count == 1


def test_pending_source_replaced_keeps_both(home, db):
    src, dst = _paths(home)
    write(dst, "옮긴 파일")
    log = _log(db, src, dst, inode_of(dst))
    write(src, "새로 생긴 파일")
    reconcile_pending(db)
    assert log.action_type == "move"
    assert read(src) == "새로 생긴 파일"
    assert read(dst) == "옮긴 파일"


def test_pending_dest_missing_becomes_failed(home, db):
    src, dst = _paths(home)
    write(src, "본문")
    log = _log(db, src, dst, inode_of(src))
    reconcile_pending(db)
    assert log.action_type == "failed"
    assert read(src) == "본문"


def test_pending_dest_other_file_is_untouched(home, db):
    src, dst = _paths(home)
    write(src, "원본")
    log = _log(db, src, write(dst, "다른 파일"), inode_of(src))
    reconcile_pending(db)
    assert log.action_type == "failed"
    assert read(src) == "원본"
    assert read(dst) == "다른 파일"


def test_pending_dest_replaced_source_gone_is_unverified(home, db):
    src, dst = _paths(home)
    log = _log(db, src, write(dst, "교체된 파일"), "1")
    reconcile_pending(db)
    assert log.action_type == "unverified"
    assert read(dst) == "교체된 파일"
    assert db.query(ActionBatch).one().failed_count == 1
    with pytest.raises(HTTPException):
        undo_organize(db, "log_t")


def test_pending_both_gone_becomes_failed(home, db):
    src, dst = _paths(home)
    log = _log(db, src, dst, "1")
    reconcile_pending(db)
    assert log.action_type == "failed"


def test_undo_pending_source_match_dest_gone_completes(home, db):
    src, dst = _paths(home)
    file = add_scanned(db, dst)
    log = _log(db, write(src, "본문"), dst, inode_of(src), "undo_pending")
    reconcile_pending(db)
    assert (log.action_type, log.is_undone) == ("move", True)
    assert db.query(File).filter_by(id=file.id).one().path == src


def test_undo_pending_midway_removes_source_link(home, db):
    src, dst = _paths(home)
    write(dst, "본문")
    os.link(dst, src)
    log = _log(db, src, dst, inode_of(dst), "undo_pending")
    reconcile_pending(db)
    assert (log.action_type, log.is_undone) == ("move", False)
    assert not os.path.lexists(src)
    assert read(dst) == "본문"


def test_undo_pending_dest_replaced_keeps_both(home, db):
    src, dst = _paths(home)
    write(src, "돌아온 파일")
    log = _log(db, src, write(dst, "새 파일"), inode_of(src), "undo_pending")
    reconcile_pending(db)
    assert (log.action_type, log.is_undone) == ("move", True)
    assert read(src) == "돌아온 파일"
    assert read(dst) == "새 파일"


def test_undo_pending_not_moved_reverts(home, db):
    src, dst = _paths(home)
    log = _log(db, src, write(dst, "본문"), inode_of(dst), "undo_pending")
    reconcile_pending(db)
    assert (log.action_type, log.is_undone) == ("move", False)
    assert read(dst) == "본문"


def test_undo_pending_without_identity_uses_existence(home, db):
    src, dst = _paths(home)
    log = _log(db, write(src, "본문"), dst, None, "undo_pending")
    reconcile_pending(db)
    assert (log.action_type, log.is_undone) == ("move", True)
    assert read(src) == "본문"


def test_repoint_never_deletes_other_row(home, db):
    src, dst = _paths(home)
    old = add_scanned(db, src)
    other = add_scanned(db, dst, scan_id="scan_new")
    repoint_file(db, src, dst)
    db.commit()
    assert db.query(File).filter_by(id=old.id).one().path == src
    assert db.query(File).filter_by(id=other.id).one().path == dst


def test_one_bad_log_does_not_stop_others(home, db, monkeypatch):
    src, dst = _paths(home)
    bad = _log(db, f"{home}/bad", f"{home}/bad_dest", "1")
    good = _log(db, src, write(dst, "본문"), inode_of(dst))
    real = move_recovery._reconcile_one

    def fail_for_bad(session, log):
        if log.id == bad.id:
            raise OSError("broken")
        real(session, log)

    monkeypatch.setattr(move_recovery, "_reconcile_one", fail_for_bad)
    assert reconcile_pending(db) == 1
    assert bad.action_type == "pending"
    assert good.action_type == "move"


def _block_reconcile(monkeypatch):
    def broken(session, log):
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(move_recovery, "_reconcile_one", broken)


def test_unresolved_blocks_apply(home, db, monkeypatch):
    add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    _log(db, f"{home}/x", f"{home}/y", "1")
    _block_reconcile(monkeypatch)
    with pytest.raises(HTTPException) as raised:
        apply_organize(db, "scan_t", "rename", f"{home}/r")
    assert raised.value.status_code == 409
    assert read(f"{home}/r/a.txt") == "본문"


def test_unresolved_blocks_undo(home, db, monkeypatch):
    src = write(f"{home}/r/a.txt", "본문")
    add_scanned(db, src)
    log_id = apply_organize(db, "scan_t", "rename", f"{home}/r")["action_log_id"]
    _log(db, f"{home}/x", f"{home}/y", "1")
    _block_reconcile(monkeypatch)
    with pytest.raises(HTTPException) as raised:
        undo_organize(db, log_id)
    assert raised.value.status_code == 409
    assert read(f"{home}/r/문서/a.txt") == "본문"


def _run_scan(db, monkeypatch, folder):
    monkeypatch.setattr(scan_service, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(scan_service.tier2_embedding, "load_custom_categories", lambda categories: None)

    async def collect():
        return [event async for event in scan_service.run_scan("scan_new", folder)]

    return asyncio.run(collect())


def test_unresolved_blocks_scan(home, db, monkeypatch):
    write(f"{home}/r/a.txt", "본문")
    _log(db, f"{home}/x", f"{home}/y", "1")
    _block_reconcile(monkeypatch)
    events = _run_scan(db, monkeypatch, f"{home}/r")
    assert [e["stage"] for e in events] == [-1]
    assert db.query(File).count() == 0


def test_scan_reconciles_first(home, db, monkeypatch):
    os.makedirs(f"{home}/r")
    src, dst = f"{home}/r/a.txt", f"{home}/다른곳/a.txt"
    log = _log(db, src, write(dst, "본문"), inode_of(dst))
    _run_scan(db, monkeypatch, f"{home}/r")
    assert log.action_type == "move"


def test_apply_after_finalize_failure_keeps_records_straight(home, db, monkeypatch):
    file = add_scanned(db, write(f"{home}/r/a.txt", "본문"))
    add_scanned(db, write(f"{home}/r/b.txt", "다른 파일"), confidence=0.1)

    def commit_failed(*args):
        raise SQLAlchemyError("commit failed")

    with monkeypatch.context() as patch:
        patch.setattr(action_service, "_finalize_move", commit_failed)
        apply_organize(db, "scan_t", "rename", f"{home}/r")
    write(f"{home}/r/a.txt", "그 사이 새로 만든 파일")

    apply_organize(db, "scan_t", "rename", f"{home}/r")

    assert db.query(File).filter_by(id=file.id).one().path == f"{home}/r/문서/a.txt"
    assert read(f"{home}/r/문서/a.txt") == "본문"
    assert read(f"{home}/r/a.txt") == "그 사이 새로 만든 파일"


def test_undo_after_commit_failure_completes_without_retry(home, db, monkeypatch):
    src = write(f"{home}/r/a.txt", "본문")
    file = add_scanned(db, src)
    add_scanned(db, write(f"{home}/r/b.txt", "B"))
    log_id = apply_organize(db, "scan_t", "rename", f"{home}/r")["action_log_id"]

    def commit_failed(*args):
        raise SQLAlchemyError("commit failed")

    with monkeypatch.context() as patch:
        patch.setattr(action_service, "_finalize_undo", commit_failed)
        undo_organize(db, log_id)

    assert reconcile_pending(db) == 0
    assert db.query(File).filter_by(id=file.id).one().path == src
    assert read(src) == "본문"
    assert db.query(ActionBatch).one().is_undone is True
    with pytest.raises(HTTPException) as raised:
        undo_organize(db, log_id)
    assert raised.value.status_code == 409


def test_startup_runs_reconcile(monkeypatch):
    import main

    calls = []
    monkeypatch.setattr(main, "reconcile_pending", lambda session: calls.append(session) or 3)
    with TestClient(main.app):
        pass
    assert len(calls) == 1
