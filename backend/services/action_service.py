import os
import re
import uuid
import logging
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.schema import File, Classification, ActionLog, ActionBatch, ActionLogIdentity, Rule
from services.move_recovery import reconcile_pending
from services.safe_move import inode_of, move_no_clobber
from utils.errors import ErrorCode, raise_error
from utils.paths import canonical_path, is_within, same_path, validate_folder_path

logger = logging.getLogger(__name__)

UNCLASSIFIED_THRESHOLD = 0.31

# Path Traversal 방지: 폴더명에 허용되지 않는 문자 제거
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|\x00]|\.\.')


def _sanitize_path_component(name: str) -> str:
    """폴더명 구성 요소에서 경로 순회 위험 문자 제거"""
    sanitized = _UNSAFE_CHARS.sub("_", name).strip(". ")
    return sanitized or "기타"


def resolve_base_dir(folder_path: str, files: list[File]) -> str:
    """요청 폴더를 정리 기준으로 확정. 대상 파일이 하나라도 벗어나면 전체 거부"""
    base_dir = validate_folder_path(folder_path)
    if base_dir is None:
        raise_error(ErrorCode.PERMISSION_DENIED, "허용되지 않은 경로입니다")
    if not os.path.isdir(base_dir):
        raise_error(ErrorCode.FOLDER_NOT_FOUND)
    # 파일 자체가 심볼릭 링크여도 판단이 흔들리지 않게 부모 폴더로 확인한다
    if any(not is_within(os.path.dirname(f.path), base_dir) for f in files):
        raise_error(ErrorCode.PERMISSION_DENIED, "정리 폴더 밖의 파일이 포함되어 있습니다")
    return base_dir


def is_occupied(db: Session, path: str, own_file_id: int | None) -> bool:
    """디스크의 파일이나 다른 File 행이 경로를 쓰고 있는지 판단"""
    if os.path.lexists(path):
        return True
    query = db.query(File).filter(File.path == path)
    if own_file_id is not None:
        query = query.filter(File.id != own_file_id)
    return query.first() is not None


def _match_rule(rule: Rule, file: File, cls: Classification | None) -> bool:
    """규칙이 파일에 매칭되는지 판별"""
    if rule.type == "date" and file.modified_at:
        return str(file.modified_at.year) == rule.value
    if rule.type == "extension" and file.extension:
        return file.extension.lstrip(".").lower() == rule.value.lower()
    if rule.type == "content":
        keyword = rule.value.lower()
        if file.extracted_text_summary and keyword in file.extracted_text_summary.lower():
            return True
        if keyword in file.filename.lower():
            return True
        if cls and cls.category and keyword in cls.category.lower():
            return True
        return False
    return False


def _build_ancestor_path(rule: Rule, rule_map: dict[int, Rule]) -> list[str]:
    """
    규칙의 조상 체인을 따라 폴더 경로 구성 (루트 → 현재 규칙 순서)
    예: 규칙 C(parent=B), B(parent=A), A(parent=None)
    → [A.folder_name, B.folder_name, C.folder_name]
    """
    chain = []
    current = rule
    visited = set()
    while current:
        if current.id in visited:
            break
        visited.add(current.id)
        chain.append(_sanitize_path_component(current.folder_name))
        current = rule_map.get(current.parent_id) if current.parent_id else None
    chain.reverse()
    return chain


