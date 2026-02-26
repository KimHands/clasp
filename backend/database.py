import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.schema import Base

# DB 파일은 앱 데이터 디렉토리에 저장
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "clasp.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """모든 테이블 생성 (최초 실행 시)"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI Depends용 DB 세션 제공"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
