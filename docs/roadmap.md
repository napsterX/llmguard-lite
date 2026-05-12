# Roadmap — LLMGuard Lite

This document describes where LLMGuard Lite is today, what is planned for upcoming releases, and what is explicitly out of scope for the open-source project. It is a living document — updated as community priorities become clearer and contributions land.

**Last updated:** May 2026

---

## Contents

1. [Roadmap purpose](#1-roadmap-purpose)
2. [Current MVP status](#2-current-mvp-status)
3. [v0.1 — MVP stabilisation](#3-v01--mvp-stabilisation)
4. [v0.2 — Provider and policy improvements](#4-v02--provider-and-policy-improvements)
5. [v0.3 — Observability and operator experience](#5-v03--observability-and-operator-experience)
6. [v0.4 — Deployment hardening](#6-v04--deployment-hardening)
7. [Future ideas](#7-future-ideas)
8. [Explicitly out of scope](#8-explicitly-out-of-scope)
9. [Contribution priorities](#9-contribution-priorities)
10. [Summary](#10-summary)

---

## 1. Roadmap purpose

This roadmap serves three audiences:

- **Contributors** — to understand which areas are most valuable to work on and avoid duplicating in-flight effort
- **Operators** — to plan around upcoming improvements and understand what to expect from each release
- **Evaluators** — to assess whether LLMGuard Lite's trajectory aligns with their governance needs

The roadmap is intentionally scoped to the open-source governance core. Items that belong in a commercial or enterprise layer are named explicitly in [Section 8](#8-explicitly-out-of-scope) so that the boundary is visible and unambiguous.

Version numbers are targets, not guarantees. Dates are not committed. Progress is driven by contributors and maintainers working in their available time.

---

## 2. Current MVP status

The current `main` branch represents a functional MVP. All items below are implemented and tested.

### What is working

| Capability | Status |
|---|---|
| Anthropic proxy (`/v1/proxy/anthropic/messages`) | Complete |
| OpenAI proxy (`/v1/proxy/openai/chat/completions`) | Complete |
| Model governance — allowlist per provider endpoint | Complete |
| Credential-format detection in prompt text | Complete |
| Personal-data identifier detection in prompt text | Complete |
| Content governance — irreversible-operation phrase detection | Complete |
| Token-budget guard | Complete |
| PostgreSQL audit log — metadata only, no prompt content | Complete |
| Provider abstraction layer (`ProviderConfig` dataclass) | Complete |
| Audit-log resilience — DB failure does not affect proxy response | Complete |
| Upstream error pass-through (4xx, 5xx from provider) | Complete |
| Timeout and connection-error handling (504, 502) | Complete |
| Read-only admin dashboard — stats and log table | Complete |
| Docker Compose deployment | Complete |
| Pytest suite — 70 tests, all I/O mocked | Complete |

### Known gaps in the MVP

| Gap | Planned in |
|---|---|
| Policy rules are hard-coded; changing them requires a code edit | v0.2 |
| Streaming responses (`stream: true`) are not proxied | v0.2 |
| No response-side policy scanning | v0.2 |
| No rate limiting | v0.3 |
| No `/metrics` endpoint for Prometheus | v0.3 |
| Admin endpoints have no access controls beyond network placement | v0.4 |
| No automated CI pipeline in the repository | v0.1 |
| Frontend uses placeholder data when the backend is unreachable; no explicit error state | v0.1 |

---

## 3. v0.1 — MVP stabilisation

**Goal:** make the existing MVP reliable, tested, and welcoming to first contributors before adding new features.

### Developer experience

- [ ] **GitHub Actions CI** — run `ruff format`, `ruff check`, and `pytest -v` on every pull request and push to `main`; fail the pipeline if any check does not pass
- [ ] **Pre-commit configuration** — provide a `.pre-commit-config.yaml` so contributors catch lint and format issues locally before pushing
- [ ] **Dependabot** — enable automated pull requests for `requirements.txt` and `package.json` dependency updates

### Frontend polish

- [ ] **Explicit error state** — display a clear message when the backend is unreachable rather than rendering empty data silently
- [ ] **Provider filter** — add a filter control to the log table so operators can view traffic for one provider at a time
- [ ] **Auto-refresh** — add a manual refresh button or a configurable polling interval to the dashboard; the current page requires a full reload to see new entries

### Documentation

- [ ] **`docs/architecture.md`** — complete ✓
- [ ] **`docs/roadmap.md`** — complete ✓
- [ ] **`CONTRIBUTING.md`** — complete ✓
- [ ] **`SECURITY.md`** — complete ✓
- [ ] **`CODE_OF_CONDUCT.md`** — complete ✓
- [ ] **`backend/.env.example`** — complete ✓
- [ ] **`LICENSE`** — verify MIT licence file is present and correctly dated
- [ ] **`CHANGELOG.md`** — start a changelog with the MVP entry; update with every tagged release

### Test coverage

- [ ] Achieve measurable coverage reporting — integrate `pytest-cov` and add a coverage badge to the README
- [ ] Add end-to-end smoke tests that run against a real Docker Compose stack in CI (separate from the unit suite)

---

## 4. v0.2 — Provider and policy improvements

**Goal:** make the policy engine configurable without code changes, add streaming support, and extend the provider set.

### Runtime-configurable policies

Currently, the model allowlist and content-governance phrase list are defined as constants in `policy_engine.py`. Changing them requires editing source code and redeploying.

- [ ] **Environment-variable allowlists** — read `ALLOWED_MODELS` from the environment as a comma-separated list; merge with or replace the hard-coded default
- [ ] **YAML policy configuration** — support an optional `policies.yaml` file that defines phrase lists, allowlists, and token limits; hot-reload on SIGHUP without a full restart
- [ ] **Per-endpoint allowlist overrides** — allow the Anthropic and OpenAI endpoints to carry independent model allowlists defined in configuration rather than code

### Streaming support

- [ ] **Server-sent events pass-through** — when a request includes `stream: true`, proxy the SSE response incrementally rather than buffering the full response
- [ ] **Streaming audit log** — log the final token counts from the `[DONE]` event rather than a buffered response body

### Policy engine improvements

- [ ] **Response-side scanning** — apply the credential-protection and personal-data policies to the upstream provider response before returning it to the caller; log and optionally block on violation
- [ ] **Configurable severity thresholds** — allow operators to configure which severity levels result in a block versus a log-only warning
- [ ] **Custom phrase lists** — support operator-defined phrase lists for content governance via the YAML config

### Additional providers

- [ ] **Provider contribution guide** — document exactly how to add a new provider (the `ProviderConfig` pattern) with a worked example
- [ ] **Community-contributed provider** — accept one well-tested community contribution for an additional provider (e.g. Google Gemini, Mistral, or Cohere) as a validation of the extension model

---

## 5. v0.3 — Observability and operator experience

**Goal:** give operators the metrics and tooling they need to run LLMGuard Lite in a shared environment with confidence.

### Metrics

- [ ] **`/metrics` endpoint** — expose a Prometheus-compatible metrics endpoint with the following gauges and counters:
  - `llmguard_requests_total` (labels: `provider`, `allowed`)
  - `llmguard_policy_blocks_total` (labels: `policy_name`, `severity`)
  - `llmguard_upstream_latency_ms` (histogram, labels: `provider`)
  - `llmguard_token_usage_total` (labels: `provider`, `direction: input|output`)
- [ ] **Grafana dashboard definition** — provide a reference `dashboard.json` that operators can import into an existing Grafana instance

### Dashboard improvements

- [ ] **Time-range filter** — allow the stats view to be scoped to a configurable window (last hour, last 24 hours, last 7 days)
- [ ] **Policy breakdown chart** — visualise the distribution of blocked requests by policy name
- [ ] **Token usage totals** — surface cumulative input and output token counts in the stats view

### Rate limiting

- [ ] **In-process sliding window** — implement a configurable request-rate limit (requests per minute per origin IP) without requiring an external dependency
- [ ] **Token-budget rate limiting** — limit the total estimated tokens proxied per origin per time window, in addition to per-request token limits
- [ ] **Rate-limit response** — return HTTP 429 with a `Retry-After` header when a limit is reached; log the event in the audit table

### Operational tooling

- [ ] **Log export** — add a `GET /admin/logs/export` endpoint that streams the audit log as newline-delimited JSON (NDJSON) for ingestion into external log platforms
- [ ] **Structured application logging** — replace plain-text log lines with JSON-structured output compatible with log aggregators such as Loki or CloudWatch

---

## 6. v0.4 — Deployment hardening

**Goal:** make LLMGuard Lite safer and easier to operate in shared and production environments.

### Admin endpoint protection

The admin endpoints are currently unauthenticated by design, relying on network-layer controls. This is appropriate for simple single-operator deployments but creates friction for teams that want a self-contained configuration.

- [ ] **Optional static token authentication** — support an `ADMIN_TOKEN` environment variable; when set, require `Authorization: Bearer <token>` on all `/admin/*` requests; when unset, behaviour is unchanged (no auth)
- [ ] **Document the trade-offs** — update `SECURITY.md` and the README with guidance on when the token option is appropriate versus a network-layer approach

### Container hardening

- [ ] **Non-root user** — update the backend `Dockerfile` to run as a non-root user
- [ ] **Read-only filesystem** — document a `docker compose` configuration that mounts the application directory as read-only, with explicit writable mounts only where needed
- [ ] **Image scanning** — add a container vulnerability scan step to CI using a tool such as Trivy

### Database

- [ ] **Alembic migrations** — introduce Alembic for schema management so that operators with existing data can apply changes incrementally rather than requiring a fresh database
- [ ] **Connection pool configuration** — expose SQLAlchemy connection pool settings (`pool_size`, `max_overflow`, `pool_timeout`) as environment variables for operators running under load
- [ ] **`sslmode` documentation** — document and test the `sslmode=require` configuration for PostgreSQL connections in the deployment guide

### Helm chart

- [ ] **Initial Helm chart** — provide a `helm/` directory with a chart that deploys the backend, frontend, and a PostgreSQL dependency; target compatibility with Kubernetes 1.27+
- [ ] **Helm values documentation** — document all configurable values with descriptions and defaults

---

## 7. Future ideas

Items in this section are not scheduled and have no assigned version. They represent directions the project could grow if community interest and contributions support them. All are subject to review against the OSS scope boundary.

| Idea | Description |
|---|---|
| **WebSocket support** | Proxy WebSocket-based LLM APIs in addition to REST |
| **Plugin system** | A defined interface for loading custom policy checks as Python packages without modifying the core |
| **Policy audit trail** | Track changes to policy configuration over time so operators can correlate behaviour changes with configuration changes |
| **OpenTelemetry tracing** | Emit distributed traces so LLMGuard Lite can be observed within an existing tracing pipeline |
| **Semantic caching** | Cache provider responses for semantically similar requests to reduce cost and latency |
| **Request replay** | Replay blocked or errored requests after a policy or configuration change for testing purposes |
| **Multi-region audit log** | Support writing audit records to multiple PostgreSQL instances or an external event stream for operators with data-residency requirements |

Community proposals for future directions are welcome in [GitHub Discussions](../../discussions).

---

## 8. Explicitly out of scope

The following capabilities are intentionally excluded from the LLMGuard Lite open-source roadmap. This boundary is a deliberate design choice, not a gap.

| Capability | Reason it is out of scope |
|---|---|
| **Tenant authentication and API key management** | Requires credential storage, rotation, and a management plane — a security surface that belongs in dedicated infrastructure rather than a governance proxy |
| **Multi-tenancy and tenant isolation** | Requires per-tenant configuration, data partitioning, and a management API; adds significant operational complexity that is disproportionate to the OSS use case |
| **Role-based access control (RBAC)** | Requires an identity model, permission authoring UX, and tight integration with an organisation's identity provider |
| **Billing and usage metering** | Requires a commercial data model and payment infrastructure |
| **Compliance certification packs** | SOC 2, HIPAA, GDPR, ISO 27001, and similar frameworks require certified controls, legal review, and domain-specific documentation that is beyond the scope of a community project |
| **AI model fine-tuning or evaluation** | Outside the proxy's functional domain |
| **Managed cloud offering** | Hosting, SLA commitments, and operational support are not part of the open-source project |

Contributions that implement the above will not be merged into this repository. If you are building an extension in these areas, the [extension points documented in the architecture](architecture.md#9-extension-points) are designed to support layering these capabilities on top of the OSS core without forking it.

---

## 9. Contribution priorities

If you are looking for a place to start, the following areas have the highest impact relative to effort and are well-suited to first-time contributors.

### High priority — most impactful right now

| Item | Version | Notes |
|---|---|---|
| GitHub Actions CI pipeline | v0.1 | Block, lint, test on every PR — foundational for accepting contributions safely |
| Frontend error state | v0.1 | One component, clear acceptance criteria, good starter issue |
| Environment-variable allowlist configuration | v0.2 | High operator value; builds on existing `config.py` and `policy_engine.py` patterns |
| Response-side policy scanning | v0.2 | Mirrors the existing request-side scanning; well-understood scope |
| `/metrics` Prometheus endpoint | v0.3 | Adds `prometheus-client` dependency and a new route; isolated change |

### Medium priority — valuable but more complex

| Item | Version | Notes |
|---|---|---|
| Streaming SSE pass-through | v0.2 | Requires understanding of async generators and SSE protocol |
| YAML policy configuration | v0.2 | Configuration schema design needs discussion before implementation |
| Rate limiting | v0.3 | Algorithm choice (token bucket vs. sliding window) warrants an issue discussion first |
| Alembic migrations | v0.4 | Requires care around the initial migration against an existing schema |

### Good for documentation contributors

| Item | Version | Notes |
|---|---|---|
| Provider contribution guide | v0.2 | Narrative documentation; no code required |
| Grafana dashboard definition | v0.3 | JSON authoring; no Python or TypeScript required |
| Deployment guide updates | v0.4 | Keeps pace with Helm and hardening work |

Before starting work on any item, check [GitHub Issues](../../issues) to see if it is already in progress. Opening an issue to discuss your approach before writing code avoids duplicated effort and increases the chance of a smooth review.

---

## 10. Summary

LLMGuard Lite has a working MVP: a policy-enforcing, auditing API proxy for Anthropic and OpenAI, covered by a 70-test suite and deployable in minutes via Docker Compose.

The roadmap follows a deliberate sequence:

1. **v0.1** — stabilise what exists: CI, error handling, coverage reporting, documentation
2. **v0.2** — make it configurable and extend the policy and provider surface
3. **v0.3** — give operators the metrics and controls they need for shared-environment use
4. **v0.4** — harden the deployment model for production confidence

Enterprise concerns — authentication, multi-tenancy, RBAC, billing, compliance — are out of scope by design and named explicitly as such. The architecture's extension points make them additive rather than requiring changes to the core.

The project welcomes contributors at every level. The highest-value starting points are listed in [Section 9](#9-contribution-priorities). If you are unsure where to begin, open an issue and ask.
