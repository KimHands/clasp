from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from routers import scan, files, rules, apply, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Clasp API",
    description="파일 정리 및 시각화 도구 백엔드",
    version="1.0.0",
    lifespan=lifespan,
)

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "clasp-backend"}