def _get_destination(
    file: File,
    cls: Classification | None,
    base_dir: str,
    rules: list[Rule],
) -> str:
    """
    트리 기반 규칙 우선순위로 폴더 경로 생성

    규칙 간 parent_id 관계로 중첩/플랫을 결정:
      - parent_id가 None인 규칙끼리는 동일 레벨 (flat)
      - parent_id가 있는 규칙은 부모 폴더 하위에 중첩 (nested)

    예: 규칙 [2025(루트), 보안(parent=2025), PDF(루트)]
      → 2025년 보안 파일: base/2025/보안/file.pdf
      → 2025년 PDF 파일: base/2025/file.pdf (PDF는 루트이므로 별도 경로)
    """
    rule_map = {r.id: r for r in rules}
    sorted_rules = sorted(rules, key=lambda r: r.priority)

    best_match: Rule | None = None
    for rule in sorted_rules:
        if _match_rule(rule, file, cls):
            if best_match is None:
                best_match = rule
            elif rule.parent_id is not None:
                ancestor = rule
                is_descendant = False
                visited = set()
                while ancestor and ancestor.id not in visited:
                    visited.add(ancestor.id)
                    if ancestor.parent_id == best_match.id:
                        is_descendant = True
                        break
                    ancestor = rule_map.get(ancestor.parent_id) if ancestor.parent_id else None
                if is_descendant:
                    best_match = rule

    if best_match:
        parts = _build_ancestor_path(best_match, rule_map)
    elif cls and cls.category:
        parts = [_sanitize_path_component(cls.category)]
    else:
        parts = ["기타"]

    safe_filename = os.path.basename(file.filename)
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = f"unnamed_{file.id}{file.extension or ''}"

    folder = os.path.join(base_dir, *parts)
    dest = os.path.join(folder, safe_filename)

    return dest


def _resolve_conflict(
    db: Session,
    dest_path: str,
    resolution: str,
    own_file_id: int | None,
) -> str | None:
    """
    충돌 해결 전략 적용
    - rename: 파일명에 번호 추가 (report_1.pdf)
    - skip: None 반환 → 이동 건너뜀
    """
    if not is_occupied(db, dest_path, own_file_id):
        return dest_path

    if resolution == "skip":
        return None

    # rename: 중복 번호 부여 (상한 1000)
    base, ext = os.path.splitext(dest_path)
    counter = 1
    while is_occupied(db, f"{base}_{counter}{ext}", own_file_id):
        counter += 1
        if counter > 1000:
            return None
    return f"{base}_{counter}{ext}"


def _changed_since_scan(file: File) -> bool:
    """스캔한 뒤 같은 경로의 파일이 바뀌었으면 그 분류를 적용하지 않는다"""
    try:
        stat = os.lstat(file.path)
    except OSError:
        return False
    if file.size is not None and stat.st_size != file.size:
        return True
    if file.modified_at is None:
        return False
    return datetime.fromtimestamp(stat.st_mtime) != file.modified_at


def _not_movable(file: File) -> bool:
    return os.path.islink(file.path) or _changed_since_scan(file)


def _get_best_classifications(db: Session, scan_id: str) -> list[tuple]:
    """
    파일별 최우선 분류 결과 반환 (수동 > 최신 자동)
    수동 분류(is_manual=True)는 scan_id와 무관하게 항상 우선 적용
    """
    auto_cls = (
        db.query(Classification)
        .filter(Classification.scan_id == scan_id, Classification.is_manual == False)
        .order_by(Classification.classified_at.desc())
        .all()
    )

    file_ids = {cls.file_id for cls in auto_cls}
    if not file_ids:
        return []

    best_cls: dict[int, Classification] = {}
    for cls in auto_cls:
        if cls.file_id not in best_cls:
            best_cls[cls.file_id] = cls

    manual_cls = (
        db.query(Classification)
        .filter(Classification.file_id.in_(file_ids), Classification.is_manual == True)
        .order_by(Classification.classified_at.desc())
        .all()
    )
    for cls in manual_cls:
        if cls.file_id not in best_cls or not best_cls[cls.file_id].is_manual:
            best_cls[cls.file_id] = cls

    files_map = {
        f.id: f for f in db.query(File).filter(File.id.in_(list(best_cls.keys()))).all()
    }
    return [(files_map[fid], cls) for fid, cls in best_cls.items() if fid in files_map]


