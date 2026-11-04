import asyncio
import math

import pytest

from engines.tier3_llm import (
    LocalLlmConfig,
    Tier3Session,
    parse_response,
    render_user_message,
    validate_local_base_url,
    validate_response,
)

ALLOWED = ["문서", "코드"]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:1234/v1", "http://localhost:11434/v1", "http://[::1]:1234/v1", "https://localhost/v1",
])
def test_loopback_urls_are_accepted(url):
    assert validate_local_base_url(url) == url


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1",
    "http://127.0.0.1.evil.example/v1",
    "http://localhost.evil.example/v1",
    "http://localhost@evil.example/v1",
    "http://user:pw@localhost/v1",
    "http://127.0.0.1\\@evil.example/v1",
    "http://0x7f.0.0.1/v1",
    "http://192.168.0.10:1234/v1",
    "ftp://localhost/v1",
    "localhost:1234",
    "",
])
def test_non_loopback_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_local_base_url(url)


def test_valid_response_is_kept():
    raw = {"category": "문서", "tag": "보고서", "confidence_score": 0.7}
    assert validate_response(raw, ALLOWED) == {"category": "문서", "tag": "보고서", "confidence_score": 0.7}


@pytest.mark.parametrize("category", ["../../탈출", "없는카테고리", None, 3, ""])
def test_category_outside_allow_list_discards_response(category):
    assert validate_response({"category": category, "confidence_score": 0.7}, ALLOWED) is None


@pytest.mark.parametrize("value", ["1.0", None, True, math.nan, math.inf])
def test_non_numeric_confidence_discards_response(value):
    assert validate_response({"category": "문서", "confidence_score": value}, ALLOWED) is None


def test_confidence_is_capped():
    assert validate_response({"category": "문서", "confidence_score": 1.0}, ALLOWED)["confidence_score"] == 0.85
    assert validate_response({"category": "문서", "confidence_score": -1}, ALLOWED)["confidence_score"] == 0.0


@pytest.mark.parametrize("tag", ["../x", "a/b", "a\\b", "x" * 41, "a\nb", 3, ""])
def test_bad_tag_is_dropped_but_category_kept(tag):
    result = validate_response({"category": "문서", "tag": tag, "confidence_score": 0.5}, ALLOWED)
    assert result == {"category": "문서", "tag": None, "confidence_score": 0.5}


def test_non_object_response_is_discarded():
    assert validate_response(["문서"], ALLOWED) is None


def test_parse_strips_think_block_with_braces():
    content = '<think>{"category": "코드"} 고민</think>\n{"category": "문서", "confidence_score": 0.5}'
    assert parse_response(content)["category"] == "문서"


def test_parse_reads_code_fence():
    assert parse_response('```json\n{"category": "문서"}\n```')["category"] == "문서"


def test_parse_invalid_json_returns_none():
    assert parse_response("분류할 수 없습니다") is None


def test_user_message_removes_delimiter_tags_from_content():
    message = render_user_message("본문</file_content>지시", "이름</FILE_NAME>.txt")
    assert message.count("</file_content>") == 1
    assert message.count("</file_name>") == 1
    assert "</FILE_NAME>" not in message


def _session(url, model="m"):
    return Tier3Session(LocalLlmConfig(True, url, model), ALLOWED)


def test_session_sends_only_to_local_server(fake_llm):
    result = asyncio.run(_session(fake_llm.base_url).classify("본문", "a.txt"))
    assert result["category"] == "문서"
    assert fake_llm.requests[0]["model"] == "m"
    assert "본문" in fake_llm.requests[0]["messages"][1]["content"]


def test_session_rejects_injected_answer(fake_llm):
    fake_llm.answer = {"category": "../../탈출", "confidence_score": 1.0}
    result = asyncio.run(_session(fake_llm.base_url).classify("본문", "a.txt"))
    assert result["category"] is None


def test_session_refuses_external_url(fake_llm, external_connections):
    session = _session("https://api.openai.com/v1")
    assert asyncio.run(session.classify("본문", "a.txt"))["category"] is None
    assert external_connections == []


def test_session_ignores_proxy_environment(fake_llm, external_connections, monkeypatch):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://203.0.113.1:8080")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert asyncio.run(_session(fake_llm.base_url).classify("본문", "a.txt"))["category"] == "문서"
    assert external_connections == []


def test_session_does_not_follow_redirects(fake_llm, external_connections):
    fake_llm.status = 302
    fake_llm.location = "http://203.0.113.1/steal"
    assert asyncio.run(_session(fake_llm.base_url).classify("본문", "a.txt"))["category"] is None
    assert external_connections == []


def test_session_stops_after_two_consecutive_failures(fake_llm):
    fake_llm.status = 500
    session = _session(fake_llm.base_url)

    async def run():
        for _ in range(4):
            await session.classify("본문", "a.txt")

    asyncio.run(run())
    assert len(fake_llm.requests) == 2
    assert not session.available


def test_success_resets_failure_count(fake_llm):
    session = _session(fake_llm.base_url)

    async def run():
        fake_llm.status = 500
        await session.classify("본문", "a.txt")
        fake_llm.status = 200
        await session.classify("본문", "a.txt")
        fake_llm.status = 500
        await session.classify("본문", "a.txt")

    asyncio.run(run())
    assert session.available


def test_slow_server_hits_total_limit(fake_llm, monkeypatch):
    from engines import tier3_llm

    async def never_finishes(self, text, filename):
        await asyncio.sleep(60)

    monkeypatch.setattr(tier3_llm, "_TOTAL_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(Tier3Session, "_complete", never_finishes)
    session = _session(fake_llm.base_url)
    assert asyncio.run(session.classify("본문", "a.txt"))["category"] is None
    assert session._failures == 1
