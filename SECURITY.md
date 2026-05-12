# Security Policy

LLMGuard Lite is open-source governance infrastructure for AI API traffic. This document describes how the project handles vulnerability reports, what operators can expect from maintainers, and what self-hosting teams should know before putting LLMGuard Lite into production.

---

## Contents

1. [Security overview](#1-security-overview)
2. [Supported versions](#2-supported-versions)
3. [Reporting a vulnerability](#3-reporting-a-vulnerability)
4. [Disclosure expectations](#4-disclosure-expectations)
5. [Response commitments](#5-response-commitments)
6. [Self-hosting security recommendations](#6-self-hosting-security-recommendations)
7. [Dependency and security patching policy](#7-dependency-and-security-patching-policy)
8. [Scope limitations](#8-scope-limitations)
9. [Safe harbor statement](#9-safe-harbor-statement)
10. [Contact process](#10-contact-process)

---

## 1. Security overview

LLMGuard Lite is a **data-governance proxy** — it intercepts requests from applications to AI providers, enforces configurable policies, and writes a structured audit log. It is not a firewall, not an authentication broker, and not a certified compliance platform.

**What the software is responsible for:**

- Evaluating data-governance policies consistently and as documented
- Forwarding only requests that pass all configured policy checks
- Writing audit records that contain the policy decision and no raw prompt content
- Handling upstream provider errors without leaking configuration details to callers

**What the software is explicitly not responsible for:**

- Network-level access control to the proxy or its admin endpoints (that is the operator's responsibility)
- End-to-end encryption of traffic between the caller and the proxy (use TLS termination at the load balancer or reverse proxy)
- Authentication and authorisation of callers (not present in the community edition — see [Scope limitations](#8-scope-limitations))
- Guaranteeing that all possible forms of sensitive data are detected — the policy engine uses pattern matching and phrase lists, not a trained classifier

Operators must understand these boundaries before deploying LLMGuard Lite in any environment that handles regulated or sensitive data.

---

## 2. Supported versions

Security fixes are applied to the `main` branch. The project does not maintain multiple long-term-support branches at this stage of its development.

| Version | Status |
|---|---|
| `main` (latest) | Actively maintained — security fixes applied |
| Tagged releases (older) | Best-effort — critical fixes backported where the risk/complexity tradeoff is justified |
| Forks and modified distributions | Not supported |

Operators running a tagged release are encouraged to upgrade to `main` promptly when a security advisory is published. Release notes will clearly identify which commits address security issues.

---

## 3. Reporting a vulnerability

**Do not report potential security issues through public GitHub Issues, pull requests, or discussion threads.** Public disclosure before a fix is available puts every operator running the software at risk.

**To report privately:**

Send a message to **security@hachira.com**. Use the subject line: `[LLMGuard Lite] Security Report`.

If you are unsure whether an issue qualifies as a security concern, err on the side of reporting it privately. A false alarm is always preferable to delayed disclosure of a real issue.

**What to include in your report:**

| Field | Guidance |
|---|---|
| Affected component | Which file, endpoint, or service is involved |
| Description | Plain-language description of the issue and why it matters |
| Conditions | Configuration or request conditions under which the issue occurs |
| Potential impact | What data or behaviour could be affected |
| Suggested fix | If you have one — not required |

You do not need a working demonstration. A clear, reproducible description is sufficient for triage.

---

## 4. Disclosure expectations

LLMGuard Lite follows a **coordinated disclosure** model:

1. The reporter submits details privately.
2. Maintainers acknowledge, triage, and confirm the issue.
3. A fix is developed and reviewed on a private branch.
4. A patched release is published to `main`.
5. A GitHub Security Advisory is created with full details.
6. The reporter is credited by name or handle, or anonymously if preferred.

We ask reporters to withhold public disclosure until step 4 is complete. In return, we commit to working efficiently and keeping the disclosure window as short as possible. For issues affecting data confidentiality or proxy correctness, the target window is **14 days or fewer** from confirmed triage to published patch.

If a fix requires more time — for example, because a coordinated upstream dependency patch is needed — the reporter will be kept informed of progress and an updated timeline will be agreed on.

---

## 5. Response commitments

| Milestone | Target |
|---|---|
| Initial acknowledgement | Within 48 hours of report receipt |
| Triage and confirmation | Within 5 business days |
| Status update if fix is delayed | Every 7 days from confirmation |
| Patch publication (high severity) | Within 14 days of confirmed triage |
| Patch publication (medium/low severity) | Best-effort, typically within 30 days |
| Security advisory publication | Same day as patch publication |

Severity is assessed using the following informal scale:

| Severity | Definition |
|---|---|
| **High** | A governance policy does not behave as documented, or the audit log records content it is documented not to record |
| **Medium** | A configuration error in the software leads to an insecure default that is not clearly documented |
| **Low** | A hardening improvement with no direct impact on documented behaviour |

---

## 6. Self-hosting security recommendations

LLMGuard Lite is designed for **self-hosted deployments** behind a trusted network boundary. These recommendations apply to any production or shared-environment deployment.

### Network access control

The admin endpoints (`/admin/stats`, `/admin/logs`) carry no built-in authentication. Before exposing the proxy to any network, restrict access to admin paths at the infrastructure layer:

- **Reverse proxy:** configure nginx, Caddy, or Traefik to require HTTP basic authentication or to allow admin paths only from trusted source IPs
- **Cloud firewall:** limit inbound access on port 8000 to known application CIDR ranges
- **Zero-trust access:** tools such as Cloudflare Access or a VPN gateway can front the admin UI without changes to LLMGuard Lite itself

The proxy endpoints (`/v1/proxy/*`) should similarly be restricted to known callers wherever possible.

### TLS

Run a TLS-terminating reverse proxy (nginx, Caddy, a cloud load balancer) in front of LLMGuard Lite. Do not expose the Uvicorn process directly to the public internet over plain HTTP.

### Secret management

- Store provider API keys and `DATABASE_URL` in environment variables or a secrets manager — never in a committed file
- The `.env` file is listed in `.gitignore`; verify this before cloning into a CI/CD environment
- Rotate provider keys immediately if you suspect they have been exposed

### Database

- Use a dedicated PostgreSQL user with `INSERT` and `SELECT` permissions on the `request_logs` table only — the application does not need `DROP`, `ALTER`, or cross-database access
- Enable PostgreSQL connection encryption (`sslmode=require` in `DATABASE_URL`)
- Take regular backups; the audit log is your primary record of proxy activity

### Container hardening

If using the provided Dockerfile:

- Run the container as a non-root user (the upstream `python:3.11-slim` base image supports this with `USER`)
- Pin base image digests in production builds to prevent unexpected upstream changes
- Scan images with a container vulnerability scanner before deployment

### Logging

LLMGuard Lite writes the policy decision category to the audit log, not the request content. Review your reverse proxy and container orchestrator logs to ensure they are not separately capturing full request bodies, which could include content the governance layer is designed to protect.

---

## 7. Dependency and security patching policy

**Python dependencies** (`backend/requirements.txt`)

- Dependencies are unpinned in the repository to allow operators to use the latest compatible versions
- The maintainers monitor PyPI advisories and the GitHub Dependabot advisory database
- When a CVE is published against a direct or transitive dependency, the project targets a patch within **7 days** for high-severity issues and **30 days** for medium/low

**Node.js dependencies** (`frontend/package.json`)

- The same monitoring and timeline commitments apply
- `npm audit` should be run locally before production frontend builds

**Operators** are responsible for running `pip install -r requirements.txt --upgrade` and `npm audit fix` on their own deployment schedule. Pinning dependencies in a production deployment is recommended; review the advisory database when upgrading.

---

## 8. Scope limitations

This section is explicit about what LLMGuard Lite does and does not do, so that operators can make informed deployment decisions.

### What LLMGuard Lite is

LLMGuard Lite is a **community-edition data-governance proxy**. It provides:

- Pattern-based policy evaluation on outbound LLM requests
- A structured audit log of every proxy decision
- A read-only dashboard for reviewing traffic statistics and log entries
- A clean extension surface for teams that want to build additional controls on top

### What LLMGuard Lite is not

| Claim | Reality |
|---|---|
| Enterprise compliance platform | LLMGuard Lite is not certified under any compliance framework (SOC 2, HIPAA, GDPR, ISO 27001, etc.). Teams with formal compliance obligations must evaluate it against their specific requirements. |
| Complete data-loss prevention | The policy engine uses regular expressions and phrase lists. It will not detect every possible form of sensitive data, and it does not apply machine-learning classification. Treat it as one control layer, not the only one. |
| Authentication and access control system | The community edition has no built-in caller authentication. Operators must supply this at the network or infrastructure layer. |
| Audit system of record | The audit log is a best-effort write; database failures are caught and logged but do not halt the proxy. For regulated audit requirements, pair LLMGuard Lite with an independent, high-durability log pipeline. |
| Multi-tenant platform | The community edition has no tenant isolation. All requests flow through a single policy configuration and a shared audit log. |

Teams evaluating LLMGuard Lite for regulated environments should treat the above limitations as deployment requirements to be addressed through complementary controls, not as defects to be fixed by the software.

---

## 9. Safe harbor statement

LLMGuard Lite welcomes good-faith security research. If you conduct security research on your own deployment of LLMGuard Lite and discover a potential issue, we will not pursue legal action for that research provided that:

- You report the issue privately following the process in [Section 3](#3-reporting-a-vulnerability) before any public disclosure
- You conduct research only against infrastructure you own or have explicit written permission to test
- You do not access, modify, or retain data belonging to other users or deployments
- You do not conduct tests that degrade service availability for any other party
- You act in good faith with the intent of improving software security

This statement applies to the software and its maintainers only. It does not extend to any third-party infrastructure, hosting providers, or AI provider APIs that LLMGuard Lite communicates with.

---

## 10. Contact process

| Purpose | Channel |
|---|---|
| Security vulnerability reports | **security@your-org.example** (private, monitored) |
| General bugs and feature requests | [GitHub Issues](../../issues) (public) |
| Usage and integration questions | [GitHub Discussions](../../discussions) (public) |

When emailing the security address, use the subject line `[LLMGuard Lite] Security Report` so that the message is correctly routed. PGP-encrypted submissions are welcome; publish a request in the issue tracker if you would like a public key.

Response times follow the commitments in [Section 5](#5-response-commitments). If you have not received an acknowledgement within 48 hours, send a follow-up to the same address. Do not open a public GitHub Issue to follow up on a security report.
