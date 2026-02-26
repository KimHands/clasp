from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import get_db
from models.schema import File, Classification, CoverSimilarityGroup
from utils.response import ok, fail
from utils.errors import ErrorCode, raise_error
from services.classify_service import update_manual_classification

router = APIRouter(prefix="/files", tags=["files"])


class PatchFileRequest(BaseModel):
    category: Optional[str] = None
    tag: Optional[str] = None


def _build_file_item(file: File, cls: Classification | None) -> dict:
    return {
        "id": file.id,
        "filename": file.filename,
        "path": file.path,
        "extension": file.extension,
        "size": file.size,
        "created_at": file.created_at.isoformat() if file.created_at else None,
        "modified_at": file.modified_at.isoformat() if file.modified_at else None,
        "category": cls.category if cls else None,
        "tag": cls.tag if cls else None,
        "tier_used": cls.tier_used if cls else None,
        "confidence_score": cls.confidence_score if cls else 0.0,
        "is_manual": cls.is_manual if cls else False,
    }


@router.get("")
async def list_files(
    scan_id: str = Query(...),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    unclassified: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """UC-03: 분류 결과 목록 조회 (페이지네이션 + 필터)"""

    # 해당 scan_id의 분류 결과 서브쿼리
    # 수동 분류 우선, 없으면 최신 자동 분류 사용
    from sqlalchemy import func, case

    # 파일별 최신 분류 결과 조회 (수동 > 자동 우선순위)
    subq = (
        db.query(
            Classification.file_id,
            func.max(
                case((Classification.is_manual == True, 2), else_=1)
            ).label("priority"),
        )
        .filter(Classification.scan_id == scan_id)
        .group_by(Classification.file_id)
        .subquery()
    )

    query = (
        db.query(File, Classification)
        .join(
            Classification,
            (Classification.file_id == File.id) & (Classification.scan_id == scan_id),
        )
        .join(
            subq,
            (subq.c.file_id == File.id) &
            (case((Classification.is_manual == True, 2), else_=1) == subq.c.priority),
        )
    )

    # 필터 적용
    if category:
        query = query.filter(Classification.category == category)
    if tag:
        query = query.filter(Classification.tag == tag)
    if min_confidence is not None:
        query = query.filter(Classification.confidence_score >= min_confidence)
    if unclassified:
        query = query.filter(Classification.confidence_score < 0.31)
    if search:
        query = query.filter(File.filename.ilike(f"%{search}%"))

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [_build_file_item(file, cls) for file, cls in rows]

    return JSONResponse(content=ok({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }))


@router.patch("/{file_id}")
async def patch_file(
    file_id: int,
    body: PatchFileRequest,
    db: Session = Depends(get_db),
):
    """UC-04: 수동 분류 수정"""
    result = update_manual_classification(
        db=db,
        file_id=file_id,
        category=body.category,
        tag=body.tag,
    )
    return JSONResponse(content=ok(result))


@router.get("/{file_id}/similar")
async def get_similar_files(
    file_id: int,
    db: Session = Depends(get_db),
):
    """표지 유사 파일 목록 조회"""
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise_error(ErrorCode.FILE_NOT_FOUND)

    # 해당 파일의 유사도 그룹 조회
    my_group = (
        db.query(CoverSimilarityGroup)
        .filter(CoverSimilarityGroup.file_id == file_id)
        .first()
    )
    if not my_group:
        raise_error(ErrorCode.NO_COVER_DATA)

    # 같은 그룹의 다른 파일 조회
    group_members = (
        db.query(CoverSimilarityGroup, File)
        .join(File, File.id == CoverSimilarityGroup.file_id)
        .filter(
            CoverSimilarityGroup.group_id == my_group.group_id,
            CoverSimilarityGroup.file_id != file_id,
        )
        .all()
    )

    similar_files = [
        {
            "id": f.id,
            "filename": f.filename,
            "similarity_score": g.similarity_score,
            "auto_tag": g.auto_tag,
        }
        for g, f in group_members
    ]

    return JSONResponse(content=ok({
        "file_id": file_id,
        "similar_files": similar_files,
    }))
