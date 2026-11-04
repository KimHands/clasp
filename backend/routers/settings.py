import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.schema import AppSetting, CustomExtension, CustomCategory, SensitiveKeyword
from engines.tier1_rule import _EXT_CATEGORY_MAP
from engines import tier3_llm
from utils.response import ok
from utils.errors import ErrorCode, raise_error

router = APIRouter(prefix="/settings", tags=["settings"])


class LocalLlmRequest(BaseModel):
    enabled: bool
    base_url: str
    model: str


class LocalLlmTestRequest(BaseModel):
    base_url: str


class SensitiveKeywordRequest(BaseModel):
    keyword: str


class CreateExtensionRequest(BaseModel):
    extension: str
    category: str


class CreateCategoryRequest(BaseModel):
    name: str
    keywords: list[str] = []


# 기본 제공 확장자 카테고리 목록 (드롭다운 표시용)
DEFAULT_CATEGORIES = sorted(set(_EXT_CATEGORY_MAP.values()))


def _validated_llm_url(base_url: str) -> str:
    try:
        return tier3_llm.validate_local_base_url(base_url.strip())
    except ValueError as e:
        raise_error(ErrorCode.INVALID_TYPE, str(e))


@router.get("/local-llm")
async def get_local_llm(db: Session = Depends(get_db)):
    """로컬 LLM 설정 조회"""
    config = tier3_llm.load_config(db)
    return JSONResponse(content=ok({
        "enabled": config.enabled,
        "base_url": config.base_url,
        "model": config.model,
    }))


@router.post("/local-llm")
async def save_local_llm(body: LocalLlmRequest, db: Session = Depends(get_db)):
    """로컬 LLM 설정 저장. 이 컴퓨터를 가리키는 주소만 허용"""
    base_url = _validated_llm_url(body.base_url)
    model = body.model.strip()
    if body.enabled and not model:
        raise_error(ErrorCode.INVALID_TYPE, "모델을 선택해주세요")
    values = {
        "local_llm_enabled": "1" if body.enabled else "0",
        "local_llm_base_url": base_url,
        "local_llm_model": model,
    }
    for key, value in values.items():
        db.merge(AppSetting(key=key, value=value))
    db.commit()
    return JSONResponse(content=ok({"enabled": body.enabled, "base_url": base_url, "model": model}))


@router.post("/local-llm/test")
async def test_local_llm(body: LocalLlmTestRequest):
    """로컬 LLM 연결 시험. 사용 가능한 모델 목록을 반환"""
    base_url = _validated_llm_url(body.base_url)
    models = await tier3_llm.list_models(base_url)
    return JSONResponse(content=ok({"ok": models is not None, "models": models or []}))


@router.get("/sensitive-keywords")
async def list_sensitive_keywords(db: Session = Depends(get_db)):
    """민감 파일 키워드 조회"""
    rows = db.query(SensitiveKeyword).order_by(SensitiveKeyword.id).all()
    return JSONResponse(content=ok({"keywords": [{"id": r.id, "keyword": r.keyword} for r in rows]}))


@router.post("/sensitive-keywords")
async def create_sensitive_keyword(body: SensitiveKeywordRequest, db: Session = Depends(get_db)):
    """민감 파일 키워드 추가"""
    keyword = body.keyword.strip()
    if not keyword:
        raise_error(ErrorCode.INVALID_TYPE, "키워드를 입력해주세요")
    if db.query(SensitiveKeyword).filter(SensitiveKeyword.keyword == keyword).first():
        raise_error(ErrorCode.CATEGORY_CONFLICT, f"'{keyword}'는 이미 등록된 키워드입니다")
    row = SensitiveKeyword(keyword=keyword)
    db.add(row)
    db.commit()
    return JSONResponse(content=ok({"id": row.id, "keyword": row.keyword}))


@router.delete("/sensitive-keywords/{keyword_id}")
async def delete_sensitive_keyword(keyword_id: int, db: Session = Depends(get_db)):
    """민감 파일 키워드 삭제"""
    db.query(SensitiveKeyword).filter(SensitiveKeyword.id == keyword_id).delete()
    db.commit()
    return JSONResponse(content=ok({"deleted_id": keyword_id}))


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
