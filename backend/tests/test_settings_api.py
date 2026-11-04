def test_old_key_endpoints_are_removed(client):
    assert client.post("/settings/api-key", json={"api_key": "x"}).status_code == 404
    assert client.post("/settings/gemini-api-key", json={"api_key": "x"}).status_code == 404
    assert client.get("/settings/llm-status").status_code == 404


def test_local_llm_defaults_to_off(client):
    data = client.get("/settings/local-llm").json()["data"]
    assert data["enabled"] is False
    assert data["base_url"] == "http://127.0.0.1:1234/v1"


def test_local_llm_is_saved(client):
    body = {"enabled": True, "base_url": "http://localhost:11434/v1", "model": "m"}
    assert client.post("/settings/local-llm", json=body).status_code == 200
    assert client.get("/settings/local-llm").json()["data"] == body


def test_external_llm_url_is_refused(client):
    body = {"enabled": True, "base_url": "https://api.openai.com/v1", "model": "m"}
    assert client.post("/settings/local-llm", json=body).status_code == 400
    assert client.get("/settings/local-llm").json()["data"]["enabled"] is False


def test_enabling_requires_model(client):
    body = {"enabled": True, "base_url": "http://localhost:1234/v1", "model": ""}
    assert client.post("/settings/local-llm", json=body).status_code == 400


def test_connection_test_lists_models(client, fake_llm):
    response = client.post("/settings/local-llm/test", json={"base_url": fake_llm.base_url})
    assert response.json()["data"] == {"ok": True, "models": ["fake-model"]}


def test_connection_test_refuses_external_url(client, external_connections):
    response = client.post("/settings/local-llm/test", json={"base_url": "https://api.openai.com/v1"})
    assert response.status_code == 400
    assert external_connections == []


def test_connection_failure_is_reported(client):
    response = client.post("/settings/local-llm/test", json={"base_url": "http://127.0.0.1:9/v1"})
    assert response.json()["data"] == {"ok": False, "models": []}


def test_sensitive_keyword_crud(client):
    created = client.post("/settings/sensitive-keywords", json={"keyword": " 급여 "}).json()["data"]
    assert created["keyword"] == "급여"
    assert client.post("/settings/sensitive-keywords", json={"keyword": "급여"}).status_code == 409
    assert client.post("/settings/sensitive-keywords", json={"keyword": " "}).status_code == 400
    listed = client.get("/settings/sensitive-keywords").json()["data"]["keywords"]
    assert listed == [created]
    assert client.delete(f"/settings/sensitive-keywords/{created['id']}").status_code == 200
    assert client.get("/settings/sensitive-keywords").json()["data"]["keywords"] == []
