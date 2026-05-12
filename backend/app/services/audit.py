from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.request_log import RequestLog
from app.services.policy_engine import PolicyDecision

logger = logging.getLogger(__name__)


def persist_log(
    db: Session,
    *,
    model: str,
    decision: PolicyDecision,
    provider: str = "anthropic",
    upstream_status_code: Optional[int] = None,
    latency_ms: Optional[int] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> None:
    """Write a ``RequestLog`` row. Never raises — logging must not break the proxy."""
    try:
        entry = RequestLog(
            provider=provider,
            model=model,
            allowed=decision.allowed,
            policy_name=decision.policy_name,
            policy_severity=decision.severity,
            policy_reason=decision.reason,
            upstream_status_code=upstream_status_code,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.error("Failed to persist request log: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
