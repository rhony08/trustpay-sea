# TrustPay SEA

**The Truecaller & Google Reviews for Southeast Asian digital payments.**

Community-driven payment-risk & reputation registry: look up a bank account or scan a
QR code (QRIS, DuitNow, PromptPay, PayNow, VietQR, QR Ph) *before* you pay. Victims
submit fraud reports; the community reviews, votes, and flags; legitimate owners can
claim and dispute; admins adjudicate with AI-assisted forensics. Every entity gets an
explainable 0–100 trust/risk score.

## Docs are the source of truth

Read [`docs/`](docs/README.md) first — blueprint, technical design, ADRs,
implementation plan, gap analysis. The handoff message in [`docs/README.md`](docs/README.md)
tells the next agent exactly what to read and which invariants must not regress.

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15 (App Router) PWA + Tailwind |
| Backend | FastAPI (Python 3.11) modular monolith |
| DB | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| AI | Gemini via pluggable provider (`AI_PROVIDER=mock|gcp|openrouter`) |

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Web: http://localhost:3000
- API + Swagger: http://localhost:8000/docs
- Health: `curl http://localhost:8000/healthz` → `{"status":"ok","version":"0.1.0"}`

### Backend tests

```bash
cd services/api
pip install -e ".[dev]"
docker compose up -d postgres redis
pytest -q
```

### Frontend checks

```bash
cd apps/web
npm install
npm run typecheck && npm run lint && npm run build
npx playwright install chromium   # once
npm run test:e2e                  # Playwright smoke (boots the built PWA)
```

### Bank reference (controlled vocabulary)

The SEA bank/e-wallet directory lives in `services/api/app/data/banks/*.json`
(single source of truth for both the resolver and the reporting UI). Seed it
into Postgres before reporting works:

```bash
cd services/api
python -m app.seeds.seed_banks        # idempotent upsert
python -m app.seeds.seed_demo         # demo users/entities/reports/dispute/gov entry
# → GET /api/v1/banks?country=ID&bank_type=E_WALLET  (public dropdown feed)
```

Demo login after `seed_demo`: `analyst@trustpay.dev` / `demo-analyst-pass` (ANALYST role).

## Project layout

```
apps/web/          Next.js 15 PWA
services/api/      FastAPI + SQLAlchemy + Alembic
packages/          shared test vectors & (later) generated types
docs/              planning docs + ADRs (source of truth)
```

## Status

Phase 0 (scaffolding, full DB schema, auth, rate limiting, CI) in progress.
Delivery phases: see [`docs/04-implementation-plan.md`](docs/04-implementation-plan.md).
