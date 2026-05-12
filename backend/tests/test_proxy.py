"""Tests for POST /v1/proxy/anthropic/messages.

DB is mocked via FastAPI dependency overrides (no live Postgres).
Anthropic HTTP calls are mocked via unittest.mock.patch on httpx.post in services/provider.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.models.request_log import RequestLog


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-key-xxxx")


@pytest.fixture
def mock_anthropic_ok():
    """Patch httpx.post (in services/provider) to return a 200 Anthropic response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = {
        "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Paris."}],
        "model": "claude-3-5-sonnet-latest",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 14, "output_tokens": 3},
    }
    with patch("app.services.provider.httpx.post", return_value=resp) as mock:
        yield mock


_SAFE: dict[str, Any] = {
    "model": "claude-3-5-sonnet-latest",
    "messages": [{"role": "user", "content": "What is the capital of France?"}],
    "max_tokens": 100,
}


def _msg(content: str) -> dict[str, Any]:
    return {**_SAFE, "messages": [{"role": "user", "content": content}]}


# ── Policy enforcement ─────────────────────────────────────────────────────


def test_unknown_model_blocked(client, mock_db):
    resp = client.post("/v1/proxy/anthropic/messages", json={**_SAFE, "model": "gpt-4o"})
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["type"] == "policy_violation"
    assert err["policy"] == "model_allowlist"
    assert "gpt-4o" in err["message"]


def test_secret_in_prompt_blocked(client, mock_db):
    resp = client.post("/v1/proxy/anthropic/messages", json=_msg("key=AKIAIOSFODNN7EXAMPLE"))
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["policy"] == "secret_detection"
    assert err["severity"] == "high"


def test_pii_in_prompt_blocked(client, mock_db):
    resp = client.post("/v1/proxy/anthropic/messages", json=_msg("My SSN is 123-45-6789"))
    assert resp.status_code == 400
    assert resp.json()["error"]["policy"] == "pii_detection"


def test_destructive_intent_blocked(client, mock_db):
    resp = client.post("/v1/proxy/anthropic/messages", json=_msg("drop database prod"))
    assert resp.status_code == 400
    assert resp.json()["error"]["policy"] == "destructive_intent"


def test_oversized_prompt_blocked(client, mock_db):
    resp = client.post("/v1/proxy/anthropic/messages", json=_msg("x" * 33_000))
    assert resp.status_code == 400
    assert resp.json()["error"]["policy"] == "token_guard"


def test_both_haiku_and_sonnet_allowed_through(client, mock_db, mock_anthropic_ok, with_api_key):
    for model in ("claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"):
        resp = client.post("/v1/proxy/anthropic/messages", json={**_SAFE, "model": model})
        assert resp.status_code == 200, f"{model} should be forwarded"


# ── Logging: blocked requests ──────────────────────────────────────────────


def test_blocked_request_is_logged(client, mock_db):
    client.post("/v1/proxy/anthropic/messages", json={**_SAFE, "model": "gpt-4o"})

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

    log: RequestLog = mock_db.add.call_args[0][0]
    assert isinstance(log, RequestLog)
    assert log.allowed is False
    assert log.policy_name == "model_allowlist"
    assert log.model == "gpt-4o"
    assert log.provider == "anthropic"
    assert log.upstream_status_code is None
    assert log.latency_ms is None


def test_blocked_log_never_contains_raw_prompt(client, mock_db):
    secret = "AKIAIOSFODNN7EXAMPLE"
    client.post("/v1/proxy/anthropic/messages", json=_msg(f"key={secret}"))

    log: RequestLog = mock_db.add.call_args[0][0]
    assert secret not in log.policy_reason


# ── Forwarding ─────────────────────────────────────────────────────────────


def test_allowed_request_is_forwarded(client, mock_db, mock_anthropic_ok, with_api_key):
    resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    assert resp.status_code == 200
    assert resp.json()["role"] == "assistant"
    mock_anthropic_ok.assert_called_once()


def test_forwarded_request_carries_api_key_header(client, mock_db, mock_anthropic_ok, with_api_key):
    client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    _, kwargs = mock_anthropic_ok.call_args
    assert kwargs["headers"]["x-api-key"] == "sk-ant-test-key-xxxx"


def test_forwarded_request_body_is_unchanged(client, mock_db, mock_anthropic_ok, with_api_key):
    client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    _, kwargs = mock_anthropic_ok.call_args
    assert kwargs["json"] == _SAFE


def test_anthropic_response_returned_verbatim(client, mock_db, mock_anthropic_ok, with_api_key):
    resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    body = resp.json()
    assert body["type"] == "message"
    assert body["content"][0]["text"] == "Paris."