def _add_log(
    db: Session,
    action_log_id: str,
    action_type: str,
    source_path: str,
    destination_path: str,
) -> ActionLog:
    log = ActionLog(
        action_log_id=action_log_id,
        action_type=action_type,
        source_path=source_path,
        destination_path=destination_path,
        is_undone=False,
    )
    db.add(log)
    _try_commit(db, f"로그 저장 {action_type} {source_path}")
    return log


def _try_commit(db: Session, context: str) -> bool:
    """기록 실패가 요청 전체를 중단시키지 않게 한다. 남은 pending은 조정 절차가 정리한다"""
    try:
        db.commit()
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning("기록 실패 (%s): %s", context, e)
        return False


def _finalize_move(db: Session, log: ActionLog, file: File, final_dest: str) -> None:
    log.action_type = "move"
    file.path = final_dest
    db.commit()


def _move_with_journal(
    db: Session,
    action_log_id: str,
    file: File,
    final_dest: str,
) -> bool:
    """
    파일 식별값과 함께 pending 로그를 먼저 남기고 옮긴다.
    최종 커밋이 실패하면 파일은 이미 옮겨졌으므로 pending을 남겨 조정 절차에 맡긴다.
    """
    source_path = file.path
    try:
        inode = inode_of(source_path)
    except OSError as e:
        logger.warning("파일 확인 실패 %s: %s", source_path, e)
        _add_log(db, action_log_id, "failed", source_path, final_dest)
        return False

    log = ActionLog(
        action_log_id=action_log_id,
        action_type="pending",
        source_path=source_path,
        destination_path=final_dest,
        is_undone=False,
        identity=ActionLogIdentity(inode=inode),
    )
    db.add(log)
    try:
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning("이동 기록 실패 %s: %s", source_path, e)
        return False

    try:
        os.makedirs(os.path.dirname(final_dest), exist_ok=True)
        move_no_clobber(source_path, final_dest)
    except OSError as e:
        logger.warning("파일 이동 실패 %s → %s: %s", source_path, final_dest, e)
        log.action_type = "failed"
        _try_commit(db, f"이동 실패 {source_path}")
        return False

    try:
        _finalize_move(db, log, file, final_dest)
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning("이동 완료 기록 실패 %s: %s", final_dest, e)
        return False
    return True


def build_preview(db: Session, scan_id: str, folder_path: str) -> dict:
    """
    UC-06: 정리 적용 미리보기
    실제 파일 이동 없이 이동 계획 트리 반환
    """
    rules = db.query(Rule).order_by(Rule.priority).all()
    rows = _get_best_classifications(db, scan_id)

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    base_dir = resolve_base_dir(folder_path, [f for f, _ in rows])

    total_files = 0
    excluded_files = 0
    folders_to_create: set[str] = set()
    conflicts = []
    preview_tree: dict[str, list] = {}

    for file, cls in rows:
        if not cls or cls.confidence_score < UNCLASSIFIED_THRESHOLD or _not_movable(file):
            excluded_files += 1
            continue

        total_files += 1
        dest_path = _get_destination(file, cls, base_dir, rules)
        dest_dir = os.path.dirname(dest_path)
        if not os.path.isdir(dest_dir):
            folders_to_create.add(dest_dir)

        if not same_path(dest_path, file.path) and is_occupied(db, dest_path, file.id):
            conflicts.append({
                "filename": file.filename,
                "destination": dest_path,
                "conflict_type": "duplicate_name",
            })

        rel_folder = os.path.relpath(dest_dir, base_dir)
        top_folder = rel_folder.split(os.sep)[0]
        if top_folder not in preview_tree:
            preview_tree[top_folder] = []
        preview_tree[top_folder].append(file.filename)

    tree_list = [
        {
            "folder": folder,
            "children": [{"file": f} for f in files],
        }
        for folder, files in preview_tree.items()
    ]

    return {
        "total_files": total_files,
        "excluded_files": excluded_files,
        "folders_to_create": len(folders_to_create),
        "conflicts": conflicts,
        "preview_tree": tree_list,
    }


