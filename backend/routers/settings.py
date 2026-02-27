import json
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.schema import CustomExtension, CustomCategory
from engines.tier1_rule import _EXT_CATEGORY_MAP
from engines import tier3_llm
from utils.response import ok
from utils.errors import ErrorCode, raise_error

router = APIRouter(prefix="/settings", tags=["settings"])


class ApiKeyRequest(BaseModel):
    api_key: str


class GeminiApiKeyRequest(BaseModel):
    api_key: str


class CreateExtensionRequest(BaseModel):
    extension: str
    category: str


class CreateCategoryRequest(BaseModel):
    name: str
    keywords: list[str] = []


# 기본 제공 확장자 카테고리 목록 (드롭다운 표시용)
DEFAULT_CATEGORIES = sorted(set(_EXT_CATEGORY_MAP.values()))


@router.get("/llm-status")
async def get_llm_status():
    """현재 백엔드에 등록된 LLM API 키 상태 확인"""
    return JSONResponse(content=ok({
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "active_provider": tier3_llm.get_active_provider(),
    }))


@router.post("/api-key")
async def set_api_key(body: ApiKeyRequest):
    """Electron 메인 프로세스에서 OpenAI API Key를 런타임에 설정"""
    key = body.api_key.strip()
    if key:
        os.environ["OPENAI_API_KEY"] = key
    else:
        os.environ.pop("OPENAI_API_KEY", None)
    return JSONResponse(content=ok({"configured": bool(key)}))


@router.post("/gemini-api-key")
async def set_gemini_api_key(body: GeminiApiKeyRequest):
    """Electron 메인 프로세스에서 Gemini API Key를 런타임에 설정"""
    key = body.api_key.strip()
    if key:
        os.environ["GEMINI_API_KEY"] = key
    else:
        os.environ.pop("GEMINI_API_KEY", None)
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


@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    """기본 카테고리 + 사용자 커스텀 카테고리 통합 조회"""
    custom_rows = db.query(CustomCategory).all()
    custom_list = [
        {
            "id": row.id,
            "name": row.name,
            "keywords": json.loads(row.keywords),
            "is_default": False,
        }
        for row in custom_rows
    ]

    default_list = [
        {"id": None, "name": cat, "keywords": [], "is_default": True}
        for cat in DEFAULT_CATEGORIES
    ]

    return JSONResponse(content=ok({"categories": default_list + custom_list}))


@router.post("/categories")
async def create_category(body: CreateCategoryRequest, db: Session = Depends(get_db)):
    """사용자 커스텀 카테고리 추가"""
    name = body.name.strip()
    if not name:
        raise_error(ErrorCode.INVALID_TYPE, "카테고리 이름을 입력해주세요")

    if name in DEFAULT_CATEGORIES:
        raise_error(ErrorCode.CATEGORY_CONFLICT, f"'{name}'는 기본 카테고리에 이미 포함되어 있습니다")

    existing = db.query(CustomCategory).filter(CustomCategory.name == name).first()
    if existing:
        raise_error(ErrorCode.CATEGORY_CONFLICT, f"'{name}'는 이미 등록된 커스텀 카테고리입니다")

    keywords = [kw.strip() for kw in body.keywords if kw.strip()]
    row = CustomCategory(name=name, keywords=json.dumps(keywords, ensure_ascii=False))
    db.add(row)
    db.commit()
    db.refresh(row)

    return JSONResponse(content=ok({
        "id": row.id,
        "name": row.name,
        "keywords": json.loads(row.keywords),
        "is_default": False,
    }))


@router.delete("/categories/{cat_id}")
async def delete_category(cat_id: int, db: Session = Depends(get_db)):
    """사용자 커스텀 카테고리 삭제 (기본 카테고리는 삭제 불가)"""
    row = db.query(CustomCategory).filter(CustomCategory.id == cat_id).first()
    if not row:
        raise_error(ErrorCode.CATEGORY_NOT_FOUND)

    db.delete(row)
    db.commit()
    return JSONResponse(content=ok({"deleted_id": cat_id}))
