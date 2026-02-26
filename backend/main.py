from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "app://.", "file://"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "clasp-backend"}
