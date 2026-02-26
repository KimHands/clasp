import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.schema import CustomExtension
from engines.tier1_rule import _EXT_CATEGORY_MAP
from utils.response import ok
from utils.errors import ErrorCode, raise_error

router = APIRouter(prefix="/settings", tags=["settings"])


class ApiKeyRequest(BaseModel):
    api_key: str


class CreateExtensionRequest(BaseModel):
    extension: str
    category: str


# 기본 제공 확장자 카테고리 목록 (드롭다운 표시용)
DEFAULT_CATEGORIES = sorted(set(_EXT_CATEGORY_MAP.values()))


@router.post("/api-key")
async def set_api_key(body: ApiKeyRequest):
    """Electron 메인 프로세스에서 OpenAI API Key를 런타임에 설정"""
    key = body.api_key.strip()
    if key:
        os.environ["OPENAI_API_KEY"] = key
    else:
        os.environ.pop("OPENAI_API_KEY", None)
    return JSONResponse(content=ok({"configured": bool(key)}))


@router.get("/extensions")
async def list_extensions(db: Session = Depends(get_db)):
    """기본 확장자 매핑 + 사용자 커스텀 확장자 통합 조회"""
    custom_rows = db.query(CustomExtension).all()
    custom_list = [
        {"id": row.id, "extension": row.extension, "category": row.category, "is_default": False}
        for row in custom_rows
    ]

    default_list = [
        {"id": None, "extension": ext, "category": cat, "is_default": True}
        for ext, cat in _EXT_CATEGORY_MAP.items()
    ]

    return JSONResponse(content=ok({
        "extensions": default_list + custom_list,
        "categories": DEFAULT_CATEGORIES,
    }))


@router.post("/extensions")
async def create_extension(body: CreateExtensionRequest, db: Session = Depends(get_db)):
    """사용자 커스텀 확장자 추가"""
    ext = body.extension.strip().lstrip(".").lower()
    cat = body.category.strip()

    if not ext or not cat:
        raise_error(ErrorCode.INVALID_TYPE, "확장자와 카테고리를 모두 입력해주세요")

    # 기본 매핑과 중복 확인
    if ext in _EXT_CATEGORY_MAP:
        raise_error(ErrorCode.EXTENSION_CONFLICT, f"'{ext}'는 기본 확장자에 이미 포함되어 있습니다")

    existing = db.query(CustomExtension).filter(CustomExtension.extension == ext).first()
    if existing:
        raise_error(ErrorCode.EXTENSION_CONFLICT, f"'{ext}'는 이미 등록된 커스텀 확장자입니다")

    row = CustomExtension(extension=ext, category=cat)
    db.add(row)
    db.commit()
    db.refresh(row)

    return JSONResponse(content=ok({
        "id": row.id, "extension": row.extension, "category": row.category, "is_default": False,
    }))


@router.delete("/extensions/{ext_id}")
async def delete_extension(ext_id: int, db: Session = Depends(get_db)):
    """사용자 커스텀 확장자 삭제 (기본 확장자는 삭제 불가)"""
    row = db.query(CustomExtension).filter(CustomExtension.id == ext_id).first()
    if not row:
        raise_error(ErrorCode.EXTENSION_NOT_FOUND)

    db.delete(row)
    db.commit()
    return JSONResponse(content=ok({"deleted_id": ext_id}))
