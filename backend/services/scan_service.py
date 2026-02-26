import os
import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator
from sqlalchemy.orm import Session

from database import SessionLocal
from models.schema import File, Classification
from utils.text_extractor import extract_text
from utils.cover_detector import extract_cover_text
from services.cover_service import save_cover, compute_similarity_groups
from engines import pipeline

logger = logging.getLogger(__name__)

TEXT_EXTRACTABLE = {".pdf", ".docx", ".doc", ".txt", ".md"}

EXCLUDED_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", "release", ".cache", ".mypy_cache",
    ".pytest_cache", "site-packages", "eggs", ".eggs",
}

EXCLUDED_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll", ".exe"}

BATCH_SIZE = 50


def _collect_files(folder_path: str) -> list[str]:
    """
    폴더 재귀 탐색으로 파일 경로 목록 수집 (시스템/빌드 디렉토리 제외)
    followlinks=False: 심볼릭 링크를 따라가지 않아 순환 참조로 인한 무한 루프 방지
    """
    result = []
    for root, dirs, files in os.walk(folder_path, followlinks=False):
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS and not d.startswith(".")
        ]
        for fname in files:
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in EXCLUDED_EXTENSIONS:
                continue
            result.append(os.path.join(root, fname))
    return result


def _get_metadata(file_path: str) -> dict:
    """파일 메타데이터 수집"""
    try:
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, "st_birthtime") else stat.st_ctime),
            "modified_at": datetime.fromtimestamp(stat.st_mtime),
        }
    except Exception:
        return {"size": None, "created_at": None, "modified_at": None}


async def run_scan(
    scan_id: str,
    folder_path: str,
) -> AsyncGenerator[dict, None]:
    """
    스캔 전체 파이프라인 실행 — SSE 이벤트 yield
    stage 1~7 순서로 진행 상황 전달
    """
    db: Session = SessionLocal()

    try:
        # Stage 1: 파일 목록 수집
        yield {"stage": 1, "message": "파일 목록 수집 중", "total": 0, "completed": 0, "current_file": ""}

        file_paths = await asyncio.to_thread(_collect_files, folder_path)
        total = len(file_paths)

        # Stage 2: 메타데이터 분석 + DB 저장 (배치 commit)
        yield {"stage": 2, "message": "메타데이터 분석 중", "total": total, "completed": 0, "current_file": ""}

        file_records: dict[str, File] = {}
        for i, fpath in enumerate(file_paths):
            filename = os.path.basename(fpath)
            extension = os.path.splitext(filename)[1].lower()
            meta = await asyncio.to_thread(_get_metadata, fpath)

            existing = db.query(File).filter(File.path == fpath).first()
            if existing:
                existing.filename = filename
                existing.extension = extension
                existing.size = meta["size"]
                existing.modified_at = meta["modified_at"]
                file_record = existing
            else:
                file_record = File(
                    path=fpath,
                    filename=filename,
                    extension=extension,
                    created_at=meta["created_at"],
                    modified_at=meta["modified_at"],
                    size=meta["size"],
                )
                db.add(file_record)

            if (i + 1) % BATCH_SIZE == 0 or i == total - 1:
                db.commit()
                for p in list(file_records.values())[-BATCH_SIZE:]:
                    db.refresh(p)
                db.refresh(file_record)

            file_records[fpath] = file_record

            yield {"stage": 2, "message": "메타데이터 분석 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # flush 후 전체 refresh (배치 commit으로 인해 id가 할당되지 않은 레코드 보정)
        db.commit()
        for fpath, rec in file_records.items():
            if rec.id is None:
                db.refresh(rec)

        # Stage 3: 표지 탐지
        yield {"stage": 3, "message": "표지 탐지 중", "total": total, "completed": 0, "current_file": ""}

        cover_count = 0
        for i, fpath in enumerate(file_paths):
            filename = os.path.basename(fpath)
            cover_text = await asyncio.to_thread(extract_cover_text, fpath)
            if cover_text:
                file_record = file_records[fpath]
                save_cover(db, file_record.id, cover_text)
                cover_count += 1

            yield {"stage": 3, "message": "표지 탐지 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 4: 본문 추출 (배치 commit)
        yield {"stage": 4, "message": "본문 추출 중", "total": total, "completed": 0, "current_file": ""}

        extracted_texts: dict[str, str | None] = {}
        for i, fpath in enumerate(file_paths):
            filename = os.path.basename(fpath)
            extension = os.path.splitext(filename)[1].lower()

            text = None
            if extension in TEXT_EXTRACTABLE:
                text = await asyncio.to_thread(extract_text, fpath)
                if text:
                    file_record = file_records[fpath]
                    file_record.extracted_text_summary = text[:500]

            extracted_texts[fpath] = text

            if (i + 1) % BATCH_SIZE == 0 or i == total - 1:
                db.commit()

            yield {"stage": 4, "message": "본문 추출 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 5: 분류 엔진 처리
        yield {"stage": 5, "message": "분류 엔진 처리 중", "total": total, "completed": 0, "current_file": ""}

        for i, fpath in enumerate(file_paths):
            filename = os.path.basename(fpath)
            extension = os.path.splitext(filename)[1].lower()
            file_record = file_records[fpath]
            text = extracted_texts.get(fpath)

            manual_cls = (
                db.query(Classification)
                .filter(Classification.file_id == file_record.id, Classification.is_manual == True)
                .order_by(Classification.classified_at.desc())
                .first()
            )
            manual_category = manual_cls.category if manual_cls else None

            result = await pipeline.classify(
                file_path=fpath,
                filename=filename,
                extension=extension,
                extracted_text=text,
                db=db,
                manual_category=manual_category,
            )

            db.query(Classification).filter(
                Classification.file_id == file_record.id,
                Classification.scan_id == scan_id,
                Classification.is_manual == False,
            ).delete()

            cls = Classification(
                file_id=file_record.id,
                scan_id=scan_id,
                category=result["category"],
                tag=result["tag"],
                tier_used=result["tier_used"],
                confidence_score=result["confidence_score"],
                is_manual=False,
            )
            db.add(cls)

            if (i + 1) % BATCH_SIZE == 0 or i == total - 1:
                db.commit()

            yield {"stage": 5, "message": "분류 엔진 처리 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 6: 유사도 계산
        yield {"stage": 6, "message": "유사도 계산 중", "total": total, "completed": total, "current_file": ""}
        await asyncio.to_thread(compute_similarity_groups, db)

        # Stage 7: 완료
        yield {"stage": 7, "message": "완료", "total": total, "completed": total, "current_file": ""}

    except Exception as e:
        logger.error("스캔 실패: %s", e, exc_info=True)
        yield {"stage": -1, "message": f"스캔 중 오류 발생: {e}", "total": 0, "completed": 0, "current_file": ""}
    finally:
        db.close()
