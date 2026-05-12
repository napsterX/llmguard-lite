from __future__ import annotations

import re

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ANTHROPIC_ALLOWED_MODELS: frozenset[str] = frozenset(
    {
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
    }
)

OPENAI_ALLOWED_MODELS: frozenset[str] = frozenset(
    {
        "gpt-4o",
        "gpt-4o-mini",
    }
)

# Default used when PolicyEngine is constructed without explicit allowed_models
_ALLOWED_MODELS = ANTHROPIC_ALLOWED_MODELS

_TOKEN_LIMIT = 8_000
_CHARS_PER_TOKEN = 4  # rough character-based estimate

_DESTRUCTIVE_PHRASES: tuple[str, ...] = (
    "delete all",
    "drop database",
    "wipe storage",
    "terminate instances",
    "remove all users",
    "destroy infrastructure",
    "reset production",
)

# (human-readable name, compiled pattern)
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS Access Key",     re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token",       re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("GitHub PAT",         re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b")),
    # Anthropic before OpenAI so sk-ant- isn't shadowed by sk- pattern
    ("Anthropic API key",  re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("OpenAI API key",     re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Private key",        re.compile(r"-----BEGIN\s(?:RSA\s|EC\s|OPENSSH\s)?PRIVATE KEY-----")),
    ("Bearer token",       re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]{20,}={0,2}")),
)

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SSN",            re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("Credit card",    re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b")),
    ("Email address",  re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("US phone",       re.compile(r"\b(?:\+1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")),
)


# ---------------------------------------------------------------------------
# Decision model
# ---------------------------------------------------------------------------

class PolicyDecision(BaseModel):
    allowed: bool
    policy_name: str
    severity: str   # "low" | "medium" | "high"
    reason: str


_ALLOW = PolicyDecision(
    allowed=True,
    policy_name="none",
    severity="low",
    reason="No policy violations detected",
)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text(payload: dict) -> str:
    """Return all human-readable text from an Anthropic-style messages payload."""
    parts: list[str] = []

    system = payload.get("system", "")
    if isinstance(system, str) and system:
        parts.append(system)

    for msg in payload.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        parts.append(text)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Individual policy checks
# Each returns a blocking PolicyDecision on violation, or None if clean.
# ---------------------------------------------------------------------------

def _check_model_allowlist(payload: dict, allowed_models: frozenset[str]) -> PolicyDecision | None:
    model = payload.get("model", "")
    if model not in allowed_models:
        return PolicyDecision(
            allowed=False,
            policy_name="model_allowlist",
            severity="medium",
            reason=f"Model '{model}' is not in the allowlist",
        )
    return None


def _check_secrets(text: str) -> PolicyDecision | None:
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return PolicyDecision(
                allowed=False,
                policy_name="secret_detection",
                severity="high",
                reason=f"Potential secret detected: {name}",
            )
    return None


def _check_pii(text: str) -> PolicyDecision | None:
    for name, pattern in _PII_PATTERNS:
        if pattern.search(text):
            return PolicyDecision(
                allowed=False,
                policy_name="pii_detection",
                severity="medium",
                reason=f"Potential PII detected: {name}",
            )
    return None


def _check_destructive_intent(text: str) -> PolicyDecision | None:
    lower = text.lower()
    for phrase in _DESTRUCTIVE_PHRASES:
        if phrase in lower:
            return PolicyDecision(
                allowed=False,
                policy_name="destructive_intent",
                severity="high",
                reason="Destructive intent phrase detected",
            )
    return None


def _check_token_limit(text: str) -> PolicyDecision | None:
    estimated = len(text) // _CHARS_PER_TOKEN
    if estimated > _TOKEN_LIMIT:
        return PolicyDecision(
            allowed=False,
            policy_name="token_guard",
            severity="low",
            reason=f"Estimated prompt size ({estimated} tokens) exceeds the {_TOKEN_LIMIT}-token limit",
        )
    return None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Evaluate a request payload against all policies.

    Pass ``allowed_models`` to restrict the model allowlist per provider.
    Policies run in priority order; the first violation is returned.
    Raw prompt content is never included in the decision.
    """

    def __init__(self, allowed_models: frozenset[str] = _ALLOWED_MODELS) -> None:
        self._allowed_models = allowed_models

    def evaluate(self, payload: dict) -> PolicyDecision:
        text = _extract_text(payload)

        # Short-circuit: `or` stops at the first truthy (non-None) value.
        return (
            _check_model_allowlist(payload, self._allowed_models)
            or _check_secrets(text)
            or _check_pii(text)
            or _check_destructive_intent(text)
            or _check_token_limit(text)
            or _ALLOW
        )
