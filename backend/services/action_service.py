import os
import re
import uuid
import shutil
import logging
from sqlalchemy.orm import Session

from models.schema import File, Classification, ActionLog, ActionBatch, Rule
from utils.errors import ErrorCode, raise_error

logger = logging.getLogger(__name__)

UNCLASSIFIED_THRESHOLD = 0.31

# Path Traversal 방지: 폴더명에 허용되지 않는 문자 제거
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|\x00]|\.\.')


def _sanitize_path_component(name: str) -> str:
    """폴더명 구성 요소에서 경로 순회 위험 문자 제거"""
    sanitized = _UNSAFE_CHARS.sub("_", name).strip(". ")
    return sanitized or "기타"


def _find_common_base(file_paths: list[str]) -> str:
    """
    파일 경로 목록에서 공통 스캔 루트 디렉토리 추출
    첫 번째 파일의 부모를 사용하는 대신 os.path.commonpath로 정확한 루트 찾기
    """
    if not file_paths:
        return os.sep
    dirs = [os.path.dirname(p) for p in file_paths]
    try:
        return os.path.commonpath(dirs)
    except ValueError:
        return os.path.dirname(file_paths[0])


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

    # base_dir 범위 이탈 방지 (최종 이중 검증)
    if not os.path.normpath(dest).startswith(os.path.normpath(base_dir)):
        dest = os.path.join(base_dir, "기타", safe_filename)

    return dest


def _resolve_conflict(dest_path: str, resolution: str) -> str | None:
    """
    충돌 해결 전략 적용
    - overwrite: 그대로 덮어쓰기
    - rename: 파일명에 번호 추가 (report_1.pdf)
    - skip: None 반환 → 이동 건너뜀
    """
    if not os.path.exists(dest_path):
        return dest_path

    if resolution == "overwrite":
        return dest_path

    if resolution == "skip":
        return None

    # rename: 중복 번호 부여 (상한 1000)
    base, ext = os.path.splitext(dest_path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
        if counter > 1000:
            return None
    return f"{base}_{counter}{ext}"


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


def build_preview(db: Session, scan_id: str) -> dict:
    """
    UC-06: 정리 적용 미리보기
    실제 파일 이동 없이 이동 계획 트리 반환
    """
    rules = db.query(Rule).order_by(Rule.priority).all()
    rows = _get_best_classifications(db, scan_id)

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    base_dir = _find_common_base([f.path for f, _ in rows])

    total_files = 0
    excluded_files = 0
    folders_to_create: set[str] = set()
    conflicts = []
    preview_tree: dict[str, list] = {}

    for file, cls in rows:
        if not cls or cls.confidence_score < UNCLASSIFIED_THRESHOLD:
            excluded_files += 1
            continue

        total_files += 1
        dest_path = _get_destination(file, cls, base_dir, rules)
        dest_dir = os.path.dirname(dest_path)
        folders_to_create.add(dest_dir)

        if os.path.exists(dest_path) and dest_path != file.path:
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
    rules = db.query(Rule).order_by(Rule.priority).all()
    rows = _get_best_classifications(db, scan_id)

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    base_dir = _find_common_base([f.path for f, _ in rows])
    action_log_id = f"log_{uuid.uuid4().hex[:12]}"

    # 배치 레코드 선행 생성 (FK 제약 충족)
    batch = ActionBatch(
        action_log_id=action_log_id,
        folder_path=folder_path,
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
        if os.path.normpath(dest_path) == os.path.normpath(file.path):
            skipped += 1
            continue

        final_dest = _resolve_conflict(dest_path, conflict_resolution)
        if final_dest is None:
            skipped += 1
            db.add(ActionLog(
                action_log_id=action_log_id,
                action_type="skip",
                source_path=file.path,
                destination_path=dest_path,
                is_undone=False,
            ))
            db.commit()
            continue

        original_path = file.path
        try:
            os.makedirs(os.path.dirname(final_dest), exist_ok=True)
            shutil.move(original_path, final_dest)
        except Exception as e:
            failed += 1
            logger.warning("파일 이동 실패 %s → %s: %s", original_path, final_dest, e)
            db.add(ActionLog(
                action_log_id=action_log_id,
                action_type="failed",
                source_path=original_path,
                destination_path=final_dest,
                is_undone=False,
            ))
            db.commit()
            continue

        file.path = final_dest
        db.add(ActionLog(
            action_log_id=action_log_id,
            action_type="move",
            source_path=original_path,
            destination_path=final_dest,
            is_undone=False,
        ))
        db.commit()
        moved += 1

    # 배치 요약 갱신
    batch.moved_count = moved
    batch.skipped_count = skipped
    batch.failed_count = failed
    db.commit()

    return {
        "moved": moved,
        "skipped": skipped,
        "failed": failed,
        "action_log_id": action_log_id,
    }


def undo_organize(db: Session, action_log_id: str) -> dict:
    """
    UC-07: 되돌리기 — action_logs 역방향 이동 + 배치 상태 갱신
    """
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
    failed = 0
    unrestorable = []

    for log in logs:
        if log.is_undone:
            continue

        if not os.path.exists(log.destination_path):
            unrestorable.append({
                "filename": os.path.basename(log.destination_path),
                "reason": "destination_file_not_found",
            })
            failed += 1
            continue

        try:
            dest = log.destination_path
            src = log.source_path
            os.makedirs(os.path.dirname(src), exist_ok=True)
            shutil.move(dest, src)

            file = db.query(File).filter(File.path == dest).first()
            if file:
                file.path = src
                db.commit()

            log.is_undone = True
            db.commit()
            restored += 1
        except Exception:
            failed += 1
            unrestorable.append({
                "filename": os.path.basename(log.destination_path),
                "reason": "move_failed",
            })

    if batch:
        batch.is_undone = True
        db.commit()

    return {
        "restored": restored,
        "failed": failed,
        "unrestorable": unrestorable,
    }


def get_folder_history(db: Session, folder_path: str) -> list[dict]:
    """
    특정 폴더의 전체 정리 이력 조회 (최신순)
    """
    batches = (
        db.query(ActionBatch)
        .filter(ActionBatch.folder_path == folder_path)
        .order_by(ActionBatch.executed_at.desc())
        .all()
    )

    return [
        {
            "action_log_id": b.action_log_id,
            "scan_id": b.scan_id,
            "moved_count": b.moved_count,
            "skipped_count": b.skipped_count,
            "failed_count": b.failed_count,
            "conflict_resolution": b.conflict_resolution,
            "executed_at": b.executed_at.isoformat() if b.executed_at else None,
            "is_undone": b.is_undone,
        }
        for b in batches
    ]
