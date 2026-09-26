# OmniScale Enterprise Pro

**Designed and Developed by NIKHIL CHARY SRIRAMOJU**

An elite, multi-tenant AI SaaS platform: autonomous agentic routing (RAG vs.
CNN vs. chat), a PyTorch computer-vision pipeline, a FAISS-backed RAG engine,
Celery/Redis background processing, PostgreSQL + Alembic migrations, Stripe
subscription billing, a Next.js dashboard, PyTest coverage, GitHub Actions
CI/CD, and Sentry/Prometheus observability.

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

## Quick start (Docker)

```bash
cp .env.example .env        # fill in your Groq/Gemini + Stripe keys
docker compose up --build
```

- Backend API: http://localhost:8000 (docs at `/docs`)
- Frontend dashboard: http://localhost:3000
- Flower (Celery monitor): http://localhost:5555
- Prometheus metrics: http://localhost:8000/metrics

## Local development (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn backend.main:app --reload

# in another terminal
celery -A backend.celery_app worker --loglevel=info -Q default,cnn,rag

# in another terminal
cd frontend && npm install && npm run dev
```

Run the test suite:

```bash
pytest --cov=backend --cov-report=term-missing
```

## Dynamic LLM provider

The agent picks a provider at runtime based on which key is set in `.env`:
`GROQ_API_KEY` (preferred — lower latency) or `GEMINI_API_KEY` (automatic
fallback). Both can be set; Groq wins.

## Billing model — an honest note on payouts

Stripe automatically transfers your available balance to your bank on the
payout schedule set in your Stripe Dashboard. A standard SaaS charging its
own customers should **not** call the Payouts API directly — that endpoint
exists for Stripe Connect platforms disbursing *other people's* funds (e.g.
marketplaces paying sellers). This project implements the correct pattern:

- `POST /api/v1/billing/checkout` → Stripe Checkout Session (subscription mode)
- `POST /api/v1/billing/webhook` → signature-verified, idempotent handling of
  `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
  `customer.subscription.deleted`
- Every event is written to `audit_logs` for compliance/support

An optional, explicitly-gated `trigger_connect_payout()` helper is included
in `backend/billing.py` for teams that genuinely run a Connect marketplace
model (`STRIPE_CONNECT_ENABLED=true`).

## What's genuinely production-shaped vs. what still needs hardening

Being direct about scope, since "zero placeholders" and "production-ready"
are different bars for a project this size:

**Solid and real:**
- Auth (JWT + API keys, bcrypt hashing), tiered Redis rate limiting
- RAG ingestion/query (FAISS + sentence-transformers), persisted per-namespace
- CNN inference (torchvision ResNet18 transfer-learning pipeline)
- Stripe checkout + webhook handling with idempotency and audit logging
- Alembic migration matching the ORM schema exactly
- A real pytest suite (auth, billing, rate limits, RAG/CNN job dispatch)

**Needs your attention before real production traffic:**
- The routing classifier in `agent.py` uses a cheap LLM call to pick
  rag/cnn/chat — fine for a portfolio/demo, but a rules-based pre-filter
  plus LLM fallback would be cheaper and more reliable at scale.
- No refresh-token rotation — access tokens are long-lived (24h default);
  add refresh tokens before shipping to real users.
- CNN endpoint returns classification against ImageNet classes, not a
  custom-trained model — swap in your own fine-tuned weights via
  `CNN_WEIGHTS_DIR` for a real product use case.
- Test suite runs against SQLite for speed; run it against a real Postgres
  container in CI before trusting it fully (the GitHub Actions workflow
  currently uses SQLite too — add a `postgres:` service there for parity).
- No frontend test coverage yet (`npm run lint`/`build` only).

## License / attribution

Every file, API response, and UI shell carries the required attribution:
**Designed and Developed by NIKHIL CHARY SRIRAMOJU**.
