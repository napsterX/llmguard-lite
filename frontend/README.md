# LLMGuard Lite — Dashboard

The dashboard is a [Next.js 16](https://nextjs.org) application (App Router, React Server Components) that provides a read-only view of LLMGuard Lite proxy activity.

## What it shows

- **Stats overview** — total requests, allowed count, blocked count, average upstream latency
- **Recent requests** — a live table of the last 20 audit log entries with provider, model, status, triggered policy, and latency

The dashboard fetches data from the backend admin endpoints at render time. It has no client-side state and requires no authentication beyond whatever network-level controls the operator has placed on the backend.

## Running locally

```bash
cp .env.example .env.local   # safe default — no edit needed for local dev
npm install
npm run dev
# → http://localhost:3000
```

The backend must be running at `http://localhost:8000` (the default), or set `FRONTEND_API_BASE_URL` in `.env.local` to point elsewhere.

## Environment

| Variable | Default | Description |
|---|---|---|
| `FRONTEND_API_BASE_URL` | `http://localhost:8000` | Backend API base URL — resolved server-side only |

This variable is read exclusively by the Next.js server process, not the browser. No `NEXT_PUBLIC_` prefix is used because all data fetching is done in Server Components at render time.

## Stack

- Next.js 16 with App Router
- React 19 Server Components
- TypeScript
- Tailwind CSS v4

## Part of the larger project

This dashboard is one component of LLMGuard Lite. See the [root README](../README.md) for the full project overview, quickstart, and documentation index.
