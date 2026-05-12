"""Tests for /admin/* endpoints (read-only, no auth required)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.request_log import RequestLog


# ── GET /admin/stats ───────────────────────────────────────────────────────


def test_get_stats_returns_200(client, mock_db):
    resp = client.get("/admin/stats")
    assert resp.status_code == 200


def test_get_stats_response_shape(client, mock_db):
    resp = client.get("/admin/stats")
    body = resp.json()
    assert "total_requests" in body
    assert "allowed_count" in body
    assert "blocked_count" in body
    assert "avg_latency_ms" in body


def test_get_stats_blocked_is_total_minus_allowed(client, mock_db):
    mock_db.query.return_value.count.return_value = 10
    mock_db.query.return_value.filter.return_value.count.return_value = 7
    mock_db.query.return_value.filter.return_value.isnot.return_value.all.return_value = []

    resp = client.get("/admin/stats")
    body = resp.json()
    assert body["total_requests"] == 10
    assert body["allowed_count"] == 7
    assert body["blocked_count"] == 3


def test_get_stats_no_tenant_count_field(client, mock_db):
    body = client.get("/admin/stats").json()
    assert "tenant_count" not in body


# ── GET /admin/logs ────────────────────────────────────────────────────────


def test_list_logs_returns_200(client, mock_db):
    resp = client.get("/admin/logs")
    assert resp.status_code == 200
    body = resp.json()
    assert "logs" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body


def test_list_logs_default_limit_is_50(client, mock_db):
    resp = client.get("/admin/logs")
    assert resp.json()["limit"] == 50


def test_list_logs_returns_log_list(client, mock_db):
    log = RequestLog(
        id="log-1",
        provider="anthropic",
        model="claude-3-5-sonnet-latest",
        allowed=True,
        policy_name="none",
        policy_severity="none",
        policy_reason="",
        created_at=datetime.now(timezone.utc),
    )
    mock_db.query.return_value.order_by.return_value.count.return_value = 1
    mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [log]

    resp = client.get("/admin/logs")
    logs = resp.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["provider"] == "anthropic"
    assert "tenant_id" not in logs[0]


def test_list_logs_no_tenant_id_in_response(client, mock_db):
    resp = client.get("/admin/logs")
    assert resp.status_code == 200
    for log_entry in resp.json()["logs"]:
        assert "tenant_id" not in log_entry
