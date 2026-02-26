import os
import shutil
from datetime import datetime
from sqlalchemy.orm import Session

from models.schema import File, Classification, ActionLog, Rule
from utils.errors import ErrorCode, raise_error

UNCLASSIFIED_THRESHOLD = 0.31


def _get_destination(
    file: File,
    cls: Classification | None,
    base_dir: str,
    rules: list[Rule],
) -> str:
    """
    규칙 우선순위 순서로 폴더 경로 생성
    예: 2025 / 보안 / PDF / filename.pdf
    """
    parts = []

    if rules:
        for rule in sorted(rules, key=lambda r: r.priority):
            if rule.type == "date" and file.modified_at:
                year = str(file.modified_at.year)
                if year == rule.value:
                    parts.append(rule.folder_name)
            elif rule.type == "extension" and file.extension:
                if file.extension.lstrip(".").lower() == rule.value.lower():
                    parts.append(rule.folder_name)
            elif rule.type == "content" and cls and cls.category:
                if rule.value.lower() in cls.category.lower():
                    parts.append(rule.folder_name)

    # 규칙 매칭이 없으면 카테고리 폴더 사용
    if not parts and cls and cls.category:
        parts.append(cls.category)
    elif not parts:
        parts.append("기타")

    folder = os.path.join(base_dir, *parts)
    return os.path.join(folder, file.filename)


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


def build_preview(db: Session, scan_id: str) -> dict:
    """
    UC-06: 정리 적용 미리보기
    실제 파일 이동 없이 이동 계획 트리 반환
    """
    from sqlalchemy import case, func

    rules = db.query(Rule).order_by(Rule.priority).all()

    # 파일별 최신 분류 결과 (수동 우선)
    subq = (
        db.query(
            Classification.file_id,
            func.max(case((Classification.is_manual == True, 2), else_=1)).label("priority"),
        )
        .filter(Classification.scan_id == scan_id)
        .group_by(Classification.file_id)
        .subquery()
    )

    rows = (
        db.query(File, Classification)
        .join(Classification, (Classification.file_id == File.id) & (Classification.scan_id == scan_id))
        .join(
            subq,
            (subq.c.file_id == File.id) &
            (case((Classification.is_manual == True, 2), else_=1) == subq.c.priority),
        )
        .all()
    )

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    # 스캔 폴더 기준 디렉토리 (첫 파일의 부모 디렉토리)
    base_dir = os.path.dirname(rows[0][0].path)

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
    from sqlalchemy import case, func

    rules = db.query(Rule).order_by(Rule.priority).all()

    subq = (
        db.query(
            Classification.file_id,
            func.max(case((Classification.is_manual == True, 2), else_=1)).label("priority"),
        )
        .filter(Classification.scan_id == scan_id)
        .group_by(Classification.file_id)
        .subquery()
    )

    rows = (
        db.query(File, Classification)
        .join(Classification, (Classification.file_id == File.id) & (Classification.scan_id == scan_id))
        .join(
            subq,
            (subq.c.file_id == File.id) &
            (case((Classification.is_manual == True, 2), else_=1) == subq.c.priority),
        )
        .all()
    )

    if not rows:
        raise_error(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID의 분류 결과 없음")

    base_dir = os.path.dirname(rows[0][0].path)
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
            os.makedirs(os.path.dirname(final_dest), exist_ok=True)
            shutil.move(file.path, final_dest)

            # DB 파일 경로 업데이트
            file.path = final_dest
            db.commit()

            log = ActionLog(
                action_log_id=action_log_id,
                action_type="move",
                source_path=file.path,
                destination_path=final_dest,
                is_undone=False,
            )
            db.add(log)
            moved += 1
        except Exception:
            failed += 1
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
            os.makedirs(os.path.dirname(log.source_path), exist_ok=True)
            shutil.move(log.destination_path, log.source_path)

            # DB 파일 경로 복원
            file = db.query(File).filter(File.path == log.destination_path).first()
            if file:
                file.path = log.source_path
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
