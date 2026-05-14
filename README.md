# LLMGuard Lite

[![CI](https://github.com/napsterX/llmguard-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/napsterX/llmguard-lite/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)

**Open-source API gateway for AI providers — policy enforcement, data governance, and audit logging for LLM traffic.**

---

## Project overview

LLMGuard Lite is a self-hosted proxy that sits between your application and AI providers such as Anthropic and OpenAI. It inspects every outbound request against a set of configurable data-governance policies, forwards compliant requests to the upstream provider, and writes a structured audit record regardless of outcome.

The goal is a lightweight, transparent layer that gives teams visibility and control over LLM usage without requiring changes to application code beyond the base URL.

---

## What it does

```
┌──────────────────┐     ┌───────────────────────────────────────────┐
│                  │     │               LLMGuard Lite               │
│   Application    │────▶│                                           │
│  (any language)  │     │  1. Evaluate data-governance policies     │
│                  │     │  2. Forward compliant requests upstream   │
└──────────────────┘     │  3. Write structured audit log entry      │
                         │                                           │
                         └────────────┬──────────────┬─────────────-─┘
                                      │              │
                           ┌──────────▼──┐  ┌────────▼───────┐
                           │Anthropic API│  │   OpenAI API   │
                           └─────────────┘  └────────────────┘
                                       │
                          ┌────────────▼──────────────────────────┐
                          │        Dashboard  (Next.js)           │
                          │   /admin/stats        /admin/logs     │
                          └───────────────────────────────────────┘
```

**Blocked request flow:** policy engine detects a violation → returns HTTP 400 with a structured error envelope → no upstream call is made → outcome is logged.

**Allowed request flow:** all policies pass → request forwarded to provider → provider response returned verbatim → outcome is logged.

---

## Architecture

![Architecture](docs/images/architecture.png)

*High-level request flow, policy enforcement pipeline, provider routing, audit logging, and dashboard visibility.*

---

## Docker Deployment

![Docker Deployment](docs/images/docker-deploy.png)

*Full local deployment using Docker Compose with backend, frontend, and PostgreSQL services running together.*

---

## Dashboard Overview

![Dashboard Overview](docs/images/dashboard-overview.png)

*Real-time operational visibility into allowed requests, blocked requests, policy categories, and request latency.*

---

## API Proxy Example

![API Proxy Example](docs/images/api-demo.png)

*Successful proxied Anthropic API request demonstrating compliant request forwarding through LLMGuard Lite.*

---

## Allowed Request Logging

![Allowed Request Logging](docs/images/allowed-request.png)

*Example of successful compliant request capture with full audit metadata.*

---

## Policy Enforcement Example

![Policy Enforcement Example](docs/images/pii-block.png)

*Demonstration of PII detection and policy-based blocking in production workflow.*

---

## Current MVP features

| Feature | Status |
|---|---|
| Anthropic proxy (`/v1/proxy/anthropic/messages`) | Included |
| OpenAI proxy (`/v1/proxy/openai/chat/completions`) | Included |
| Model governance — allowlist per provider endpoint | Included |
| Credential-format detection in prompt text | Included |
| Personal-data identifier detection in prompt text | Included |
| Content governance — irreversible-operation phrase detection | Included |
| Token-budget guard — block oversized prompts | Included |
| Structured audit log (PostgreSQL) | Included |
| Minimal read-only dashboard (Next.js) | Included |
| Provider timeout and connection-error handling | Included |
| DB-failure resilience — proxy response unaffected by log failure | Included |

### Policy reference

Each request is evaluated in the order below. The first violation short-circuits further evaluation. Raw prompt text is never written to the audit log — only the policy category and a descriptive reason are recorded.

| Policy | `policy_name` | Severity | Governs |
|---|---|---|---|
| Model governance | `model_allowlist` | `medium` | Requests targeting models not on the configured allowlist |
| Credential protection | `secret_detection` | `high` | Common API-key and authentication-token formats in prompt text |
| Personal-data protection | `pii_detection` | `medium` | Personal identifiers: national ID numbers, payment card numbers, email addresses, phone numbers |
| Content governance | `destructive_intent` | `high` | Phrases associated with irreversible data or infrastructure operations |
| Token-budget guard | `token_guard` | `low` | Prompts whose estimated token count exceeds the configured limit (default: 8 000) |

All policy logic is contained in `backend/app/services/policy_engine.py` and is covered by the unit test suite.

---

## Architecture

```
backend/
  app/
    config.py            ← Pydantic-settings env config
    db.py                ← SQLAlchemy engine + session factory
    main.py              ← FastAPI app, CORS, global error handler
    models/
      request_log.py     ← Audit log ORM model (PostgreSQL)
    routes/
      health.py          ← GET /health
      proxy.py           ← POST /v1/proxy/anthropic/messages
      openai_proxy.py    ← POST /v1/proxy/openai/chat/completions
      admin.py           ← GET /admin/stats, GET /admin/logs
    services/
      policy_engine.py   ← PolicyEngine, PolicyDecision, all five checks
      provider.py        ← ProviderConfig dataclass, forward_request()
      audit.py           ← persist_log() — resilient fire-and-forget write
  tests/                 ← pytest suite (mocked DB + mocked HTTP)

frontend/
  app/
    page.tsx             ← Server-component dashboard (stats + log table)
    layout.tsx           ← App shell
```

**Key design decisions:**

- **Provider abstraction.** Adding a new provider requires one `ProviderConfig` dataclass entry — URL, header builder, and usage-field extractor. The route handler is identical for every provider.
- **Audit resilience.** `persist_log()` wraps every database operation in a try/except. A DB failure writes a warning to the application log and calls `rollback()`, but does not affect the response returned to the caller.
- **No prompt storage.** The `RequestLog` model has no column for prompt content. The policy reason field records a category description only (e.g. `"Potential PII detected: Email address"`).

---

## Quickstart

### Docker (recommended)

```bash
git clone https://github.com/napsterX/llmguard-lite
cd llmguard-lite

cp backend/.env.example backend/.env
# Edit backend/.env — add your provider API keys (see Configuration below)

docker compose up --build
```

| Service | URL |
|---|---|
| Proxy API | http://localhost:8000 |
| Dashboard | http://localhost:3000 |
| PostgreSQL | localhost:5432 |

### Without Docker

**Prerequisites:** Python 3.9+, Node 20+, PostgreSQL 14+

```bash
# 1. Backend
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in DATABASE_URL and provider keys
uvicorn app.main:app --reload

# 2. Frontend — separate terminal
cd frontend
cp .env.example .env.local    # defaults to http://localhost:8000 — no edit needed
npm install
npm run dev
```

### Verify the proxy is running

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

### Send a proxied request

```bash
curl http://localhost:8000/v1/proxy/anthropic/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-latest",
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "What is the capital of France?"}]
  }'
```

The provider's response is returned verbatim on success.

### Policy violation response

When a request is blocked the proxy returns HTTP 400 and makes no upstream call:

```json
{
  "error": {
    "type": "policy_violation",
    "policy": "pii_detection",
    "severity": "medium",
    "message": "Potential PII detected: Email address"
  }
}
```

---

## Configuration

Copy `backend/.env.example` to `backend/.env` before starting the backend.

```
# DATABASE_URL=postgresql://llmguard:llmguard@localhost:5432/llmguard
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# APP_NAME=LLMGuard Lite
# DEBUG=false
```

**Backend** (`backend/.env`):

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `postgresql://llmguard:llmguard@localhost:5432/llmguard` | Yes | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | _(empty)_ | To proxy Anthropic | Anthropic API key |
| `OPENAI_API_KEY` | _(empty)_ | To proxy OpenAI | OpenAI API key |
| `APP_NAME` | `LLMGuard Lite` | No | Shown in auto-generated API docs at `/docs` |
| `DEBUG` | `false` | No | FastAPI debug mode — keep `false` in production |

**Frontend** (`frontend/.env.local`):

| Variable | Default | Required | Description |
|---|---|---|---|
| `FRONTEND_API_BASE_URL` | `http://localhost:8000` | No | Backend API base URL — read server-side only |

In Docker Compose, `FRONTEND_API_BASE_URL` is automatically set to `http://backend:8000` (the internal service name). No manual edit is needed for the Docker path.

The database schema is created automatically on first startup. No separate migration step is needed for a fresh install.

**Security note:** Never commit `.env` or `.env.local` to version control. Both are listed in `.gitignore` by default.

---

## Running tests

The test suite runs without a live database or network connection. All database queries are replaced with a `MagicMock` session via FastAPI dependency overrides, and all HTTP calls to upstream providers are patched with `unittest.mock.patch`.

```bash
cd backend
source venv/bin/activate
pytest -v
```

Expected result: **70 passed**.

| Test file | Covers |
|---|---|
| `tests/test_proxy.py` | Anthropic proxy — policy decisions, forwarding, logging, error envelopes |
| `tests/test_openai_proxy.py` | OpenAI proxy — same case set for the OpenAI endpoint |
| `tests/test_policy_engine.py` | PolicyEngine unit tests — one test per policy type and edge case |
| `tests/test_admin.py` | Admin stats and log endpoints |
| `tests/test_health.py` | Health check |

---

## Roadmap

The current release is the OSS core. Planned work, roughly in priority order:

- [ ] **Runtime-configurable policies** — load allowlists and phrase lists from environment variables or a YAML file without code changes
- [ ] **Streaming support** — proxy `stream: true` / SSE responses from both providers
- [ ] **Response-side scanning** — apply governance policies to upstream responses, not just requests
- [ ] **Rate limiting** — per-origin request and token-per-minute cap
- [ ] **Prometheus metrics** — `/metrics` endpoint for Grafana dashboards
- [ ] **GitHub Actions CI** — automated lint, type-check, and test on every pull request
- [ ] **Helm chart** — first-class Kubernetes deployment manifest

---

## Contributing

Contributions are welcome. Please open an issue before starting significant work so that direction can be agreed on early.

- **Bugs and feature requests:** [GitHub Issues](../../issues)
- **Security issues:** see [SECURITY.md](SECURITY.md) — do not open public issues for vulnerabilities
- **Pull requests:** run `pytest -v` locally before submitting; all tests must pass

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
