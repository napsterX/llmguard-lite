# Contributing to LLMGuard Lite

LLMGuard Lite is open-source infrastructure for AI governance. Every contribution — whether a bug fix, a new policy check, improved documentation, or a test case — directly improves the data-governance posture of every team that runs it.

This document is the single source of truth for how to contribute. Read it once before opening your first pull request.

---

## Contents

1. [Development environment setup](#1-development-environment-setup)
2. [Running services locally](#2-running-services-locally)
3. [Docker workflow](#3-docker-workflow)
4. [Test execution requirements](#4-test-execution-requirements)
5. [Coding standards](#5-coding-standards)
6. [Commit and pull request process](#6-commit-and-pull-request-process)
7. [Reporting bugs](#7-reporting-bugs)
8. [Feature requests](#8-feature-requests)
9. [Community expectations](#9-community-expectations)
10. [Scope boundaries](#10-scope-boundaries)

---

## 1. Development environment setup

**Prerequisites**

| Tool | Minimum version |
|---|---|
| Python | 3.9 |
| Node.js | 20 |
| PostgreSQL | 14 (or Docker) |
| Git | Any recent version |

**Clone and install**

```bash
git clone https://github.com/napsterX/llmguard-lite
cd llmguard-lite
```

Backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `backend/.env` and fill in `DATABASE_URL` and any provider API keys you want to test against. Provider keys are not required to run the test suite.

Frontend:

```bash
cd frontend
npm install
```

---

## 2. Running services locally

Start a PostgreSQL instance via Docker (easiest) or point `DATABASE_URL` at an existing local installation:

```bash
# From the repository root — starts only the database
docker compose up postgres -d
```

Then start each service in its own terminal:

```bash
# Terminal 1 — backend (from backend/)
source venv/bin/activate
uvicorn app.main:app --reload
# Listening on http://localhost:8000
```

```bash
# Terminal 2 — frontend (from frontend/)
npm run dev
# Listening on http://localhost:3000
```

Verify the backend is healthy:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

The database schema is created automatically on first startup. No migration step is needed for a fresh install.

---

## 3. Docker workflow

To build and run the full stack — backend, frontend, and PostgreSQL — in containers:

```bash
# From the repository root
cp backend/.env.example backend/.env   # add your provider keys
docker compose up --build
```

| Service | URL |
|---|---|
| Proxy API | http://localhost:8000 |
| Dashboard | http://localhost:3000 |
| PostgreSQL | localhost:5432 |

Iterate on backend code with live reload:

```bash
# Start only the database and frontend in Docker;
# run the backend locally for faster iteration
docker compose up postgres frontend -d
cd backend && uvicorn app.main:app --reload
```

Tear everything down, including the named volume:

```bash
docker compose down -v
```

---

## 4. Test execution requirements

The test suite runs entirely without a live database or network connection. All I/O is replaced by mocks through FastAPI dependency overrides and `unittest.mock.patch`.

```bash
cd backend
source venv/bin/activate
pytest -v
```

Expected result: **70 passed**.

**Requirements before submitting a pull request:**

- All 70 existing tests must pass locally with no modifications.
- New features require tests covering the expected behaviour and at least one edge case.
- Bug fixes require a regression test that fails on `main` and passes after your fix.
- All test fixtures must use non-operational placeholder values. Do not include realistic credentials, personal identifiers, or any data that resembles real user input.

**Test layout:**

| File | Scope |
|---|---|
| `tests/test_proxy.py` | Anthropic proxy — policy decisions, forwarding, logging, error envelopes |
| `tests/test_openai_proxy.py` | OpenAI proxy — equivalent case set for the OpenAI endpoint |
| `tests/test_policy_engine.py` | PolicyEngine unit tests — one case per policy type and edge case |
| `tests/test_admin.py` | Admin stats and log endpoints |
| `tests/test_health.py` | Health check |

---

## 5. Coding standards

### Python

- **Formatter:** [Ruff](https://docs.astral.sh/ruff/) — run `ruff format .` before committing
- **Linter:** `ruff check .` — all warnings must be resolved, not suppressed
- **Type annotations:** required on all public functions and methods; avoid `Any` where a concrete type is feasible
- **Comments:** explain *why*, not *what* — well-named identifiers already describe what code does; reserve comments for non-obvious constraints, invariants, or workarounds
- **Docstrings:** a one-line summary is sufficient for public classes; multi-paragraph docstrings add noise without value in a codebase of this size

### TypeScript / React

- **Formatter:** Prettier via `npm run lint`
- **Components:** Server Components by default; add `"use client"` only when a browser API is explicitly required
- **Data fetching:** belongs in page-level `async` Server Components; avoid `useEffect` for data that can be fetched at render time

### General

- Prefer editing existing files over creating new ones
- Do not add error handling for conditions that cannot occur; trust internal guarantees
- Do not introduce backwards-compatibility shims when you can simply update the calling code
- Keep pull requests focused — one logical change per PR is easier to review and easier to revert if needed

---

## 6. Commit and pull request process

### Branch naming

| Prefix | Purpose |
|---|---|
| `feat/` | New capability |
| `fix/` | Bug correction |
| `docs/` | Documentation only |
| `test/` | Test additions or improvements |
| `refactor/` | Code change with no functional effect |
| `chore/` | Dependency updates, build tooling |

Use lowercase, hyphen-separated names: `feat/configurable-token-limit`, `fix/empty-response-body`, `docs/architecture-overview`.

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary, present tense, no trailing period>

[optional body — explain the why, not the what]
```

Examples from this codebase:

```
feat(policy): add content-governance check for irreversible-operation phrases
fix(proxy): handle empty upstream response body without raising KeyError
test(admin): cover provider filter query parameter on GET /admin/logs
chore(deps): pin httpx to 0.27 for Python 3.9 compatibility
```

### Pull requests

Open pull requests against `main`. The description must answer three questions:

1. **What problem does this solve?**
2. **How did you test it?**
3. **Is there follow-up work that is intentionally out of scope for this PR?**

A maintainer will review within a few business days. Expect feedback — iteration is normal and expected, not a rejection.

**Checklist before marking a PR ready for review:**

- [ ] `pytest -v` passes locally (70 tests)
- [ ] `ruff format .` and `ruff check .` pass with no suppressions
- [ ] New behaviour is covered by tests
- [ ] Documentation is updated if the public interface changed
- [ ] No real credentials, personal data, or sensitive values appear anywhere in the diff

---

## 7. Reporting bugs

Search [existing issues](../../issues) before opening a new one to avoid duplicates.

**A complete bug report includes:**

- Git commit SHA or release tag
- Operating system, Python version, and Node version
- Exact steps to reproduce from a clean state
- What you expected to happen and what actually happened
- Relevant log output — scrub any credentials, personal data, or internal hostnames before pasting

**Security-related issues must not be reported in public issues.** Follow the private disclosure process described in [SECURITY.md](SECURITY.md). Public disclosure before a patch is available harms every user of the project.

---

## 8. Feature requests

Open a [GitHub Issue](../../issues/new) with the label `enhancement`.

Structure your request around three points:

1. **The problem** — describe the situation where the current behaviour is insufficient
2. **The proposed solution** — describe what you want to happen, not just that you want it
3. **Alternatives** — what else did you consider, and why did you set it aside

Large changes benefit from discussion before implementation. Opening an issue first means you get feedback on the direction before investing time in the code.

---

## 9. Community expectations

LLMGuard Lite follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). The short version: treat everyone with respect, engage with ideas rather than people, and assume good intent.

Maintainers will close issues and pull requests that are disrespectful, off-topic, or clearly outside the project scope — without extended discussion.

We value:

- **Clarity** — a concise, well-explained contribution is more useful than a large, unclear one
- **Rigour** — governance infrastructure must be correct; untested contributions will not be merged
- **Restraint** — adding less and doing it well is better than adding more and doing it halfway
- **Transparency** — if you are uncertain about an approach, ask in the issue before writing code

---

## 10. Scope boundaries

Understanding what belongs in this repository saves everyone time.

**In scope:**

- Proxy forwarding and upstream error handling
- Data-governance policy evaluation and policy configuration
- Audit logging and log retention model
- Provider abstraction (adding new LLM providers)
- Read-only admin dashboard

**Out of scope for this repository:**

- Tenant isolation and per-tenant API key management
- Role-based access control and permission systems
- Billing, usage metering, and quota enforcement
- Compliance-report generation
- Authentication middleware

Contributions in the out-of-scope categories belong in a separate project that extends LLMGuard Lite rather than inside this repository. If you are unsure whether an idea is in scope, open an issue and ask before writing any code.
