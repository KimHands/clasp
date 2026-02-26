import os
import sys
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from models.schema import Base


def _get_db_dir() -> str:
    """
    OS별 앱 데이터 디렉토리 반환.
    PyInstaller 번들에서도 안정적으로 동작하도록
    사용자 홈 기반 경로 사용.
    """
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Clasp")
    elif sys.platform == "win32":
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Clasp")
    else:
        base = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "Clasp")
    return base


DB_DIR = _get_db_dir()
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "clasp.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


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
