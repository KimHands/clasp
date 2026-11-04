"""
분류 결과 읽기 전용 조회.
MCP 클라이언트는 클라우드 LLM일 수 있으므로 기본 응답에는 파일명, 태그, 본문, 절대 경로를 넣지 않는다.
"""
import os
import pathlib
import re
import sqlite3
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from models.schema import Classification, File
from services.action_service import build_preview, get_folder_history, _get_best_classifications
from services.sensitive import is_sensitive, load_keywords
from utils.paths import app_data_dir, is_within, validate_folder_path

UNCLASSIFIED_THRESHOLD = 0.31
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
_MAX_FILENAME_LENGTH = 200
_MAX_LABEL_LENGTH = 40
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _database_path() -> str:
    return os.environ.get("CLASP_DB_PATH") or os.path.join(app_data_dir(), "clasp.db")


def _connect_readonly():
    path = _database_path()
    if not os.path.exists(path):
        raise ValueError("Clasp 데이터베이스가 없습니다. 앱에서 폴더를 먼저 스캔하세요")
    # as_uri() also handles Windows drive letters and backslashes
    uri = f"{pathlib.Path(path).resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
    connection.execute("PRAGMA query_only=ON")
    return connection


@contextmanager
def open_readonly_session():
    engine = create_engine("sqlite://", creator=_connect_readonly, poolclass=NullPool)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _clean_label(label: str | None) -> str | None:
    """카테고리와 폴더 이름도 DB에서 온 값이므로 줄바꿈, 경로, 긴 문장을 그대로 내보내지 않는다"""
    if label is None:
        return None
    return re.sub(r"[/\\]", "_", _CONTROL_CHARS.sub(" ", label))[:_MAX_LABEL_LENGTH]


def _validated_folder(folder_path: str) -> str:
    folder = validate_folder_path(folder_path)
    if folder is None:
        raise ValueError("홈 폴더 아래의 경로만 조회할 수 있습니다")
    return folder


def _latest_scan_id(db: Session, folder: str) -> str:
    row = (
        db.query(Classification.scan_id)
        .join(File, File.id == Classification.file_id)
        .filter(
            File.path.startswith(folder + os.sep, autoescape=True),
            Classification.is_manual == False,
        )
        .order_by(Classification.classified_at.desc(), Classification.id.desc())
        .first()
    )
    if row is None:
        raise ValueError("이 폴더의 스캔 결과가 없습니다. 앱에서 먼저 스캔하세요")
    return row[0]


def _rows_in_folder(db: Session, folder: str) -> list[tuple[File, Classification]]:
    rows = _get_best_classifications(db, _latest_scan_id(db, folder))
    return [(f, c) for f, c in rows if is_within(os.path.dirname(f.path), folder)]


def _is_unclassified(cls: Classification) -> bool:
    return cls.confidence_score < UNCLASSIFIED_THRESHOLD or cls.category is None


def classification_summary(folder_path: str) -> dict:
    folder = _validated_folder(folder_path)
    with open_readonly_session() as db:
        rows = _rows_in_folder(db, folder)
    by_category: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    unclassified = 0
    for _, cls in rows:
        by_tier[str(cls.tier_used)] = by_tier.get(str(cls.tier_used), 0) + 1
        if _is_unclassified(cls):
            unclassified += 1
        else:
            label = _clean_label(cls.category)
            by_category[label] = by_category.get(label, 0) + 1
    return {"total": len(rows), "unclassified": unclassified, "by_category": by_category, "by_tier": by_tier}


def _show_filenames() -> bool:
    return os.environ.get("CLASP_MCP_SHOW_FILENAMES") == "1"


def _file_item(file: File, cls: Classification, keywords: list[str]) -> dict:
    item = {
        "file_id": file.id,
        "extension": file.extension,
        "category": None if _is_unclassified(cls) else _clean_label(cls.category),
        "tier_used": cls.tier_used,
        "confidence_score": round(cls.confidence_score, 3),
        "is_manual": cls.is_manual,
    }
    if _show_filenames() and not is_sensitive(file.filename, keywords):
        # 파일명은 누구나 정할 수 있으므로 지시가 아니라 데이터로 다뤄야 한다
        item["untrusted_filename"] = _CONTROL_CHARS.sub(" ", file.filename)[:_MAX_FILENAME_LENGTH]
        item["tag"] = cls.tag
    return item


def classified_files(
    folder_path: str,
    category: str | None = None,
    only_unclassified: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    folder = _validated_folder(folder_path)
    limit = max(1, min(limit, MAX_LIMIT))
    with open_readonly_session() as db:
        keywords = load_keywords(db)
        rows = sorted(_rows_in_folder(db, folder), key=lambda row: row[0].id)
        if category is not None:
            rows = [(f, c) for f, c in rows if c.category == category and not _is_unclassified(c)]
        if only_unclassified:
            rows = [(f, c) for f, c in rows if _is_unclassified(c)]
        page = rows[max(0, offset):max(0, offset) + limit]
        return {
            "total": len(rows),
            "limit": limit,
            "offset": max(0, offset),
            "items": [_file_item(f, c, keywords) for f, c in page],
        }


def organize_plan(folder_path: str) -> dict:
    """미리보기와 같은 계산으로 건수만 돌려준다. 파일을 옮기지 않는다"""
    folder = _validated_folder(folder_path)
    with open_readonly_session() as db:
        scan_id = _latest_scan_id(db, folder)
        try:
            preview = build_preview(db, scan_id, folder)
        except HTTPException as e:
            raise ValueError(e.detail["error"]["message"]) from e
    return {
        "applied": False,
        "files_to_move": preview["total_files"],
        "excluded_files": preview["excluded_files"],
        "folders_to_create": preview["folders_to_create"],
        "conflict_count": len(preview["conflicts"]),
        "folders": [
            {"folder": _clean_label(entry["folder"]), "file_count": len(entry["children"])}
            for entry in preview["preview_tree"]
        ],
    }


def organize_history(folder_path: str) -> dict:
    folder = _validated_folder(folder_path)
    with open_readonly_session() as db:
        history = get_folder_history(db, folder)
    return {"batches": [{k: v for k, v in batch.items() if k != "scan_id"} for batch in history]}
