import os
import tempfile

# database.py creates the app data directory at import time, so HOME must be
# replaced before any project module is imported.
os.environ["HOME"] = os.environ["USERPROFILE"] = tempfile.mkdtemp(prefix="clasp-test-home-")

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
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
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

    os.environ["CLASP_API_TOKEN"] = "test-token"
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, base_url="http://127.0.0.1", headers={"X-Clasp-Token": "test-token"})
    app.dependency_overrides.clear()


@pytest.fixture
def fake_llm():
    """루프백에 뜨는 OpenAI 호환 가짜 서버. 받은 요청을 기록하고 지정한 응답을 돌려준다"""
    import json as json_module
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class State:
        requests = []
        answer = {"category": "문서", "tag": None, "confidence_score": 0.6}
        status = 200
        location = None
        raw_content = None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(200, {"data": [{"id": "fake-model"}]})

        def do_POST(self):
            body = json_module.loads(self.rfile.read(int(self.headers["Content-Length"])))
            State.requests.append(body)
            content = State.raw_content or json_module.dumps(State.answer, ensure_ascii=False)
            self._send(State.status, {"choices": [{"message": {"role": "assistant", "content": content}}]})

        def _send(self, status, payload):
            data = json_module.dumps(payload).encode()
            self.send_response(status)
            if State.location:
                self.send_header("Location", State.location)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    State.requests = []
    State.base_url = f"http://127.0.0.1:{server.server_port}/v1"
    yield State
    server.shutdown()
    server.server_close()


@pytest.fixture
def external_connections(monkeypatch):
    """루프백이 아닌 연결 시도와 이름 조회를 기록하고 막는다"""
    import ipaddress
    import socket

    attempts = []
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def is_loopback(host):
        if host in ("localhost", None):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not is_loopback(address[0]):
            attempts.append(address[0])
            raise OSError("external connection blocked by test")
        return real_connect(self, address)

    def getaddrinfo(host, *args, **kwargs):
        host_text = host.decode() if isinstance(host, bytes) else host
        if not is_loopback(host_text):
            attempts.append(host_text)
            raise socket.gaierror("external lookup blocked by test")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return attempts


@pytest.fixture
def stub_embeddings(monkeypatch):
    """임베딩 모델을 불러오지 않는다. 낮은 점수를 돌려줘 Tier 3까지 진행하게 한다"""
    import json as json_module

    from engines import tier2_embedding
    from services import cover_service

    monkeypatch.setattr(tier2_embedding, "load_custom_categories", lambda categories: None)
    monkeypatch.setattr(tier2_embedding, "apply_feedback", lambda text, category: None)
    monkeypatch.setattr(
        tier2_embedding,
        "run",
        lambda text: {"category": None, "tag": None, "confidence_score": 0.2, "embedding": None},
    )
    monkeypatch.setattr("engines.pipeline.infer_tag", lambda text, category: None)
    monkeypatch.setattr(cover_service, "compute_embedding", lambda text: json_module.dumps([1.0, 0.0]))
    monkeypatch.setattr(cover_service, "infer_tag", lambda text, category: None)
