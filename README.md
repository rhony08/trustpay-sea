# TrustPay SEA

**The Truecaller & Google Reviews for Southeast Asian digital payments.**

Community-driven payment-risk & reputation registry: look up a bank account or scan a
QR code (QRIS, DuitNow, PromptPay, PayNow, VietQR, QR Ph) *before* you pay. Victims
submit fraud reports; the community reviews, votes, and flags; legitimate owners can
claim and dispute; admins adjudicate with AI-assisted forensics. Every entity gets an
explainable 0–100 trust/risk score.

> **Proprietary.** This repository is source-available for evaluation only — see
> [`LICENSE`](LICENSE). Copying, reuse, or redistribution of the idea or code is not
> permitted.

---

## Features

**Check before you pay**
- Exact-match bank-account lookup, cross-wallet phone search, and QR screening
  (client decodes for preview; the server re-decodes and CRC-validates — ADR-001).
- 4-band **risk gauge** with polarity clarity (`0 safe → 100 critical`) + factor
  breakdown (NG-2).
- **Recipient Name Matcher** radar — flags mule accounts when the bank holder name
  differs from the name the seller claimed (ADR-016).
- Mandatory **cooling-off timer** on fresh/high-risk hits.

**Report & forensics**
- 4-step empathetic reporting wizard with a live **asymmetric redaction** demo.
- Fail-closed PII redaction pipeline (victim data blurred, scammer destination clear).
- AI slip forensics: OCR, tamper detection, duplicate (pHash) detection, typology + NER.

**Community & owners**
- Upvotes/downvotes, review flagging, owner claim + dispute with **safe-harbor score
  freeze**, pinned owner clarifications.

**Admin & safety**
- Analyst console with four-eyes (ADR-021) approval queue and hash-chained audit log.
- WebAuthn passkeys + MFA step-up for admin roles (ADR-020).

**Tools**
- **Scam Message Analyzer** — paste a message/chat, get social-engineering signals and
  extracted payment coordinates (artifact-first, replaces generic fact-check).
- "Too good to be true?" deal checker, scam playbooks, scam simulator, diligence
  receipt, emergency recovery hub.

**Localization**
- Full UI in **EN / ID / MS / TH / VI / FIL** (570-key catalogs, live switcher).

---

## AI

All AI runs behind a pluggable provider (`AI_PROVIDER=mock|gcp|openrouter`) in
`services/api/app/ai/`. The `mock` provider (local heuristics) is the default and
requires **no key** — everything degrades gracefully and **redaction is fail-closed**
regardless of provider.

| Capability | Where |
|---|---|
| Slip OCR + tamper detection + PII-region redaction | `app/ai/vision.py`, `forensics.py`, `prompts.py` |
| Typology + NER on report text (prompt-injection-proof) | `app/ai/nlp.py`, `providers/base.py` |
| Grounded entity summary | `app/ai/summary.py` |
| Deal judge + message analyzer | `app/ai/prompts.py`, `app/api/tools.py` |

Enable live Gemini on GCP with `AI_PROVIDER=gcp` (+ `GCP_PROJECT`, `roles/aiplatform.user`
on the runtime service account) or `AI_PROVIDER=openrouter` (+ `OPENROUTER_API_KEY`).

---

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15 (App Router) PWA + Tailwind |
| Backend | FastAPI (Python 3.11) modular monolith |
| DB | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| AI | Gemini via pluggable provider (`mock|gcp|openrouter`) |
| Deploy | Docker Compose (single VM) · Cloud Run / GCE (`gcp/`) |

## Project layout

```
apps/web/          Next.js 15 PWA
services/api/      FastAPI + SQLAlchemy + Alembic
packages/          shared test vectors
prototype/         static HTML design prototypes
deck/              self-contained HTML pitch deck
docs/              planning docs + ADRs (source of truth)
deploy/            nginx + GCE single-VM compose bundle
gcp/               Terraform + Cloud Run / GCE deploy assets
```

## Quick start (local)

```bash
cp .env.example .env
docker compose up -d postgres redis   # or the full stack: docker compose up --build

cd services/api
python -m app.seeds.seed_banks        # 393-institution SEA reference (idempotent)
python -m app.seeds.seed_demo         # demo users/entities/reports/dispute
# demo login: analyst@trustpay.dev / demo-analyst-pass (ANALYST)
```

- Web: http://localhost:3000 · API + Swagger: http://localhost:8000/docs
- Health: `curl http://localhost:8000/healthz` → `{"status":"ok","version":"0.1.0"}`

## Tests

```bash
# Backend (real Postgres + Redis)
cd services/api
pytest -q --cov=app --cov-fail-under=70

# Frontend
cd apps/web
npm run typecheck && npm run lint && npm run build
npx playwright install chromium && npm run test:e2e
```

## Deploy to GCP

Two supported paths (both target **Compute Engine**, per the hackathon requirement):

1. **Single VM + Docker Compose** — the simplest, fully self-contained stack
   (Postgres, Redis, API, web, Caddy auto-TLS). See
   [`docs/13-gcp-deployment.md`](docs/13-gcp-deployment.md) and the bundle in
   [`deploy/gcp/`](deploy/gcp/). Cost ≈ $22/mo on one `e2-small` (Jakarta).
2. **Terraform + Cloud Run / GCE** — see [`gcp/`](gcp/) and
   [`docs/07-gce-cheap-usecase-notes.md`](docs/07-gce-cheap-usecase-notes.md).

Secrets are **never committed**: only `*.example` templates are tracked, and the API
**refuses to boot with `ENVIRONMENT=prod`** while dev placeholder secrets are in use.

## Pitch deck

Open [`deck/index.html`](deck/index.html) in any browser (self-contained; arrow keys
to navigate).

## Docs

Read [`docs/`](docs/README.md) first — blueprint, technical design, ADRs,
implementation plan, gap analysis, UI redesign, and the GCP deployment plan.

## License

Proprietary — **All Rights Reserved**. See [`LICENSE`](LICENSE).
