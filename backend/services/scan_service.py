import os
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from sqlalchemy.orm import Session

from database import SessionLocal
from models.schema import File, Classification
from utils.text_extractor import extract_text
from utils.cover_detector import extract_cover_text
from services.cover_service import save_cover, compute_similarity_groups
from engines import pipeline

# 텍스트 추출 지원 확장자
TEXT_EXTRACTABLE = {".pdf", ".docx", ".doc", ".txt", ".md"}


def _collect_files(folder_path: str) -> list[str]:
    """폴더 재귀 탐색으로 파일 경로 목록 수집"""
    result = []
    for root, _, files in os.walk(folder_path):
        for fname in files:
            # 숨김 파일 제외
            if fname.startswith("."):
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
        await asyncio.sleep(0)

        file_paths = _collect_files(folder_path)
        total = len(file_paths)

        # Stage 2: 메타데이터 분석 + DB 저장 (체크포인트)
        yield {"stage": 2, "message": "메타데이터 분석 중", "total": total, "completed": 0, "current_file": ""}
        await asyncio.sleep(0)

        file_records: dict[str, File] = {}
        for i, path in enumerate(file_paths):
            filename = os.path.basename(path)
            extension = os.path.splitext(filename)[1].lower()
            meta = _get_metadata(path)

            # 이미 존재하는 파일이면 업데이트, 없으면 생성
            existing = db.query(File).filter(File.path == path).first()
            if existing:
                existing.filename = filename
                existing.extension = extension
                existing.size = meta["size"]
                existing.modified_at = meta["modified_at"]
                file_record = existing
            else:
                file_record = File(
                    path=path,
                    filename=filename,
                    extension=extension,
                    created_at=meta["created_at"],
                    modified_at=meta["modified_at"],
                    size=meta["size"],
                )
                db.add(file_record)

            db.commit()
            db.refresh(file_record)
            file_records[path] = file_record

            yield {"stage": 2, "message": "메타데이터 분석 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 3: 표지 탐지
        yield {"stage": 3, "message": "표지 탐지 중", "total": total, "completed": 0, "current_file": ""}
        await asyncio.sleep(0)

        cover_count = 0
        for i, path in enumerate(file_paths):
            filename = os.path.basename(path)
            cover_text = extract_cover_text(path)
            if cover_text:
                file_record = file_records[path]
                save_cover(db, file_record.id, cover_text)
                cover_count += 1

            yield {"stage": 3, "message": "표지 탐지 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 4: 본문 추출
        yield {"stage": 4, "message": "본문 추출 중", "total": total, "completed": 0, "current_file": ""}
        await asyncio.sleep(0)

        extracted_texts: dict[str, str | None] = {}
        for i, path in enumerate(file_paths):
            filename = os.path.basename(path)
            extension = os.path.splitext(filename)[1].lower()

            text = None
            if extension in TEXT_EXTRACTABLE:
                text = extract_text(path)
                if text:
                    file_record = file_records[path]
                    file_record.extracted_text_summary = text[:500]
                    db.commit()

            extracted_texts[path] = text

            yield {"stage": 4, "message": "본문 추출 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 5: 분류 엔진 처리
        yield {"stage": 5, "message": "분류 엔진 처리 중", "total": total, "completed": 0, "current_file": ""}
        await asyncio.sleep(0)

        for i, path in enumerate(file_paths):
            filename = os.path.basename(path)
            extension = os.path.splitext(filename)[1].lower()
            file_record = file_records[path]
            text = extracted_texts.get(path)

            # 이전 수동 분류 확인
            manual_cls = (
                db.query(Classification)
                .filter(Classification.file_id == file_record.id, Classification.is_manual == True)
                .order_by(Classification.classified_at.desc())
                .first()
            )
            manual_category = manual_cls.category if manual_cls else None

            result = await pipeline.classify(
                file_path=path,
                filename=filename,
                extension=extension,
                extracted_text=text,
                db=db,
                manual_category=manual_category,
            )

            # 기존 자동 분류 결과 삭제 후 새로 저장
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
            db.commit()

            yield {"stage": 5, "message": "분류 엔진 처리 중", "total": total, "completed": i + 1, "current_file": filename}
            await asyncio.sleep(0)

        # Stage 6: 유사도 계산
        yield {"stage": 6, "message": "유사도 계산 중", "total": total, "completed": total, "current_file": ""}
        await asyncio.sleep(0)
        compute_similarity_groups(db)

        # Stage 7: 완료
        yield {"stage": 7, "message": "완료", "total": total, "completed": total, "current_file": ""}

    finally:
        db.close()
