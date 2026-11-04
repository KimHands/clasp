import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token"


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("CLASP_API_TOKEN", TOKEN)
    from main import app

    return TestClient(app, base_url="http://127.0.0.1")


def _auth(extra=None):
    return {"X-Clasp-Token": TOKEN, **(extra or {})}


def test_valid_token_is_accepted(app_client):
    response = app_client.get("/health", headers=_auth())
    assert response.status_code == 200
    assert response.json()["service"] == "clasp-backend"


def test_missing_token_is_rejected(app_client):
    assert app_client.get("/health").status_code == 401


def test_wrong_token_is_rejected(app_client):
    assert app_client.get("/health", headers={"X-Clasp-Token": "wrong"}).status_code == 401


def test_unset_token_rejects_everything(app_client, monkeypatch):
    monkeypatch.delenv("CLASP_API_TOKEN")
    assert app_client.get("/health", headers=_auth()).status_code == 401
    assert app_client.get("/health", headers={"X-Clasp-Token": ""}).status_code == 401


def test_forged_host_is_rejected(app_client):
    response = app_client.get("/health", headers=_auth({"Host": "evil.example"}))
    assert response.status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1:9000", "localhost:9000", "[::1]:9000", "localhost"])
def test_loopback_hosts_are_accepted(app_client, host):
    assert app_client.get("/health", headers=_auth({"Host": host})).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_disabled(app_client, path):
    assert app_client.get(path, headers=_auth()).status_code == 404


def test_foreign_origin_gets_no_cors_header(app_client):
    response = app_client.get("/health", headers=_auth({"Origin": "https://evil.example"}))
    assert "access-control-allow-origin" not in response.headers


def test_foreign_preflight_is_refused(app_client):
    response = app_client.options("/scan/start", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-clasp-token,content-type",
    })
    assert "access-control-allow-origin" not in response.headers


def test_renderer_preflight_with_token_header_is_allowed(app_client):
    response = app_client.options("/scan/start", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-clasp-token",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
