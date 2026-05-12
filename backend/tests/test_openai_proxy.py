"""Tests for POST /v1/proxy/openai/chat/completions."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.models.request_log import RequestLog


@pytest.fixture
def with_openai_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-openai-test-key")


@pytest.fixture
def mock_openai_ok():
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = {
        "id": "chatcmpl-abc123",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": "Bonjour!"}}],
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
    }
    with patch("app.services.provider.httpx.post", return_value=resp) as mock:
        yield mock


_SAFE: dict[str, Any] = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Say hi in French."}],
}


def _msg(content: str) -> dict[str, Any]:
    return {**_SAFE, "messages": [{"role": "user", "content": content}]}


# ── Model allowlist ────────────────────────────────────────────────────────


def test_gpt4o_allowed(client, mock_db, mock_openai_ok, with_openai_key):
    resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    assert resp.status_code == 200


def test_gpt4o_mini_allowed(client, mock_db, mock_openai_ok, with_openai_key):
    resp = client.post("/v1/proxy/openai/chat/completions", json={**_SAFE, "model": "gpt-4o-mini"})
    assert resp.status_code == 200


def test_claude_model_blocked_on_openai_endpoint(client, mock_db):
    resp = client.post(
        "/v1/proxy/openai/chat/completions",
        json={**_SAFE, "model": "claude-3-5-sonnet-latest"},
    )
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["type"] == "policy_violation"
    assert err["policy"] == "model_allowlist"


def test_unknown_model_blocked_on_openai_endpoint(client, mock_db):
    resp = client.post(
        "/v1/proxy/openai/chat/completions",
        json={**_SAFE, "model": "gemini-pro"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["policy"] == "model_allowlist"


# ── Shared policy checks work on OpenAI endpoint ──────────────────────────


def test_secret_blocked_on_openai_endpoint(client, mock_db):
    resp = client.post(
        "/v1/proxy/openai/chat/completions",
        json=_msg("key=AKIAIOSFODNN7EXAMPLE"),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["policy"] == "secret_detection"


def test_pii_blocked_on_openai_endpoint(client, mock_db):
    resp = client.post(
        "/v1/proxy/openai/chat/completions",
        json=_msg("My SSN is 123-45-6789"),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["policy"] == "pii_detection"


# ── Forwarding ─────────────────────────────────────────────────────────────


def test_request_forwarded_to_openai(client, mock_db, mock_openai_ok, with_openai_key):
    resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    assert resp.status_code == 200
    mock_openai_ok.assert_called_once()
    _, kwargs = mock_openai_ok.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer sk-openai-test-key"


def test_openai_response_returned_verbatim(client, mock_db, mock_openai_ok, with_openai_key):
    resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Bonjour!"


# ── Logging: provider and token fields ────────────────────────────────────


def test_openai_request_logged_with_provider(client, mock_db, mock_openai_ok, with_openai_key):
    client.post("/v1/proxy/openai/chat/completions", json=_SAFE)

    log: RequestLog = mock_db.add.call_args[0][0]
    assert log.provider == "openai"
    assert log.model == "gpt-4o"
    assert log.upstream_status_code == 200
    assert log.input_tokens == 10
    assert log.output_tokens == 4


def test_openai_blocked_request_logged(client, mock_db):
    client.post(
        "/v1/proxy/openai/chat/completions",
        json={**_SAFE, "model": "gemini-pro"},
    )
    log: RequestLog = mock_db.add.call_args[0][0]
    assert log.provider == "openai"
    assert log.allowed is False
    assert log.upstream_status_code is None


# ── Infrastructure errors ──────────────────────────────────────────────────


def test_missing_openai_key_returns_503(client, mock_db, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    assert resp.status_code == 503
    assert resp.json()["error"]["type"] == "configuration_error"


def test_openai_timeout_returns_504(client, mock_db, with_openai_key):
    with patch("app.services.provider.httpx.post", side_effect=httpx.TimeoutException("timed out")):
        resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    assert resp.status_code == 504
    assert resp.json()["error"]["type"] == "upstream_timeout"


def test_openai_connection_error_returns_502(client, mock_db, with_openai_key):
    with patch("app.services.provider.httpx.post", side_effect=httpx.ConnectError("refused")):
        resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    assert resp.status_code == 502
    assert resp.json()["error"]["type"] == "upstream_error"


def test_db_failure_does_not_break_openai_response(client, mock_db, mock_openai_ok, with_openai_key):
    mock_db.commit.side_effect = Exception("db down")
    resp = client.post("/v1/proxy/openai/chat/completions", json=_SAFE)
    assert resp.status_code == 200
    mock_db.rollback.assert_called_once()
