import os
import tempfile

# database.py creates the app data directory at import time, so HOME must be
# replaced before any project module is imported.
os.environ["HOME"] = tempfile.mkdtemp(prefix="clasp-test-home-")

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.schema import Base, Classification, File


def write(path, text) -> str:
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def read(path) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def add_scanned(db, path, scan_id="scan_t", category="문서", confidence=0.7) -> File:
    """스캔이 남기는 File·Classification 행을 직접 만든다"""
    path = str(path)
    size = modified_at = None
    if os.path.lexists(path):
        stat = os.lstat(path)
        size = stat.st_size
        modified_at = datetime.fromtimestamp(stat.st_mtime)
    file = File(
        path=path,
        filename=os.path.basename(path),
        extension=os.path.splitext(path)[1],
        size=size,
        modified_at=modified_at,
    )
    db.add(file)
    db.commit()
    db.add(Classification(
        file_id=file.id,
        scan_id=scan_id,
        category=category,
        tag=None,
        tier_used=1,
        confidence_score=confidence,
        is_manual=False,
    ))
    db.commit()
    return file


@pytest.fixture
def home(tmp_path, monkeypatch) -> str:
    monkeypatch.setenv("HOME", str(tmp_path))
    return os.path.realpath(tmp_path)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from database import get_db
    from main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
