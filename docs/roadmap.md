# Product Roadmap — LLMGuard Lite

**Last updated:** May 2026 · **Current release:** v1.0.0

---

## Contents

1. [Roadmap philosophy](#1-roadmap-philosophy)
2. [v1.0 — Current release](#2-v10--current-release)
3. [v1.1 — OSS stabilization](#3-v11--oss-stabilization)
4. [v1.2 — Configurable governance](#4-v12--configurable-governance)
5. [v1.3 — Operational hardening](#5-v13--operational-hardening)
6. [Future OSS considerations](#6-future-oss-considerations)
7. [Explicitly out of scope](#7-explicitly-out-of-scope)
8. [Enterprise boundary](#8-enterprise-boundary)

---

## 1. Roadmap philosophy

LLMGuard Lite is built on a simple premise: AI governance should be a default layer in every team's infrastructure stack, not a premium add-on. This roadmap reflects that conviction.

**Three principles govern every release decision:**

**Scope discipline.** Every proposed feature is evaluated against the question: *does this belong in a self-hosted governance proxy?* If the answer is "only in a managed, multi-tenant, or enterprise context," it does not ship in this repository. The [out-of-scope table](#7-explicitly-out-of-scope) makes those boundaries explicit and permanent.

**Operator confidence before feature velocity.** Stability, observability, and deployment clarity are prioritized over net-new capabilities. A governance proxy that operators cannot trust or understand creates more risk than it mitigates.

**Extension over fragmentation.** The provider abstraction and policy engine are designed to be extended by contributors and downstream consumers without forking the core. Commercial or enterprise layers build on top of this foundation — they do not require changes to it.

**On versioning:** milestones represent development targets, not contractual commitments. There are no attached dates. Progress depends on maintainer capacity and community contributions. Capabilities may shift between versions as priorities are refined through real-world operator feedback.

---

## 2. v1.0 — Current release

The v1.0 release is a production-capable governance proxy covering the full request lifecycle: policy evaluation, upstream forwarding, and structured audit logging.

### Shipped capabilities

| Capability | Notes |
|---|---|
| Anthropic proxy — `POST /v1/proxy/anthropic/messages` | Full request/response cycle with error pass-through |
| OpenAI proxy — `POST /v1/proxy/openai/chat/completions` | Consistent behavior with Anthropic endpoint |
| Model governance — provider-scoped allowlists | Hard-coded defaults; configurable in v1.2 |
| Credential-format detection | Common API key and token patterns in prompt text |
| PII detection | Email addresses, payment card numbers, national identifiers, phone numbers |
| Destructive-intent detection | Phrases associated with irreversible data and infrastructure operations |
| Token-budget enforcement | Configurable per-request token ceiling (default: 8,000) |
| PostgreSQL audit log | Metadata only — no prompt content stored |
| Provider abstraction layer | `ProviderConfig` dataclass; new providers require one constant and one route |
| Audit-log resilience | DB failure does not affect the proxy response path |
| Upstream error handling | 4xx, 5xx, timeout (504), and connection error (502) handled uniformly |
| Read-only admin dashboard | Stats overview and paginated request log; Next.js Server Components |
| Docker Compose deployment | Single `docker compose up --build` brings up all three services |
| pytest suite — 70 tests | All I/O mocked; no live database or network connection required |

### Known limitations in v1.0

| Limitation | Addressed in |
|---|---|
| Policy rules are hard-coded; changes require a code edit and redeploy | v1.2 |
| Streaming responses (`stream: true`) are not proxied | v1.2 |
| No response-side policy scanning | v1.2 |
| No request rate limiting | v1.3 |
| No Prometheus metrics endpoint | v1.3 |
| No automated CI in the repository | v1.1 |
| Admin endpoints rely on network-layer access controls only | v1.3 |

---

## 3. v1.1 — OSS Stabilization

**Objective:** Harden the contributor experience and establish the operational baseline required before the project can responsibly accept external contributions at scale. No new governance capabilities ship in this milestone.

### CI and automation

- [ ] **GitHub Actions pipeline** — run `ruff format --check`, `ruff check`, and `pytest -v` on every pull request and push to `main`; pipeline failure blocks merge
- [ ] **Pre-commit configuration** — provide `.pre-commit-config.yaml` so contributors catch lint and format violations before they reach CI
- [ ] **Dependabot** — enable automated dependency PRs for both `requirements.txt` and `package.json`
- [ ] **Coverage reporting** — integrate `pytest-cov` and surface a coverage badge on the README; establish 90% line coverage as a merge gate for the backend

### Issue and PR infrastructure

- [ ] **Bug report template** — `.github/ISSUE_TEMPLATE/bug_report.md` with environment, reproduction steps, and expected/actual behavior sections
- [ ] **Feature request template** — `.github/ISSUE_TEMPLATE/feature_request.md` with problem statement, proposed solution, and alternatives considered
- [ ] **Pull request template** — checklist covering test coverage, `pytest -v` pass, documentation updates, and scope alignment
- [ ] **`CHANGELOG.md`** — initialize with the v1.0 entry; all subsequent tagged releases update this file before tagging

### Dashboard polish

- [ ] **Backend-unreachable state** — display a clear, actionable error banner when the admin API is unavailable (in place of silent empty-state rendering)
- [ ] **Provider filter** — add a filter control to the request log so operators can isolate traffic by provider
- [ ] **Manual refresh** — add a refresh control; the current page requires a full browser reload to surface new entries

### Documentation completeness

- [ ] **Architecture doc** — complete (`docs/architecture.md`)
- [ ] **Contributor guide** — complete (`CONTRIBUTING.md`)
- [ ] **Security policy** — complete (`SECURITY.md`)
- [ ] **Code of conduct** — complete (`CODE_OF_CONDUCT.md`)
- [ ] **Provider extension walkthrough** — document the `ProviderConfig` pattern end-to-end with a worked example; publish in `docs/`

---

## 4. v1.2 — Configurable Governance

**Objective:** Decouple policy configuration from source code. Operators should be able to define governance rules through configuration — not code changes — and extend the system to additional providers without forking.

### Runtime-configurable policies

The current release encodes model allowlists and phrase lists as constants in `policy_engine.py`. v1.2 externalizes this configuration while preserving the existing defaults for operators who make no configuration changes.

- [ ] **Environment-variable allowlists** — read `ALLOWED_MODELS_ANTHROPIC` and `ALLOWED_MODELS_OPENAI` from the environment as comma-separated lists; these override or extend the hard-coded defaults
- [ ] **YAML policy configuration** — support an optional `policies.yaml` loaded at startup; defines phrase lists, model allowlists, and token limits; validated against a published schema on load
- [ ] **Hot-reload on SIGHUP** — reload `policies.yaml` without a full process restart; emit a structured log entry confirming the reload and any validation errors
- [ ] **Per-severity action configuration** — allow operators to configure per-policy whether a violation results in a block (HTTP 400) or a log-only warning (request continues to upstream)

### Streaming support

- [ ] **SSE pass-through** — proxy `stream: true` requests by forwarding the server-sent event stream incrementally rather than buffering the full response
- [ ] **Streaming audit log** — derive token counts from the final `[DONE]` event; log them consistently with non-streaming requests

### Response-side scanning

- [ ] **Downstream policy evaluation** — apply credential-protection and PII policies to the upstream provider response before returning it to the caller; log and optionally block on violation
- [ ] **Response scan audit fields** — extend the `RequestLog` schema with a `response_policy_name` column and the corresponding Alembic migration

### Provider ecosystem

- [ ] **Community-contributed provider** — accept one well-tested community contribution for an additional provider (candidates: Google Gemini, Mistral, Cohere) as a validation of the extension model
- [ ] **Provider registry documentation** — enumerate supported providers, their endpoint schemas, and the `ProviderConfig` fields required to add a new one

---

## 5. v1.3 — Operational Hardening

**Objective:** Equip teams running LLMGuard Lite in shared, multi-application, or regulated environments with the operational controls they need — metrics, rate limiting, structured logs, and a hardened deployment model.

### Observability

- [ ] **Prometheus metrics endpoint** — expose `GET /metrics` with the following signals:

  | Metric | Type | Labels |
  |---|---|---|
  | `llmguard_requests_total` | Counter | `provider`, `allowed` |
  | `llmguard_policy_blocks_total` | Counter | `policy_name`, `severity` |
  | `llmguard_upstream_latency_ms` | Histogram | `provider` |
  | `llmguard_token_usage_total` | Counter | `provider`, `direction` |

- [ ] **Reference Grafana dashboard** — publish a `grafana/dashboard.json` importable into any Grafana instance; panels for request volume, block rate by policy, and upstream latency percentiles

### Rate limiting

- [ ] **Per-origin sliding-window rate limit** — configurable requests-per-minute ceiling per origin IP; no external dependency required
- [ ] **Token-budget rate limit** — limit cumulative estimated tokens proxied per origin per time window, separate from the per-request token ceiling
- [ ] **HTTP 429 with `Retry-After`** — return a well-formed rate-limit response and log the event in the audit table

### Structured logging

- [ ] **JSON application logs** — replace plain-text log lines with structured JSON output (timestamp, level, message, context fields); compatible with Loki, CloudWatch, and Datadog log agents
- [ ] **Audit log export endpoint** — `GET /admin/logs/export` streams the audit log as newline-delimited JSON (NDJSON) for ingestion into external platforms

### Deployment hardening

- [ ] **Non-root container** — update the backend `Dockerfile` to run as a non-root user; `USER` instruction added with a dedicated service account
- [ ] **Container image scanning** — integrate Trivy into the CI pipeline; fail the build on HIGH or CRITICAL CVEs in the production image layers
- [ ] **Optional admin token authentication** — support an `ADMIN_TOKEN` environment variable; when set, require `Authorization: Bearer <token>` on all `/admin/*` requests; behavior is unchanged when unset
- [ ] **Database connection pool configuration** — expose `POOL_SIZE`, `MAX_OVERFLOW`, and `POOL_TIMEOUT` as environment variables for operators running under sustained load
- [ ] **Alembic schema migrations** — introduce Alembic for incremental schema management; provide a documented upgrade path for operators with existing data

### Kubernetes

- [ ] **Helm chart** — initial `helm/` directory targeting Kubernetes 1.27+; deploys backend, frontend, and a PostgreSQL dependency with sane production defaults
- [ ] **Helm values reference** — document all configurable values with types, defaults, and descriptions

---

## 6. Future OSS Considerations

The items below are not scheduled and carry no version assignment. They represent directions the project could develop given sufficient community interest and contribution. All remain subject to evaluation against the scope principles in [Section 1](#1-roadmap-philosophy).

| Direction | Description |
|---|---|
| **Expanded provider ecosystem** | Additional LLM providers beyond Anthropic and OpenAI; standardized provider contribution process |
| **OpenTelemetry tracing** | Distributed trace emission for integration with existing observability pipelines |
| **Semantic request deduplication** | Cache governance decisions for near-identical requests to reduce upstream latency |
| **Policy audit trail** | Versioned record of policy configuration changes correlated with behavioral changes in the audit log |
| **WebSocket proxy** | Support for WebSocket-based LLM APIs alongside REST |
| **Plugin interface** | Defined Python extension point for loading custom policy checks as installable packages |
| **Enhanced dashboard analytics** | Time-range filtering, policy breakdown charts, and token usage trends in the admin UI |
| **Request replay tooling** | Replay blocked or errored requests against a modified policy configuration for validation |

Community proposals for future directions belong in [GitHub Discussions](../../discussions). Open a discussion before opening a pull request for any unscheduled item.

---

## 7. Explicitly Out of Scope

The following capabilities are intentionally and permanently excluded from the LLMGuard Lite open-source roadmap. This is a deliberate architectural boundary, not a gap in ambition.

| Capability | Reason |
|---|---|
| **Multi-tenancy and tenant isolation** | Requires per-tenant configuration, data partitioning, and a management plane — operational complexity that is disproportionate to the self-hosted use case |
| **API key management and rotation** | Credential lifecycle management belongs in dedicated secrets infrastructure, not a governance proxy |
| **Role-based access control (RBAC)** | Requires an identity model, permission authoring, and integration with an organization's identity provider |
| **Billing and usage metering** | Requires a commercial data model and payment infrastructure with no role in a governance-only proxy |
| **Compliance certification packs** | SOC 2, HIPAA, GDPR, and ISO 27001 controls require certified audits, legal review, and domain-specific tooling beyond the scope of a community project |
| **Managed cloud offering** | Hosting, SLAs, and operational support are outside the OSS project's scope |
| **LLM fine-tuning or evaluation** | Outside the functional domain of a governance proxy |

Contributions implementing the above will not be merged. If you are building capabilities in these areas, the [extension points documented in the architecture guide](architecture.md#extension-points) are specifically designed to support layering enterprise functionality on top of the OSS core without requiring a fork.

---

## 8. Enterprise Boundary

LLMGuard Lite is the open-source governance core. It is designed as a stable foundation — not a feature-complete enterprise platform.

Advanced capabilities such as tenant isolation, RBAC, compliance reporting, and managed deployment are intentionally absent from this repository. They represent a distinct product surface with distinct operational, security, and commercial requirements. Where those capabilities exist or are developed, they are built on top of this foundation rather than merged into it.

This boundary is an asset, not a limitation. It means:

- The OSS codebase remains auditable, understandable, and contributor-accessible
- Operators deploying LLMGuard Lite receive a purpose-built tool with a clear and bounded attack surface
- Enterprise extensions can be developed, versioned, and operated independently without destabilizing the community edition

If you are evaluating LLMGuard Lite for an enterprise context that requires capabilities listed in [Section 7](#7-explicitly-out-of-scope), open a [GitHub Discussion](../../discussions) to explore what an integration or extension path would look like.