def _require_reconciled(db: Session) -> None:
    """해결되지 않은 이동 위에 새 작업이 쌓이면 나중에 조정할 수 없어 막는다"""
    if reconcile_pending(db):
        raise_error(ErrorCode.MOVES_UNRESOLVED)


def apply_organize(
    db: Session,
    scan_id: str,
    conflict_resolution: str,
    folder_path: str,
) -> dict:
    """
    UC-06: 정리 적용 실행
    파일 이동 후 ActionBatch + ActionLog 저장
    """
    _require_reconciled(db)
    rules = db.query(Rule).order_by(Rule.priority).all()
    rows = _get_best_classifications(db, scan_id)

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    base_dir = resolve_base_dir(folder_path, [f for f, _ in rows])
    action_log_id = f"log_{uuid.uuid4().hex[:12]}"

    # 배치 레코드 선행 생성 (FK 제약 충족)
    batch = ActionBatch(
        action_log_id=action_log_id,
        folder_path=base_dir,
        scan_id=scan_id,
        conflict_resolution=conflict_resolution,
    )
    db.add(batch)
    db.commit()

    moved = 0
    skipped = 0
    failed = 0

    for file, cls in rows:
        if not cls or cls.confidence_score < UNCLASSIFIED_THRESHOLD:
            skipped += 1
            continue

        dest_path = _get_destination(file, cls, base_dir, rules)
        if _not_movable(file):
            skipped += 1
            _add_log(db, action_log_id, "skip", file.path, dest_path)
            continue

        if same_path(dest_path, file.path):
            skipped += 1
            continue

        if not is_within(os.path.dirname(dest_path), base_dir):
            failed += 1
            logger.warning("정리 폴더 밖으로 나가는 경로: %s", dest_path)
            _add_log(db, action_log_id, "failed", file.path, dest_path)
            continue

        final_dest = _resolve_conflict(db, dest_path, conflict_resolution, file.id)
        if final_dest is None:
            skipped += 1
            _add_log(db, action_log_id, "skip", file.path, dest_path)
            continue

        if _move_with_journal(db, action_log_id, file, final_dest):
            moved += 1
        else:
            failed += 1

    # 배치 요약 갱신
    batch.moved_count = moved
    batch.skipped_count = skipped
    batch.failed_count = failed
    _try_commit(db, f"배치 요약 {action_log_id}")

    return {
        "moved": moved,
        "skipped": skipped,
        "failed": failed,
        "action_log_id": action_log_id,
    }


def _undo_block_reason(
    db: Session,
    log: ActionLog,
    batch: ActionBatch | None,
    file: File | None,
) -> str | None:
    """되돌리면 안 되는 이유. 다른 파일을 옮기거나 덮어쓰지 않도록 이동 전에 확인"""
    if not os.path.lexists(log.destination_path):
        return "destination_file_not_found"
    if log.identity and inode_of(log.destination_path) != log.identity.inode:
        return "identity_mismatch"
    if batch and not is_within(os.path.dirname(log.source_path), batch.folder_path):
        return "source_outside_root"
    if is_occupied(db, log.source_path, file.id if file else None):
        return "source_occupied"
    return None


def _finalize_undo(db: Session, log: ActionLog, file: File | None) -> None:
    log.action_type = "move"
    log.is_undone = True
    if file:
        file.path = log.source_path
    db.commit()


