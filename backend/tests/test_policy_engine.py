import pytest

from app.services.policy_engine import PolicyEngine, PolicyDecision

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine()


def _payload(content: str, model: str = "claude-3-5-sonnet-latest") -> dict:
    return {"model": model, "messages": [{"role": "user", "content": content}]}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_safe_prompt_is_allowed(engine):
    decision = engine.evaluate(_payload("What is the capital of France?"))
    assert decision.allowed is True
    assert decision.policy_name == "none"


def test_both_allowed_models_pass(engine):
    for model in ("claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"):
        decision = engine.evaluate(_payload("Hello", model=model))
        assert decision.allowed is True, f"{model} should be allowed"


def test_returns_policy_decision_instance(engine):
    result = engine.evaluate(_payload("Hello"))
    assert isinstance(result, PolicyDecision)


# ---------------------------------------------------------------------------
# Model allowlist
# ---------------------------------------------------------------------------


def test_unknown_model_is_blocked(engine):
    decision = engine.evaluate(_payload("Hello", model="gpt-4o"))
    assert decision.allowed is False
    assert decision.policy_name == "model_allowlist"
    assert decision.severity == "medium"
    assert "gpt-4o" in decision.reason


def test_missing_model_is_blocked(engine):
    decision = engine.evaluate({"messages": [{"role": "user", "content": "hi"}]})
    assert decision.allowed is False
    assert decision.policy_name == "model_allowlist"


def test_empty_model_is_blocked(engine):
    decision = engine.evaluate(_payload("Hello", model=""))
    assert decision.allowed is False
    assert decision.policy_name == "model_allowlist"


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------


def test_aws_access_key_is_blocked(engine):
    decision = engine.evaluate(_payload("key=AKIAIOSFODNN7EXAMPLE here"))
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"
    assert decision.severity == "high"
    assert "AWS" in decision.reason


def test_github_token_is_blocked(engine):
    token = "ghp_" + "A" * 36
    decision = engine.evaluate(_payload(f"token: {token}"))
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"


def test_anthropic_key_is_blocked(engine):
    key = "sk-ant-" + "a1B2" * 25   # 100 chars after prefix
    decision = engine.evaluate(_payload(f"my key is {key}"))
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"


def test_openai_key_is_blocked(engine):
    key = "sk-" + "a" * 48
    decision = engine.evaluate(_payload(f"key: {key}"))
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"


def test_private_key_header_is_blocked(engine):
    decision = engine.evaluate(_payload("-----BEGIN RSA PRIVATE KEY-----\nMIIEo..."))
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"


def test_bearer_token_is_blocked(engine):
    token = "Bearer " + "x" * 30
    decision = engine.evaluate(_payload(f"Authorization: {token}"))
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"


# ---------------------------------------------------------------------------
# PII detection
# ---------------------------------------------------------------------------


def test_ssn_is_blocked(engine):
    decision = engine.evaluate(_payload("My SSN is 123-45-6789, keep it safe."))
    assert decision.allowed is False
    assert decision.policy_name == "pii_detection"
    assert decision.severity == "medium"
    assert "SSN" in decision.reason


def test_credit_card_is_blocked(engine):
    decision = engine.evaluate(_payload("Card number: 4111 1111 1111 1111"))
    assert decision.allowed is False
    assert decision.policy_name == "pii_detection"
    assert "Credit card" in decision.reason


def test_email_is_blocked(engine):
    decision = engine.evaluate(_payload("Contact me at alice@example.com"))
    assert decision.allowed is False
    assert decision.policy_name == "pii_detection"


def test_us_phone_is_blocked(engine):
    decision = engine.evaluate(_payload("Call me at 555-867-5309"))
    assert decision.allowed is False
    assert decision.policy_name == "pii_detection"


# ---------------------------------------------------------------------------
# Destructive intent
# ---------------------------------------------------------------------------


def test_destructive_phrase_is_blocked(engine):
    decision = engine.evaluate(_payload("Please delete all records immediately"))
    assert decision.allowed is False
    assert decision.policy_name == "destructive_intent"
    assert decision.severity == "high"


def test_destructive_phrases_case_insensitive(engine):
    for phrase in (
        "DROP DATABASE",
        "Wipe Storage",
        "TERMINATE INSTANCES",
        "Remove All Users",
        "Destroy Infrastructure",
        "Reset Production",
    ):
        decision = engine.evaluate(_payload(phrase))
        assert decision.allowed is False, f"'{phrase}' should be blocked"
        assert decision.policy_name == "destructive_intent"


# ---------------------------------------------------------------------------
# Token guard
# ---------------------------------------------------------------------------


def test_oversized_prompt_is_blocked(engine):
    # Need len(text) // 4 > 8000, i.e. at least 32 004 chars (32004 // 4 = 8001)
    big = "a" * 32_005
    decision = engine.evaluate(_payload(big))
    assert decision.allowed is False
    assert decision.policy_name == "token_guard"
    assert decision.severity == "low"
    assert "8000" in decision.reason


def test_prompt_at_token_limit_is_allowed(engine):
    # Exactly 32 000 chars → 8 000 tokens (not strictly greater than limit)
    at_limit = "a" * 32_000
    decision = engine.evaluate(_payload(at_limit))
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Policy priority: model allowlist fires before content checks
# ---------------------------------------------------------------------------


def test_model_violation_takes_priority_over_secret(engine):
    key = "AKIAIOSFODNN7EXAMPLE"
    decision = engine.evaluate(_payload(key, model="gpt-4o"))
    assert decision.policy_name == "model_allowlist"


# ---------------------------------------------------------------------------
# Multi-part content blocks
# ---------------------------------------------------------------------------


def test_secret_in_content_block_is_blocked(engine):
    payload = {
        "model": "claude-3-5-sonnet-latest",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is my key: AKIAIOSFODNN7EXAMPLE"},
                ],
            }
        ],
    }
    decision = engine.evaluate(payload)
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"


def test_secret_in_system_prompt_is_blocked(engine):
    payload = {
        "model": "claude-3-5-sonnet-latest",
        "system": "Use key AKIAIOSFODNN7EXAMPLE for S3 access.",
        "messages": [{"role": "user", "content": "List my buckets"}],
    }
    decision = engine.evaluate(payload)
    assert decision.allowed is False
    assert decision.policy_name == "secret_detection"