# ── Logging: forwarded requests ────────────────────────────────────────────


def test_forwarded_request_is_logged_with_metadata(client, mock_db, mock_anthropic_ok, with_api_key):
    client.post("/v1/proxy/anthropic/messages", json=_SAFE)

    mock_db.add.assert_called_once()
    log: RequestLog = mock_db.add.call_args[0][0]

    assert log.allowed is True
    assert log.policy_name == "none"
    assert log.model == "claude-3-5-sonnet-latest"
    assert log.provider == "anthropic"
    assert log.upstream_status_code == 200
    assert log.input_tokens == 14
    assert log.output_tokens == 3
    assert log.latency_ms is not None
    assert log.latency_ms >= 0


def test_anthropic_error_status_is_logged(client, mock_db, with_api_key):
    err_resp = MagicMock()
    err_resp.status_code = 429
    err_resp.headers = {"content-type": "application/json"}
    err_resp.json.return_value = {"error": {"type": "rate_limit_error"}}

    with patch("app.services.provider.httpx.post", return_value=err_resp):
        client.post("/v1/proxy/anthropic/messages", json=_SAFE)

    log: RequestLog = mock_db.add.call_args[0][0]
    assert log.upstream_status_code == 429


# ── Anthropic error pass-through ───────────────────────────────────────────


def test_anthropic_401_passed_through(client, mock_db, with_api_key):
    err_resp = MagicMock()
    err_resp.status_code = 401
    err_resp.headers = {"content-type": "application/json"}
    err_resp.json.return_value = {"error": {"type": "authentication_error", "message": "Invalid key"}}

    with patch("app.services.provider.httpx.post", return_value=err_resp):
        resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)

    assert resp.status_code == 401
    assert resp.json()["error"]["type"] == "authentication_error"


def test_anthropic_429_passed_through(client, mock_db, with_api_key):
    err_resp = MagicMock()
    err_resp.status_code = 429
    err_resp.headers = {"content-type": "application/json"}
    err_resp.json.return_value = {"error": {"type": "rate_limit_error"}}

    with patch("app.services.provider.httpx.post", return_value=err_resp):
        resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)

    assert resp.status_code == 429


def test_anthropic_500_passed_through(client, mock_db, with_api_key):
    err_resp = MagicMock()
    err_resp.status_code = 500
    err_resp.headers = {"content-type": "application/json"}
    err_resp.json.return_value = {"error": {"type": "api_error"}}

    with patch("app.services.provider.httpx.post", return_value=err_resp):
        resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)

    assert resp.status_code == 500


# ── Infrastructure errors ──────────────────────────────────────────────────


def test_missing_api_key_returns_503(client, mock_db, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    assert resp.status_code == 503
    assert resp.json()["error"]["type"] == "configuration_error"


def test_anthropic_timeout_returns_504(client, mock_db, with_api_key):
    with patch("app.services.provider.httpx.post", side_effect=httpx.TimeoutException("timed out")):
        resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    assert resp.status_code == 504
    assert resp.json()["error"]["type"] == "upstream_timeout"


def test_anthropic_connection_error_returns_502(client, mock_db, with_api_key):
    with patch("app.services.provider.httpx.post", side_effect=httpx.ConnectError("refused")):
        resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    assert resp.status_code == 502
    assert resp.json()["error"]["type"] == "upstream_error"


# ── DB failure resilience ──────────────────────────────────────────────────


def test_db_commit_failure_does_not_affect_response(client, mock_db, mock_anthropic_ok, with_api_key):
    mock_db.commit.side_effect = Exception("connection lost")
    resp = client.post("/v1/proxy/anthropic/messages", json=_SAFE)
    assert resp.status_code == 200
    mock_db.rollback.assert_called_once()


def test_db_failure_on_blocked_request_does_not_swallow_policy_error(client, mock_db):
    mock_db.commit.side_effect = Exception("connection lost")
    resp = client.post("/v1/proxy/anthropic/messages", json={**_SAFE, "model": "gpt-4o"})
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "policy_violation"
    mock_db.rollback.assert_called_once()


# ── Error response shape ───────────────────────────────────────────────────


def test_policy_violation_error_has_required_fields(client, mock_db):
    resp = client.post("/v1/proxy/anthropic/messages", json={**_SAFE, "model": "gpt-4o"})
    err = resp.json()["error"]
    assert "type" in err
    assert "policy" in err
    assert "severity" in err
    assert "message" in err


def test_503_error_has_required_fields(client, mock_db, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    err = client.post("/v1/proxy/anthropic/messages", json=_SAFE).json()["error"]
    assert "type" in err
    assert "message" in err