def _undo_one(db: Session, log: ActionLog, batch: ActionBatch | None) -> str | None:
    """로그 하나를 되돌리고 실패 사유를 반환. 성공하면 None"""
    file = db.query(File).filter(File.path == log.destination_path).first()
    reason = _undo_block_reason(db, log, batch, file)
    if reason:
        return reason

    log.action_type = "undo_pending"
    if not _try_commit(db, f"되돌리기 시작 {log.source_path}"):
        return "move_failed"
    try:
        os.makedirs(os.path.dirname(log.source_path), exist_ok=True)
        move_no_clobber(log.destination_path, log.source_path)
    except OSError as e:
        logger.warning("되돌리기 실패 %s: %s", log.destination_path, e)
        log.action_type = "move"
        _try_commit(db, f"되돌리기 복귀 {log.source_path}")
        return "source_occupied" if isinstance(e, FileExistsError) else "move_failed"

    try:
        _finalize_undo(db, log, file)
    except SQLAlchemyError as e:
        # 파일은 이미 돌아왔으므로 undo_pending을 남겨 조정 절차에 맡긴다
        db.rollback()
        logger.warning("되돌리기 완료 기록 실패 %s: %s", log.source_path, e)
        return "move_failed"
    return None


def undo_organize(db: Session, action_log_id: str) -> dict:
    """
    UC-07: 되돌리기 — action_logs 역방향 이동 + 배치 상태 갱신
    """
    _require_reconciled(db)
    batch = (
        db.query(ActionBatch)
        .filter(ActionBatch.action_log_id == action_log_id)
        .first()
    )

    logs = (
        db.query(ActionLog)
        .filter(
            ActionLog.action_log_id == action_log_id,
            ActionLog.action_type == "move",
        )
        .all()
    )

    if not logs:
        raise_error(ErrorCode.LOG_NOT_FOUND)

    if all(log.is_undone for log in logs):
        raise_error(ErrorCode.ALREADY_UNDONE)

    restored = 0
    unrestorable = []

    for log in logs:
        if log.is_undone:
            continue
        reason = _undo_one(db, log, batch)
        if reason:
            unrestorable.append({
                "filename": os.path.basename(log.destination_path),
                "reason": reason,
            })
        else:
            restored += 1

    if batch:
        batch.is_undone = all(log.is_undone for log in logs)
        _try_commit(db, f"배치 되돌림 {action_log_id}")

    return {
        "restored": restored,
        "failed": len(unrestorable),
        "unrestorable": unrestorable,
    }


def _undo_state(batch: ActionBatch) -> str:
    moves = [log for log in batch.logs if log.action_type in ("move", "undo_pending")]
    undone = sum(1 for log in moves if log.is_undone)
    if undone == 0:
        return "none"
    return "undone" if undone == len(moves) else "partial"


def _history_item(batch: ActionBatch) -> dict:
    # 요약 저장 전에 중단될 수 있어 건수와 되돌림 상태는 로그에서 계산한다
    state = _undo_state(batch)
    return {
        "action_log_id": batch.action_log_id,
        "scan_id": batch.scan_id,
        "moved_count": sum(1 for log in batch.logs if log.action_type in ("move", "undo_pending")),
        "skipped_count": batch.skipped_count,
        "failed_count": sum(1 for log in batch.logs if log.action_type in ("failed", "unverified")),
        "conflict_resolution": batch.conflict_resolution,
        # DB에는 UTC가 시간대 없이 저장되므로 표시해 주지 않으면 화면이 현지 시각으로 읽는다
        "executed_at": f"{batch.executed_at.isoformat()}Z" if batch.executed_at else None,
        "is_undone": state == "undone",
        "undo_state": state,
    }


def get_folder_history(db: Session, folder_path: str) -> list[dict]:
    """
    특정 폴더의 전체 정리 이력 조회 (최신순)
    과거 이력은 정규화 전 경로로 저장됐을 수 있어 여러 표기로 찾는다
    """
    real = os.path.realpath(folder_path)
    batches = (
        db.query(ActionBatch)
        .filter(ActionBatch.folder_path.in_([folder_path, real, canonical_path(real)]))
        .order_by(ActionBatch.executed_at.desc())
        .all()
    )
    return [_history_item(b) for b in batches]
