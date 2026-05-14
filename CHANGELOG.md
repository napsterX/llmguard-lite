# Changelog

All notable changes to LLMGuard Lite are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-05-14

Initial public release.

### Added

- **Anthropic proxy** — `POST /v1/proxy/anthropic/messages` forwards requests to the Anthropic Messages API after policy evaluation
- **OpenAI proxy** — `POST /v1/proxy/openai/chat/completions` with identical policy enforcement behaviour
- **Provider abstraction** — `ProviderConfig` dataclass and `forward_request()` enable new providers to be added with a single constant and a route handler
- **Policy engine** — five sequentially evaluated policies; first violation short-circuits further evaluation:
  - `model_allowlist` — blocks requests targeting models outside the configured allowlist
  - `secret_detection` — detects common API-key and authentication-token formats in prompt text
  - `pii_detection` — detects email addresses, payment card numbers, national identifiers, and phone numbers
  - `destructive_intent` — detects phrases associated with irreversible data or infrastructure operations
  - `token_guard` — blocks prompts whose estimated token count exceeds the configured limit (default: 8 000)
- **PostgreSQL audit log** — `RequestLog` table records policy decision metadata; raw prompt content is never stored
- **Audit resilience** — `persist_log()` wraps every DB write in try/except; a database failure does not affect the proxy response
- **Admin API** — `GET /admin/stats` and `GET /admin/logs` for read-only operational visibility
- **Next.js dashboard** — server-side rendered stats overview and request log table; no client-side state
- **Docker Compose deployment** — single `docker compose up --build` starts backend, frontend, and PostgreSQL
- **pytest suite** — 70 tests covering all policies, proxy routes, admin endpoints, and error paths; no live database or network required
- **GitHub Actions CI** — lint (`ruff check`), test (`pytest -v`), and frontend build on every pull request and push to `main`
- **OSS documentation** — `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `docs/architecture.md`, `docs/roadmap.md`

[1.0.0]: https://github.com/napsterX/llmguard-lite/releases/tag/v1.0.0
