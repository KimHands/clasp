import os
import json
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from utils.response import ok, fail
from utils.errors import ErrorCode
from services import scan_service

router = APIRouter(prefix="/scan", tags=["scan"])

# 진행 중인 스캔 상태 저장 (메모리)
_active_scans: dict[str, dict] = {}


class ScanStartRequest(BaseModel):
    folder_path: str


@router.post("/start")
async def start_scan(body: ScanStartRequest):
    """UC-02: 스캔 시작"""
    folder_path = body.folder_path

    if not os.path.exists(folder_path):
        return JSONResponse(
            status_code=404,
            content=fail(ErrorCode.FOLDER_NOT_FOUND, "폴더 경로가 존재하지 않음"),
        )

    if not os.access(folder_path, os.R_OK):
        return JSONResponse(
            status_code=403,
            content=fail(ErrorCode.PERMISSION_DENIED, "폴더 접근 권한 없음"),
        )

    # 스캔 ID 생성
    scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _active_scans[scan_id] = {
        "folder_path": folder_path,
        "status": "started",
    }

    return JSONResponse(
        content=ok({
            "scan_id": scan_id,
            "status": "started",
            "folder_path": folder_path,
        })
    )


@router.get("/progress")
async def scan_progress(scan_id: str):
    """UC-02: SSE 스캔 진행 상황 스트리밍"""
    if scan_id not in _active_scans:
        return JSONResponse(
            status_code=404,
            content=fail(ErrorCode.SCAN_NOT_FOUND, "해당 스캔 ID 없음"),
        )

    folder_path = _active_scans[scan_id]["folder_path"]

    async def event_generator():
        async for progress in scan_service.run_scan(scan_id, folder_path):
            yield {"data": json.dumps(progress, ensure_ascii=False)}
        # 스캔 완료 후 메모리에서 제거
        _active_scans.pop(scan_id, None)

    return EventSourceResponse(event_generator())
