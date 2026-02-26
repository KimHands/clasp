from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[dict] = None


def ok(data: Any = None) -> dict:
    """성공 응답 래퍼"""
    return {"success": True, "data": data, "error": None}


def fail(code: str, message: str) -> dict:
    """에러 응답 래퍼"""
    return {"success": False, "data": None, "error": {"code": code, "message": message}}
