# Architecture — LLMGuard Lite

This document describes the high-level architecture of LLMGuard Lite: its components, the lifecycle of a request through the system, the key design decisions that shape the codebase, and the boundaries between the open-source core and future extension points.

**Audience:** contributors, operators, and anyone evaluating the project technically.

---

## Contents

1. [Project purpose](#1-project-purpose)
2. [System overview](#2-system-overview)
3. [Core components](#3-core-components)
4. [Request lifecycle](#4-request-lifecycle)
5. [Directory structure](#5-directory-structure)
6. [Key design decisions](#6-key-design-decisions)
7. [Security design principles](#7-security-design-principles)
8. [Deployment model](#8-deployment-model)
9. [Extension points](#9-extension-points)
10. [OSS and enterprise boundary](#10-oss-and-enterprise-boundary)
11. [Summary](#11-summary)

---

## 1. Project purpose

LLMGuard Lite is a self-hosted API proxy that enforces data-governance policies on outbound requests to AI language model providers. It addresses a gap that appears when organisations begin integrating LLMs into internal tooling: traffic to external AI APIs is opaque, unaudited, and ungoverned by default.

The proxy provides three capabilities:

- **Policy enforcement** — evaluate each request against a configurable rule set before forwarding it, blocking violations at the network boundary
- **Audit logging** — persist a structured record of every request decision, with no storage of raw prompt content
- **Operational visibility** — a minimal dashboard that surfaces traffic statistics and log entries to operators

LLMGuard Lite is not a firewall, an authentication system, or a certified compliance platform. It is a governance layer — one control among several that a responsible deployment should include.

---

## 2. System overview

```
                         ┌─────────────────────────────────────────────────────────┐
                         │                    LLMGuard Lite                        │
                         │                                                         │
  ┌──────────────┐       │  ┌─────────────────────────────────────────────────┐   │
  │              │       │  │                  FastAPI Backend                 │   │
  │  Application │──────▶│  │                                                 │   │
  │ (any language│       │  │  ┌──────────────┐     ┌────────────────────┐   │   │
  │  or SDK)     │       │  │  │ Policy Engine│     │ Provider Abstraction│   │   │
  │              │       │  │  │              │     │ Layer              │   │   │
  └──────────────┘       │  │  │ model        │     │                    │   │   │
                         │  │  │ allowlist    │     │ ProviderConfig     │   │   │
                         │  │  │ credential   │     │ forward_request()  │   │   │
                         │  │  │ protection   │     │                    │   │   │
                         │  │  │ PII guard    │     └────────┬───────────┘   │   │
                         │  │  │ content gov. │              │               │   │
                         │  │  │ token limit  │              │               │   │
                         │  │  └──────┬───────┘              │               │   │
                         │  │         │                       │               │   │
                         │  │  ┌──────▼───────┐              │               │   │
                         │  │  │  Audit Logger│              │               │   │
                         │  │  │ persist_log()│              │               │   │
                         │  │  └──────┬───────┘              │               │   │
                         │  │         │                       │               │   │
                         │  └─────────┼───────────────────────┼───────────────┘   │
                         │            │                       │                   │
                         └────────────┼───────────────────────┼───────────────────┘
                                      │                       │
                         ┌────────────▼───────┐   ┌──────────▼──────────────────┐
                         │    PostgreSQL       │   │    AI Providers (external)   │
                         │   request_logs     │   │                             │
                         │                   │   │  Anthropic   │   OpenAI     │
                         └────────────┬───────┘   └─────────────────────────────┘
                                      │
                         ┌────────────▼───────────────────────┐
                         │       Next.js Dashboard             │
                         │                                    │
                         │   /admin/stats    /admin/logs      │
                         │                                    │
                         └────────────────────────────────────┘
```

---

## 3. Core components

### 3.1 FastAPI backend (`backend/app/`)

The backend is a synchronous FastAPI application served by Uvicorn. It owns the entire request path: receiving the inbound call, invoking the policy engine, forwarding to the upstream provider if appropriate, and writing the audit log entry.

FastAPI is chosen for its typed request/response model, automatic OpenAPI documentation at `/docs`, and dependency injection system — which makes the database session and any future injectable services straightforward to mock in tests.

Routes are registered as separate `APIRouter` instances and mounted in `main.py`. This keeps the route definitions isolated and independently testable.

**Key files:**

| File | Responsibility |
|---|---|
| `app/main.py` | Application factory, CORS middleware, global error handler, router registration |
| `app/config.py` | Pydantic-settings config — all environment variables in one place |
| `app/db.py` | SQLAlchemy engine and session factory (`get_db` dependency) |

### 3.2 Frontend dashboard (`frontend/`)

The dashboard is a Next.js 16 application using the App Router and React Server Components. Pages fetch data from the backend admin endpoints at render time using the native `fetch` API with `cache: "no-store"`, so every page load reflects current state without a client-side data layer.

The dashboard is intentionally read-only. It surfaces two views:

- **Stats** — total requests, allowed count, blocked count, average latency
- **Log table** — a paginated list of recent audit log entries with provider, model, status, policy name, and latency

No write operations are exposed through the dashboard. Configuration changes are made via environment variables or code.

### 3.3 Provider abstraction layer (`app/services/provider.py`)

The provider layer decouples the proxy route handlers from provider-specific details. Each supported provider is represented as a `ProviderConfig` dataclass instance with three fields:

- `url` — the upstream API endpoint
- `build_headers` — a callable that takes an API key and returns the appropriate request headers for that provider
- `extract_usage` — a callable that reads token counts from the provider's response body

A single `forward_request()` function accepts any `ProviderConfig` and handles the HTTP call, timing, error classification, and response parsing uniformly. Route handlers call `forward_request()` with the appropriate config; they do not contain any provider-specific logic themselves.

This means adding a new provider requires only a new `ProviderConfig` instance — the route handler, policy evaluation, and audit logging code is reused unchanged.

**Current providers:**

| Provider | Config constant | Upstream URL |
|---|---|---|
| Anthropic | `ANTHROPIC` | `https://api.anthropic.com/v1/messages` |
| OpenAI | `OPENAI` | `https://api.openai.com/v1/chat/completions` |

### 3.4 Policy engine (`app/services/policy_engine.py`)

The policy engine evaluates a request payload against an ordered set of independent policy checks. Each check is a pure function that returns either `None` (no violation) or a `PolicyDecision` instance (violation found). The engine uses Python's short-circuit `or` chain to stop at the first violation:

```
model_allowlist → credential protection → PII guard → content governance → token limit → allow
```

`PolicyDecision` is a Pydantic model with four fields: `allowed` (bool), `policy_name` (str), `severity` (str), and `reason` (str). The reason field describes the category of finding — never the content that triggered it.

`PolicyEngine` is instantiated once per route at module load time with a provider-specific model allowlist. Checks that do not depend on the allowlist (credential protection, PII guard, content governance, token limit) are shared across all providers.

**Policies:**

| Check | `policy_name` | Severity | Evaluated against |
|---|---|---|---|
| Model governance | `model_allowlist` | `medium` | Request payload `model` field |
| Credential protection | `secret_detection` | `high` | All text content in the request |
| Personal-data protection | `pii_detection` | `medium` | All text content in the request |
| Content governance | `destructive_intent` | `high` | All text content in the request |
| Token-budget guard | `token_guard` | `low` | Estimated character count of all text content |

### 3.5 Audit logger (`app/services/audit.py`)

`persist_log()` writes a `RequestLog` row to PostgreSQL after every policy evaluation, whether the request was allowed or blocked. It is designed to never propagate exceptions to the caller — a database failure produces a logged warning and a `rollback()` call, but does not affect the response returned to the application.

This resilience guarantee means that a transient database outage degrades observability without degrading proxy availability. The tradeoff is that audit log entries may be missing for the duration of an outage; this is acceptable for the community edition and documented in `SECURITY.md`.

### 3.6 PostgreSQL (`request_logs` table)

The database holds a single application table: `request_logs`. The schema is created automatically by SQLAlchemy's `Base.metadata.create_all()` on startup. There are no migration files; a fresh database is always in the correct state.

**Schema:**

| Column | Type | Description |
|---|---|---|
| `id` | `VARCHAR(36)` | UUID, primary key, generated at write time |
| `created_at` | `TIMESTAMPTZ` | UTC timestamp of the request |
| `provider` | `VARCHAR(20)` | `anthropic` or `openai` |
| `model` | `VARCHAR(100)` | Model identifier from the request payload |
| `allowed` | `BOOLEAN` | Whether the request passed all policy checks |
| `policy_name` | `VARCHAR(50)` | Name of the triggered policy, or `none` |
| `policy_severity` | `VARCHAR(20)` | `high`, `medium`, `low`, or `none` |
| `policy_reason` | `TEXT` | Human-readable category description |
| `upstream_status_code` | `INTEGER` | HTTP status returned by the provider, or `NULL` if blocked |
| `latency_ms` | `INTEGER` | Round-trip time to the provider in milliseconds, or `NULL` if blocked |
| `input_tokens` | `INTEGER` | Input token count from the provider response, or `NULL` |
| `output_tokens` | `INTEGER` | Output token count from the provider response, or `NULL` |

There is no column for prompt content, request body, or response body.

---

## 4. Request lifecycle

The following describes the complete path of a single proxied request.

```
Inbound request
      │
      ▼
┌─────────────────────────────────────────────┐
│  Route handler  (proxy.py / openai_proxy.py) │
│  Extracts: model, request body               │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  Policy engine  evaluate(payload)            │
│                                             │
│  1. model_allowlist   ──── violation? ──▶ BLOCK
│  2. secret_detection  ──── violation? ──▶ BLOCK
│  3. pii_detection     ──── violation? ──▶ BLOCK
│  4. destructive_intent──── violation? ──▶ BLOCK
│  5. token_guard       ──── violation? ──▶ BLOCK
│                                    │
│                              all pass?
└─────────────────────────────┬───────────────┘
                              │
             ┌────────────────┴──────────────┐
             │ BLOCKED                       │ ALLOWED
             │                               │
             ▼                               ▼
    persist_log(allowed=False)      API key present?
    return HTTP 400                      │
    {"error": {policy_violation}}   No ──▶ HTTP 503
                                         │
                                    Yes  ▼
                                 forward_request()
                                 (httpx.post, 60s timeout)
                                         │
                              ┌──────────┴──────────┐
                              │ Network error        │ Success
                              │                      │
                    timeout ──▶ HTTP 504    persist_log(allowed=True,
                    connect ──▶ HTTP 502      upstream_status_code,
                                              latency_ms,
                                              input_tokens,
                                              output_tokens)
                                                     │
                                             return HTTP <upstream>
                                             {provider response body}
```

**Error envelope shape** (all non-2xx responses from the proxy itself):

```json
{
  "error": {
    "type": "policy_violation | configuration_error | upstream_timeout | upstream_error",
    "policy": "policy_name (policy_violation only)",
    "severity": "high | medium | low (policy_violation only)",
    "message": "Human-readable description"
  }
}
```

Provider error responses (4xx, 5xx from Anthropic or OpenAI) are returned verbatim with their original status code. The proxy does not rewrite upstream errors.

---

## 5. Directory structure

```
llmguard-lite/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Settings — one class, all env vars
│   │   ├── db.py                  # Engine, SessionLocal, Base, get_db()
│   │   ├── main.py                # App factory, middleware, exception handler
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py        # Imports all models to register with Base
│   │   │   └── request_log.py     # RequestLog ORM model
│   │   │
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py          # GET /health
│   │   │   ├── proxy.py           # POST /v1/proxy/anthropic/messages
│   │   │   ├── openai_proxy.py    # POST /v1/proxy/openai/chat/completions
│   │   │   └── admin.py           # GET /admin/stats, GET /admin/logs
│   │   │
│   │   └── services/
│   │       ├── audit.py           # persist_log() — resilient DB write
│   │       ├── policy_engine.py   # PolicyEngine, PolicyDecision, checks
│   │       └── provider.py        # ProviderConfig, ForwardResult, forward_request()
│   │
│   ├── tests/
│   │   ├── conftest.py            # client, mock_db fixtures
│   │   ├── test_health.py
│   │   ├── test_proxy.py
│   │   ├── test_openai_proxy.py
│   │   ├── test_policy_engine.py
│   │   └── test_admin.py
│   │
│   ├── .env.example
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx             # App shell, metadata
│   │   └── page.tsx               # Stats + log dashboard (Server Component)
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
│
├── docs/
│   ├── architecture.md            # This document
│   └── roadmap.md
│
├── docker-compose.yml
├── .gitignore
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── SECURITY.md
```

---

## 6. Key design decisions

### No prompt storage

The `request_logs` table has no column for request or response content. This is a deliberate, load-bearing constraint — not an omission to be filled later.

Storing prompt content would make the database a secondary repository of whatever sensitive material the policy engine was designed to intercept. It would also create a data-retention obligation for operators that is out of proportion to the value gained. The audit log records *what happened* (which policy triggered, which model was targeted, what the outcome was) and nothing more.

This decision simplifies the security posture of the database, reduces GDPR and similar compliance surface area for operators, and makes the proxy safe to use in front of sensitive internal workloads.

### Metadata-only audit log

Every request produces a log entry regardless of outcome. Blocked requests are logged with `allowed=False`, the policy name, and a category-level reason. Allowed requests are logged with `allowed=True`, the upstream HTTP status, round-trip latency, and token counts extracted from the provider response.

The `policy_reason` field contains a description of the category of finding (e.g. `"Potential PII detected: Email address"`) generated by the policy engine. It never contains any portion of the request text.

### Provider abstraction via dataclass

The `ProviderConfig` dataclass separates what is provider-specific (URL, header format, response structure) from what is generic (HTTP forwarding, timing, error classification). Route handlers are structurally identical across providers — the only difference is which `ProviderConfig` constant is passed to `forward_request()`.

This design means the cost of adding a new provider is a new `ProviderConfig` instance plus allowlist configuration. No changes to route handlers, audit logging, or policy evaluation are required.

### Audit resilience over audit completeness

`persist_log()` catches all exceptions, logs a warning, and returns without raising. The proxy response is always delivered, even if the database write fails. This prioritises proxy availability over guaranteed audit completeness.

For the community edition, this tradeoff is appropriate. Operators with hard audit requirements — regulated environments where every event must be durable — should pair LLMGuard Lite with an independent, high-durability log pipeline.

### OSS scope boundaries

Authentication, multi-tenancy, RBAC, billing, and compliance reporting are intentionally absent from the codebase. These are enterprise concerns that require careful per-customer configuration and carry significant liability surface area. Their absence keeps the OSS core auditable, deployable without infrastructure dependencies beyond PostgreSQL, and trustworthy as a foundation for extensions.

The extension points described in [Section 9](#9-extension-points) are designed to let these capabilities be layered on without modifying the core.

---

## 7. Security design principles

**Least-privilege data model.** The database holds only what is needed for operational visibility. No credentials, no prompt content, no user identifiers.

**Environment-variable-only secrets.** Provider API keys and `DATABASE_URL` are read exclusively from environment variables via Pydantic-settings. They are never logged, never included in error responses, and never appear in the codebase.

**Structured error responses.** All error responses from the proxy use the same `{"error": {...}}` envelope. Internal details (stack traces, configuration values) are never returned to callers. Provider errors are forwarded verbatim, which is intentional — the proxy does not add information to upstream errors.

**No admin authentication by design.** The admin endpoints are read-only and carry no built-in authentication. This is an intentional design choice for a self-hosted tool: the operator supplies access control at the infrastructure layer (reverse proxy, firewall, VPN). Building auth into the proxy itself would create a second credential management surface without adding meaningful security for the typical self-hosted deployment model.

**Dependency surface minimisation.** The backend depends on a small set of well-maintained libraries: FastAPI, SQLAlchemy, Pydantic, httpx, and psycopg2. No LLM SDKs are used — provider communication is plain HTTP via httpx, which keeps the dependency graph shallow and the upgrade path straightforward.

---

## 8. Deployment model

### Local development

Each service runs in its own process: Uvicorn for the backend, `next dev` for the frontend, and a local or containerised PostgreSQL instance. Environment is configured via `backend/.env`. The database schema is created automatically on first startup.

### Docker Compose

The provided `docker-compose.yml` defines three services:

| Service | Image | Port |
|---|---|---|
| `backend` | Built from `backend/Dockerfile` | 8000 |
| `frontend` | Built from `frontend/Dockerfile` | 3000 |
| `postgres` | `postgres:16` | 5432 |

```
docker compose up --build
```

A named volume (`postgres_data`) persists the database across container restarts. The backend mounts `./backend/app` as a volume for live-reload during development.

### Production considerations

The Compose configuration is a development and evaluation baseline. Production deployments should additionally:

- Run a TLS-terminating reverse proxy (nginx, Caddy, a cloud load balancer) in front of both services
- Restrict access to admin paths at the reverse proxy or firewall layer
- Use a managed PostgreSQL service or a hardened self-hosted instance with backups and point-in-time recovery
- Pin Docker image digests to prevent unexpected base image changes
- Run containers as non-root users
- Store secrets in a secrets manager rather than a `.env` file on disk

---

## 9. Extension points

The architecture is designed so that capabilities beyond the OSS scope can be added as layers without modifying the core.

### Adding a new provider

1. Define a `ProviderConfig` instance in `services/provider.py` with the provider's URL, header builder, and usage extractor.
2. Define the model allowlist as a `frozenset[str]`.
3. Create a route handler in `routes/` that instantiates `PolicyEngine` with the new allowlist, calls `forward_request()` with the new config, and calls `persist_log()`.
4. Register the new router in `main.py`.

No other files change.

### Adding a new policy check

1. Write a function in `services/policy_engine.py` with the signature `(text: str) -> PolicyDecision | None`.
2. Add it to the `or` chain in `PolicyEngine.evaluate()` at the appropriate priority position.
3. Add test cases to `tests/test_policy_engine.py`.

No route handlers change.

### Extending the audit log schema

Add columns to `RequestLog` in `models/request_log.py` and corresponding parameters to `persist_log()`. SQLAlchemy's `create_all()` will add new columns on the next startup for a fresh database; operators with existing data will need a migration.

### Authentication overlay

An authentication dependency can be injected into any route using FastAPI's `Depends()` system without modifying the route body. A middleware approach is also viable. Neither requires changes to the policy engine, provider layer, or audit logger.

### Multi-tenancy overlay

A `tenant_id` field can be added to `RequestLog` and populated via an injected dependency in the same way. The OSS schema intentionally omits this column; adding it is a non-breaking extension.

---

## 10. OSS and enterprise boundary

The distinction between the OSS core and a hypothetical enterprise layer is architectural, not incidental.

**OSS core (this repository):**

- Provider-agnostic proxy forwarding
- Data-governance policy evaluation
- Metadata-only audit logging
- Read-only operational dashboard

**Out of scope for this repository:**

| Capability | Why it is out of scope |
|---|---|
| Caller authentication | Requires credential storage and rotation — a security surface that belongs in dedicated infrastructure, not a proxy |
| Multi-tenancy and isolation | Requires per-tenant configuration, data separation, and a management plane |
| RBAC and permission management | Requires an identity model and policy authoring UX |
| Billing and usage metering | Requires a commercial data model |
| Compliance reporting | Requires certified controls, audit trails with higher durability guarantees, and domain-specific knowledge |

These capabilities are implementable as extension layers using the injection points described in [Section 9](#9-extension-points). They are absent from this repository by design — not because they are technically difficult, but because including them would compromise the auditability, deployability, and trustworthiness of the OSS core.

---

## 11. Summary

LLMGuard Lite is a narrow, well-scoped piece of infrastructure. It does one thing end to end: intercept an outbound LLM API call, evaluate it against governance policies, forward it or block it, and record the decision.

The architecture reflects that scope:

- A small, typed Python codebase with a shallow dependency graph
- A single-table database schema that stores only decision metadata
- A provider abstraction that makes new integrations additive rather than invasive
- A policy engine structured for independent testability of each check
- An audit logger that degrades gracefully rather than introducing a hard dependency on database availability
- Clear extension points that allow enterprise capabilities to be layered on without modifying the core

The result is a codebase that is auditable by a single engineer in an afternoon, deployable with Docker Compose in minutes, and extensible without architectural renegotiation.
