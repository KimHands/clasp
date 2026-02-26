import os
import re
import shutil
from datetime import datetime
from sqlalchemy.orm import Session

from models.schema import File, Classification, ActionLog, Rule
from utils.errors import ErrorCode, raise_error

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
    if rule.type == "content" and cls and cls.category:
        return rule.value.lower() in cls.category.lower()
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
            # 가장 깊은(구체적인) 매칭 규칙을 찾기 위해 자식 우선 탐색
            # 부모도 매칭되고 자식도 매칭되면 자식이 더 구체적
            if best_match is None:
                best_match = rule
            elif rule.parent_id is not None:
                # 현재 best_match의 후손인지 확인
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

    folder = os.path.join(base_dir, *parts)
    dest = os.path.join(folder, file.filename)

    # base_dir 범위 이탈 방지 (최종 이중 검증)
    if not os.path.normpath(dest).startswith(os.path.normpath(base_dir)):
        dest = os.path.join(base_dir, "기타", file.filename)

    return dest


def _resolve_conflict(dest_path: str, resolution: str) -> str:
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

    # rename: 중복 번호 부여
    base, ext = os.path.splitext(dest_path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"


def _get_best_classifications(db: Session, scan_id: str) -> list[tuple]:
    """파일별 최우선 분류 결과 반환 (수동 > 최신 자동)"""
    all_cls = (
        db.query(Classification)
        .filter(Classification.scan_id == scan_id)
        .order_by(Classification.is_manual.desc(), Classification.classified_at.desc())
        .all()
    )
    best_cls: dict[int, Classification] = {}
    for cls in all_cls:
        if cls.file_id not in best_cls:
            best_cls[cls.file_id] = cls
        elif cls.is_manual and not best_cls[cls.file_id].is_manual:
            best_cls[cls.file_id] = cls

    if not best_cls:
        return []

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

    # 공통 스캔 루트 디렉토리 (모든 파일 경로에서 commonpath 추출)
    base_dir = _find_common_base([f.path for f, _ in rows])

    total_files = 0
    excluded_files = 0
    folders_to_create: set[str] = set()
    conflicts = []
    preview_tree: dict[str, list] = {}

    for file, cls in rows:
        # 미분류 파일 자동 제외
        if not cls or cls.confidence_score < UNCLASSIFIED_THRESHOLD:
            excluded_files += 1
            continue

        total_files += 1
        dest_path = _get_destination(file, cls, base_dir, rules)
        dest_dir = os.path.dirname(dest_path)
        folders_to_create.add(dest_dir)

        # 충돌 감지
        if os.path.exists(dest_path) and dest_path != file.path:
            conflicts.append({
                "filename": file.filename,
                "destination": dest_path,
                "conflict_type": "duplicate_name",
            })

        # 트리 구조 구성
        rel_folder = os.path.relpath(dest_dir, base_dir)
        top_folder = rel_folder.split(os.sep)[0]
        if top_folder not in preview_tree:
            preview_tree[top_folder] = []
        preview_tree[top_folder].append(file.filename)

    # 트리 직렬화
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
) -> dict:
    """
    UC-06: 정리 적용 실행
    파일 이동 후 action_logs 저장
    """
    rules = db.query(Rule).order_by(Rule.priority).all()
    rows = _get_best_classifications(db, scan_id)

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    # 공통 스캔 루트 디렉토리 (모든 파일 경로에서 commonpath 추출)
    base_dir = _find_common_base([f.path for f, _ in rows])
    action_log_id = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    moved = 0
    skipped = 0
    failed = 0

    for file, cls in rows:
        # 미분류 파일 자동 제외
        if not cls or cls.confidence_score < UNCLASSIFIED_THRESHOLD:
            skipped += 1
            continue

        # 이미 올바른 위치에 있는 파일 건너뜀
        dest_path = _get_destination(file, cls, base_dir, rules)
        if os.path.normpath(dest_path) == os.path.normpath(file.path):
            skipped += 1
            continue

        # 충돌 해결
        final_dest = _resolve_conflict(dest_path, conflict_resolution)
        if final_dest is None:
            skipped += 1
            log = ActionLog(
                action_log_id=action_log_id,
                action_type="skip",
                source_path=file.path,
                destination_path=dest_path,
                is_undone=False,
            )
            db.add(log)
            continue

        try:
            original_path = file.path
            os.makedirs(os.path.dirname(final_dest), exist_ok=True)
            shutil.move(original_path, final_dest)

            # DB 파일 경로 업데이트 (이동 전 원본 경로 보존 후 업데이트)
            file.path = final_dest
            db.commit()

            log = ActionLog(
                action_log_id=action_log_id,
                action_type="move",
                source_path=original_path,
                destination_path=final_dest,
                is_undone=False,
            )
            db.add(log)
            moved += 1
        except Exception as e:
            db.rollback()
            failed += 1
            print(f"[apply] 파일 이동 실패 {file.path} → {final_dest}: {e}")
            log = ActionLog(
                action_log_id=action_log_id,
                action_type="failed",
                source_path=file.path,
                destination_path=final_dest,
                is_undone=False,
            )
            db.add(log)

    db.commit()

    return {
        "moved": moved,
        "skipped": skipped,
        "failed": failed,
        "action_log_id": action_log_id,
    }


def undo_organize(db: Session, action_log_id: str) -> dict:
    """
    UC-07: 되돌리기 — action_logs 역방향 이동
    """
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

    # 이미 되돌린 작업 확인
    if all(log.is_undone for log in logs):
        raise_error(ErrorCode.ALREADY_UNDONE)

    restored = 0
    failed = 0
    unrestorable = []

    for log in logs:
        if log.is_undone:
            continue

        # destination → source 역방향 이동
        if not os.path.exists(log.destination_path):
            unrestorable.append({
                "filename": os.path.basename(log.destination_path),
                "reason": "original_path_not_found",
            })
            failed += 1
            continue

        try:
            dest = log.destination_path
            src = log.source_path
            os.makedirs(os.path.dirname(src), exist_ok=True)
            shutil.move(dest, src)

            # DB 파일 경로 복원
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

    return {
        "restored": restored,
        "failed": failed,
        "unrestorable": unrestorable,
    }
