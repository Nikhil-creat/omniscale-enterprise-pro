<div align="center">

# OmniScale Enterprise Pro

**A multi-tenant AI SaaS platform with autonomous agentic routing, computer vision, RAG, metered billing, and full observability.**

[![CI/CD](https://img.shields.io/github/actions/workflow/status/Nikhil-creat/omniscale-enterprise-pro/ci-cd.yml?branch=main&label=CI%2FCD&style=flat-square)](https://github.com/Nikhil-creat/omniscale-enterprise-pro/actions)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org/)

[**Live project page →**](https://nikhil-creat.github.io/omniscale-enterprise-pro/) · [Quick start](#quick-start-docker) · [Architecture](#architecture) · [API reference](#api-reference)

</div>

---

## What this is

OmniScale is a reference-grade, multi-tenant AI SaaS backend and dashboard. Every request is
handled by an **autonomous agent router** that decides — per call — whether to answer from a
user's uploaded documents (RAG), analyze an uploaded image (CNN), or respond directly from an
LLM (chat). Around that core sits everything a real product needs to ship: auth, tiered rate
limiting, async background processing, Stripe billing, migrations, and observability.

It's built as a portfolio-grade demonstration of production system design, not a toy demo —
see [Scope & honesty](#scope--what-still-needs-hardening) for exactly where the line between
"solid" and "needs your attention" sits.

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Quick start (Docker)](#quick-start-docker)
- [Local development](#local-development)
- [API reference](#api-reference)
- [Testing](#testing)
- [Billing model](#billing-model)
- [Scope & what still needs hardening](#scope--what-still-needs-hardening)
- [Project structure](#project-structure)
- [License](#license)

## Features

| Capability | Implementation |
|---|---|
| **Autonomous agent routing** | Classifies each prompt into `rag` / `cnn` / `chat` and grounds RAG answers strictly in retrieved context |
| **Dynamic LLM provider** | Resolves Groq or Gemini at runtime from whichever API key is set — no code change to switch |
| **RAG retrieval engine** | FAISS + sentence-transformers, per-user vector namespaces persisted to disk |
| **Computer vision pipeline** | PyTorch ResNet18 transfer learning — classification + 512-d feature vector, run as a background job |
| **Async task processing** | Celery + Redis queues (`default`, `cnn`, `rag`) so heavy work never blocks an HTTP request |
| **Metered subscription billing** | Stripe Checkout, signature-verified idempotent webhooks, permanent audit log |
| **Tiered rate limiting** | Redis fixed-window limiter scaled by subscription tier |
| **Auth** | JWT bearer tokens + revocable API keys (SHA-256 hashed, never stored in plaintext) |
| **Migrations** | Alembic, hand-verified against the live ORM schema |
| **Observability** | Sentry error tracking, Prometheus metrics at `/metrics` |
| **CI/CD** | GitHub Actions: lint → test → build → push images to GHCR |
| **Dashboard** | Next.js — auth, agent console, document upload, vision job polling, billing |
| **Scheduled maintenance** | Celery Beat — auto-fails stuck jobs (30 min timeout), auto-downgrades subscriptions stuck `past_due` past a grace period |
| **Deploy-time automation** | Container entrypoint waits for Postgres, then applies Alembic migrations automatically before serving traffic |
| **Security & dependency automation** | CodeQL scanning (push/PR + weekly), Dependabot for pip/npm/Docker/Actions, pre-commit hooks |

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Next.js    │────▶│  FastAPI backend │────▶│   PostgreSQL     │
│  Dashboard  │     │  (agent router,  │     │  (users, subs,   │
└─────────────┘     │   auth, billing) │     │   audit, jobs)   │
                     └────────┬─────────┘     └─────────────────┘
                              │
                     ┌────────▼─────────┐     ┌─────────────────┐
                     │  Celery + Redis  │────▶│  PyTorch CNN /   │
                     │  task queue      │     │  FAISS RAG index │
                     └──────────────────┘     └─────────────────┘
                              │
                     ┌────────▼─────────┐
                     │  Stripe billing  │
                     │  (checkout +     │
                     │   webhooks)      │
                     └──────────────────┘
```

A request to `/api/v1/agent/invoke` is classified, then either grounded against a user's FAISS
namespace, dispatched to a queued CNN job, or answered directly — see
[`backend/agent.py`](backend/agent.py) for the routing logic itself.

## Tech stack

**Backend** — FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async) · PostgreSQL · Alembic · Celery ·
Redis · PyTorch · torchvision · FAISS · sentence-transformers · Groq API · Google Gemini ·
Stripe · Sentry · Prometheus

**Frontend** — Next.js 14 · React 18 · Axios

**Infra** — Docker · Docker Compose · GitHub Actions · GHCR

## Quick start (Docker)

```bash
cp .env.example .env        # add GROQ_API_KEY or GEMINI_API_KEY, Stripe test keys
docker compose up --build
```

| Service | URL |
|---|---|
| Backend API + docs | http://localhost:8000/docs |
| Frontend dashboard | http://localhost:3000 |
| Flower (Celery monitor) | http://localhost:5555 |
| Prometheus metrics | http://localhost:8000/metrics |

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn backend.main:app --reload

# separate terminal — background workers
celery -A backend.celery_app worker --loglevel=info -Q default,cnn,rag

# separate terminal — frontend
cd frontend && npm install && npm run dev
```

## API reference

Interactive OpenAPI docs are served at `/docs` once the backend is running. Core endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Create an account |
| `POST` | `/api/v1/auth/login` | Get a JWT access token |
| `POST` | `/api/v1/auth/api-keys` | Issue a revocable API key |
| `POST` | `/api/v1/agent/invoke` | Ask the autonomous agent anything |
| `POST` | `/api/v1/rag/documents` | Upload a document for indexing (async) |
| `POST` | `/api/v1/rag/query` | Query your indexed documents |
| `POST` | `/api/v1/cnn/analyze` | Submit an image for CNN analysis (async) |
| `GET` | `/api/v1/cnn/jobs/{id}` | Poll a background job's status/result |
| `POST` | `/api/v1/billing/checkout` | Start a Stripe Checkout session |
| `POST` | `/api/v1/billing/webhook` | Stripe webhook receiver (signature-verified) |
| `GET` | `/api/v1/billing/usage` | Current usage against your rate limit |

## Automation

Beyond the request/response API, the platform runs itself in a few ways:

- **Celery Beat schedule** (`backend/celery_app.py`) — `cleanup_stale_jobs` runs every
  10 minutes and fails any job stuck in `pending`/`running` past 30 minutes (a crashed worker
  should never leave a job spinning forever in the UI). `downgrade_expired_subscriptions` runs
  hourly and drops any subscription stuck `past_due` for more than 3 days back to the free tier.
- **Migrations on deploy** — `backend/entrypoint.sh` waits for Postgres, then runs
  `alembic upgrade head` automatically before starting Uvicorn, so a fresh container or a rolling
  deploy never serves traffic against a stale schema.
- **Dependabot** (`.github/dependabot.yml`) — weekly PRs for pip, npm, Docker base images, and
  GitHub Actions versions.
- **CodeQL** (`.github/workflows/codeql.yml`) — static security analysis on every push/PR plus a
  weekly scheduled scan, for both the Python backend and the Next.js frontend.
- **Pre-commit hooks** (`.pre-commit-config.yaml`) — ruff lint/format, trailing whitespace,
  large-file and secret-key checks run locally before a commit lands; `make seed-hooks` installs
  them.
- **`Makefile`** — one-word entry points (`make up`, `make test`, `make migrate`, `make fresh`,
  etc.) so the automation above doesn't require memorizing flags.

## Testing

```bash
pytest --cov=backend --cov-report=term-missing
```

Covers auth lifecycle (register/login/API keys), Stripe webhook signature verification and
checkout flow, agent routing, and RAG/CNN job dispatch — all with external services (Stripe,
Redis, Groq) mocked so the suite runs fast and offline.

## Billing model

Stripe automatically transfers your available balance to your bank account on the payout
schedule set in your Stripe Dashboard. A standard SaaS charging its own customers should **not**
call the Payouts API directly — that endpoint is for Stripe Connect platforms disbursing *other
people's* funds (e.g. marketplaces paying sellers). This project implements the correct
pattern instead:

- `POST /api/v1/billing/checkout` → Stripe Checkout Session (subscription mode)
- `POST /api/v1/billing/webhook` → signature-verified, idempotent handling of
  `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
  `customer.subscription.deleted`
- Every event is written to `audit_logs` for compliance and support

An optional, explicitly-gated `trigger_connect_payout()` helper is included in
[`backend/billing.py`](backend/billing.py) for teams that genuinely run a Connect marketplace
model (`STRIPE_CONNECT_ENABLED=true`).

## Scope & what still needs hardening

Being direct about where this sits between "portfolio-grade" and "battle-tested":

**Solid and real:**
- Auth (JWT + API keys, bcrypt hashing), tiered Redis rate limiting
- RAG ingestion/query (FAISS + sentence-transformers), persisted per-namespace
- CNN inference (torchvision ResNet18 transfer-learning pipeline)
- Stripe checkout + webhook handling with idempotency and audit logging
- Alembic migration matching the ORM schema exactly
- A real pytest suite (auth, billing, rate limits, RAG/CNN job dispatch)

**Needs attention before real production traffic:**
- The routing classifier in `agent.py` makes a cheap LLM call to pick rag/cnn/chat — fine for a
  demo, but a rules-based pre-filter with LLM fallback would be cheaper and more reliable at scale
- No refresh-token rotation — access tokens are long-lived (24h default); add refresh tokens
  before shipping to real users
- The CNN endpoint classifies against ImageNet classes, not a custom-trained model — swap in
  your own fine-tuned weights via `CNN_WEIGHTS_DIR` for a real product use case
- The test suite runs against SQLite for speed; the GitHub Actions workflow does too — add a
  `postgres:` service there for parity before trusting it fully in CI
- No frontend test coverage yet (`npm run lint` / `npm run build` only)

## Project structure

```
omniscale/
├── backend/
│   ├── main.py              FastAPI entrypoint
│   ├── agent.py              Autonomous routing + LLM client
│   ├── rag_engine.py         FAISS retrieval
│   ├── cnn_module.py         PyTorch vision pipeline
│   ├── billing.py            Stripe checkout + webhooks
│   ├── tasks.py               Celery background workers
│   ├── models.py / schemas.py
│   ├── routers/               API route modules
│   └── alembic/                Migrations
├── frontend/                  Next.js dashboard
├── tests/                     PyTest suite
├── docs/                      GitHub Pages landing site
├── docker-compose.yml
└── .github/workflows/ci-cd.yml
```

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Designed and developed by Nikhil Chary Sriramoju**

[GitHub](https://github.com/Nikhil-creat) · [LinkedIn](https://in.linkedin.com/in/nikhil-chary-sriramoju-95041b38a)

</div>
