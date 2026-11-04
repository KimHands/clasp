import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import SessionLocal, init_db
from routers import scan, files, rules, apply, settings
from services.move_recovery import reconcile_pending
from utils.local_access import LocalAccessMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        remaining = reconcile_pending(db)
        if remaining:
            logger.warning("조정하지 못한 파일 이동 %d건", remaining)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Clasp API",
    description="파일 정리 및 시각화 도구 백엔드",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Added first so it runs inside CORS: browsers send preflight requests without the token
app.add_middleware(LocalAccessMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CLASP_ALLOWED_ORIGIN", "http://localhost:5173")],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Accept", "X-Clasp-Token"],
)

app.include_router(scan.router)
app.include_router(files.router)
app.include_router(rules.router)
app.include_router(apply.router)
app.include_router(settings.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "clasp-backend"}
