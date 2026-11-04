import logging
import os

from sqlalchemy.orm import Session

from models.schema import ActionBatch, ActionLog, File

logger = logging.getLogger(__name__)

UNRESOLVED_TYPES = ("pending", "undo_pending")


def _inode(path: str) -> str | None:
    # 권한 오류는 "파일 없음"이 아니므로 전파해 미해결로 남긴다
    try:
        return str(os.lstat(path).st_ino)
    except (FileNotFoundError, NotADirectoryError):
        return None


def repoint_file(db: Session, old_path: str, new_path: str) -> None:
    """File 행의 경로를 옮긴다. 다른 행이 쓰는 경로면 수동 분류를 잃지 않게 건너뛴다"""
    if db.query(File).filter(File.path == new_path).first():
        logger.warning("경로를 쓰는 다른 파일 행이 있어 갱신을 건너뜀: %s", new_path)
        return
    file = db.query(File).filter(File.path == old_path).first()
    if file:
        file.path = new_path


def _reconcile_move(db: Session, log: ActionLog) -> None:
    recorded = log.identity.inode if log.identity else None
    source = _inode(log.source_path)
    destination = _inode(log.destination_path)

    if recorded is not None and destination == recorded:
        if source == recorded:
            # 링크만 만들고 중단됨: 원본이 그대로이므로 방금 만든 링크만 지운다
            os.unlink(log.destination_path)
            log.action_type = "failed"
        else:
            log.action_type = "move"
            repoint_file(db, log.source_path, log.destination_path)
    elif destination is None or source is not None:
        log.action_type = "failed"
    else:
        # 원본은 없고 대상은 다른 파일: 옮긴 뒤 교체됐는지 알 수 없어 건드리지 않는다
        log.action_type = "unverified"


def _complete_undo(db: Session, log: ActionLog) -> None:
    log.action_type = "move"
    log.is_undone = True
    repoint_file(db, log.destination_path, log.source_path)


def _reconcile_undo(db: Session, log: ActionLog) -> None:
    source = _inode(log.source_path)
    destination = _inode(log.destination_path)

    if not log.identity:
        # 식별값 도입 전에 옮긴 로그: 존재 여부로만 판단한다
        if source is not None and destination is None:
            _complete_undo(db, log)
        else:
            log.action_type = "move"
        return

    recorded = log.identity.inode
    if source != recorded:
        log.action_type = "move"
    elif destination == recorded:
        # 링크만 만들고 중단됨: 정리된 위치가 그대로이므로 방금 만든 링크만 지운다
        os.unlink(log.source_path)
        log.action_type = "move"
    else:
        _complete_undo(db, log)


def _reconcile_one(db: Session, log: ActionLog) -> None:
    if log.action_type == "pending":
        _reconcile_move(db, log)
    else:
        _reconcile_undo(db, log)
    db.commit()


def _recount_batch(db: Session, action_log_id: str) -> None:
    batch = db.query(ActionBatch).filter(ActionBatch.action_log_id == action_log_id).first()
    if not batch:
        return
    logs = db.query(ActionLog).filter(ActionLog.action_log_id == action_log_id).all()
    moves = [log for log in logs if log.action_type == "move"]
    batch.moved_count = len(moves)
    batch.is_undone = bool(moves) and all(log.is_undone for log in moves)
    batch.failed_count = sum(1 for log in logs if log.action_type in ("failed", "unverified"))
    db.commit()


def reconcile_pending(db: Session) -> int:
    """
    중단된 이동과 되돌리기를 실제 파일과 대조해 확정한다.
    처리하지 못하고 남은 로그 수를 반환하며 예외를 전파하지 않는다.
    """
    try:
        logs = db.query(ActionLog).filter(ActionLog.action_type.in_(UNRESOLVED_TYPES)).all()
    except Exception as e:
        db.rollback()
        logger.warning("조정 대상 조회 실패: %s", e)
        return 1

    remaining = 0
    batch_ids = set()
    for log in logs:
        batch_ids.add(log.action_log_id)
        try:
            _reconcile_one(db, log)
        except Exception as e:
            db.rollback()
            remaining += 1
            logger.warning("이동 조정 실패 %s: %s", log.destination_path, e)

    for action_log_id in batch_ids:
        try:
            _recount_batch(db, action_log_id)
        except Exception as e:
            db.rollback()
            logger.warning("배치 집계 실패 %s: %s", action_log_id, e)
    return remaining
