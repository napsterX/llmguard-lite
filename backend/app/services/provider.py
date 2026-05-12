from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ForwardResult:
    status_code: int
    body: dict[str, Any]
    latency_ms: int
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    error_type: Optional[str] = None  # "timeout" | "connection_error" | None


@dataclass
class ProviderConfig:
    name: str
    url: str
    # Callable[api_key] -> request headers dict
    build_headers: Callable[[str], dict[str, str]]
    # Callable[response_body] -> (input_tokens, output_tokens)
    extract_usage: Callable[[dict[str, Any]], tuple[Optional[int], Optional[int]]]


def _anthropic_headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


def _openai_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }


def _anthropic_usage(body: dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    u = body.get("usage", {})
    return u.get("input_tokens"), u.get("output_tokens")


def _openai_usage(body: dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    u = body.get("usage", {})
    return u.get("prompt_tokens"), u.get("completion_tokens")


ANTHROPIC = ProviderConfig(
    name="anthropic",
    url="https://api.anthropic.com/v1/messages",
    build_headers=_anthropic_headers,
    extract_usage=_anthropic_usage,
)

OPENAI = ProviderConfig(
    name="openai",
    url="https://api.openai.com/v1/chat/completions",
    build_headers=_openai_headers,
    extract_usage=_openai_usage,
)


def forward_request(
    config: ProviderConfig,
    body: dict[str, Any],
    api_key: str,
    timeout: float = 60.0,
) -> ForwardResult:
    """Forward *body* to the provider and return a structured result.

    Never raises — network errors are captured in ``ForwardResult.error_type``.
    """
    headers = config.build_headers(api_key)
    t0 = time.monotonic()
    try:
        resp = httpx.post(config.url, json=body, headers=headers, timeout=timeout)
    except httpx.TimeoutException:
        logger.warning("Provider %s timed out", config.name)
        return ForwardResult(
            status_code=504,
            body={},
            latency_ms=int((time.monotonic() - t0) * 1000),
            input_tokens=None,
            output_tokens=None,
            error_type="timeout",
        )
    except httpx.RequestError as exc:
        logger.error("Provider %s connection error: %s", config.name, exc)
        return ForwardResult(
            status_code=502,
            body={},
            latency_ms=int((time.monotonic() - t0) * 1000),
            input_tokens=None,
            output_tokens=None,
            error_type="connection_error",
        )

    latency_ms = int((time.monotonic() - t0) * 1000)

    resp_body: dict[str, Any] = {}
    if "application/json" in resp.headers.get("content-type", ""):
        try:
            resp_body = resp.json()
        except Exception:
            pass

    input_tokens, output_tokens = config.extract_usage(resp_body)
    return ForwardResult(
        status_code=resp.status_code,
        body=resp_body,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
