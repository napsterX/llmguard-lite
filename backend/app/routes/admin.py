from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.request_log import RequestLog

router = APIRouter(prefix="/admin", tags=["admin"])


def _log_dict(log: RequestLog) -> dict:
    return {
        "id": log.id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "provider": log.provider,
        "model": log.model,
        "allowed": log.allowed,
        "policy_name": log.policy_name,
        "policy_severity": log.policy_severity,
        "upstream_status_code": log.upstream_status_code,
        "latency_ms": log.latency_ms,
        "input_tokens": log.input_tokens,
        "output_tokens": log.output_tokens,
    }


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)) -> JSONResponse:
    total = db.query(RequestLog).count()
    allowed_count = db.query(RequestLog).filter(RequestLog.allowed.is_(True)).count()

    latency_rows = (
        db.query(RequestLog.latency_ms)
        .filter(RequestLog.latency_ms.isnot(None))
        .all()
    )
    avg_latency = sum(r[0] for r in latency_rows) // len(latency_rows) if latency_rows else 0

    return JSONResponse(
        content={
            "total_requests": total,
            "allowed_count": allowed_count,
            "blocked_count": total - allowed_count,
            "avg_latency_ms": avg_latency,
        }
    )


@router.get("/logs")
def list_logs(
    limit: int = 50,
    offset: int = 0,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    q = db.query(RequestLog).order_by(RequestLog.created_at.desc())
    if provider:
        q = q.filter(RequestLog.provider == provider)
    total = q.count()
    logs = q.offset(offset).limit(limit).all()
    return JSONResponse(
        content={
            "total": total,
            "offset": offset,
            "limit": limit,
            "logs": [_log_dict(log) for log in logs],
        }
    )
