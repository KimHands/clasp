from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from utils.response import ok
from utils.errors import ErrorCode, raise_error
from services.action_service import (
    build_preview,
    apply_organize,
    undo_organize,
    get_folder_history,
)

router = APIRouter(tags=["apply"])

VALID_RESOLUTIONS = {"overwrite", "rename", "skip"}


class ApplyRequest(BaseModel):
    scan_id: str
    conflict_resolution: str
    folder_path: str


class UndoRequest(BaseModel):
    action_log_id: str


@router.get("/apply/preview")
async def preview(scan_id: str = Query(...), db: Session = Depends(get_db)):
    """UC-06: 정리 적용 미리보기"""
    result = build_preview(db, scan_id)
    return JSONResponse(content=ok(result))


@router.post("/apply")
async def apply(body: ApplyRequest, db: Session = Depends(get_db)):
    """UC-06: 정리 적용 실행"""
    if body.conflict_resolution not in VALID_RESOLUTIONS:
        raise_error(
            ErrorCode.INVALID_TYPE,
            f"conflict_resolution은 overwrite/rename/skip 중 하나여야 합니다",
        )
    result = apply_organize(
        db,
        body.scan_id,
        body.conflict_resolution,
        body.folder_path,
    )
    return JSONResponse(content=ok(result))


@router.post("/undo")
async def undo(body: UndoRequest, db: Session = Depends(get_db)):
    """UC-07: 되돌리기"""
    result = undo_organize(db, body.action_log_id)
    return JSONResponse(content=ok(result))


@router.get("/apply/history")
async def history(
    folder_path: str = Query(...),
    db: Session = Depends(get_db),
):
    """폴더별 정리 적용 이력 조회"""
    result = get_folder_history(db, folder_path)
    return JSONResponse(content=ok(result))
