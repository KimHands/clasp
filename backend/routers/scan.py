import os
import json
import time
import uuid
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

# TTL 기반 메모리 정리 (5분 초과 시 자동 제거)
_SCAN_TTL_SECONDS = 300


def _cleanup_stale_scans():
    """TTL 초과 스캔 항목 정리"""
    now = time.time()
    stale = [sid for sid, info in _active_scans.items()
             if now - info.get("created_at", 0) > _SCAN_TTL_SECONDS]
    for sid in stale:
        _active_scans.pop(sid, None)


# Path Traversal 방지: 사용자 홈 디렉토리 하위만 허용
_ALLOWED_ROOTS = [os.path.expanduser("~")]


def _validate_folder_path(folder_path: str) -> str | None:
    """
    경로를 정규화하고 허용 범위 내인지 검증.
    유효하면 정규화된 경로 반환, 아니면 None.
    """
    real = os.path.realpath(os.path.expanduser(folder_path))
    for root in _ALLOWED_ROOTS:
        if real.startswith(os.path.realpath(root) + os.sep) or real == os.path.realpath(root):
            return real
    return None


class ScanStartRequest(BaseModel):
    folder_path: str


@router.post("/start")
async def start_scan(body: ScanStartRequest):
    """UC-02: 스캔 시작"""
    folder_path = _validate_folder_path(body.folder_path)

    if folder_path is None:
        return JSONResponse(
            status_code=403,
            content=fail(ErrorCode.PERMISSION_DENIED, "허용되지 않은 경로입니다"),
        )

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

    _cleanup_stale_scans()

    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    _active_scans[scan_id] = {
        "folder_path": folder_path,
        "status": "started",
        "created_at": time.time(),
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
