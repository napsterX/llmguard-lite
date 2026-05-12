from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.audit import persist_log
from app.services.policy_engine import OPENAI_ALLOWED_MODELS, PolicyEngine
from app.services.provider import OPENAI, forward_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/proxy", tags=["proxy"])

_policy_engine = PolicyEngine(allowed_models=OPENAI_ALLOWED_MODELS)


@router.post("/openai/chat/completions")
def openai_chat_completions(
    body: Annotated[dict[str, Any], Body()],
    db: Session = Depends(get_db),
) -> JSONResponse:
    model = body.get("model", "")

    decision = _policy_engine.evaluate(body)

    if not decision.allowed:
        persist_log(db, model=model, decision=decision, provider="openai")
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "type": "policy_violation",
                    "policy": decision.policy_name,
                    "severity": decision.severity,
                    "message": decision.reason,
                }
            },
        )

    from app.config import settings

    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not configured")
        return JSONResponse(
            status_code=503,
            content={"error": {"type": "configuration_error", "message": "Upstream API key is not configured"}},
        )

    result = forward_request(OPENAI, body, settings.openai_api_key)

    if result.error_type == "timeout":
        return JSONResponse(
            status_code=504,
            content={"error": {"type": "upstream_timeout", "message": "OpenAI API timed out"}},
        )
    if result.error_type == "connection_error":
        return JSONResponse(
            status_code=502,
            content={"error": {"type": "upstream_error", "message": "Could not reach OpenAI API"}},
        )

    persist_log(
        db,
        model=model,
        decision=decision,
        provider="openai",
        upstream_status_code=result.status_code,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    return JSONResponse(status_code=result.status_code, content=result.body)
