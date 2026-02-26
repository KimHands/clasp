import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel

from database import init_db
from routers import scan, files, rules, apply, settings
from utils.response import ok


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 DB 테이블 생성
    init_db()
    yield


app = FastAPI(
    title="Clasp API",
    description="파일 정리 및 시각화 도구 백엔드",
    version="1.0.0",
    lifespan=lifespan,
)

# Electron 렌더러 프로세스에서의 요청 허용
# file:// 는 프로덕션 Electron 빌드에서 필요, localhost는 개발 환경용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "app://."],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(scan.router)
app.include_router(files.router)
app.include_router(rules.router)
app.include_router(apply.router)
app.include_router(settings.router)


class ApiKeyRequest(BaseModel):
    api_key: str


@app.post("/settings/api-key")
async def set_api_key(body: ApiKeyRequest):
    """Electron 메인 프로세스에서 OpenAI API Key를 런타임에 설정"""
    key = body.api_key.strip()
    if key:
        os.environ["OPENAI_API_KEY"] = key
    else:
        os.environ.pop("OPENAI_API_KEY", None)
    return JSONResponse(content=ok({"configured": bool(key)}))


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "clasp-backend"}
