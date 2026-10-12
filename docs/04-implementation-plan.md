# 04 — Implementation Plan: TrustPay SEA

**Doc Version**: 1.0 · **Status**: Approved for planning
**Target**: Hackathon deliverable + foundation for MVP

This plan is structured so each phase produces a **verifiable, demo-able increment**. Every task is written as an actionable checklist with acceptance criteria. It intentionally fronts the **Open Public API** (per ADR-006) and includes search-intelligence + AI augmentation (per ADR-011/012).

---

## 0. Delivery Principles

1. **Demo-able at every phase** — end each phase with something a stakeholder can click/curl.
2. **Public API first** — implement backend as API-first; UI consumes the same OpenAPI contract as external partners would.
3. **Explainable everything** — every score/dispute decision must be legible in the UI.
4. **Mock external services** (gov adapters, Google Fact Check `FACTCHECK_API_KEY` absent) and swap in real integrations later behind the same interface.
5. **Tests gate commits** — unit + workflow-state tests run in CI/locally before merge.

---

## Phase 0 — Project Scaffolding & Foundation

**Goal**: Standing repo with CI, DB migrations, auth, and a smoke-test endpoint.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 0.1 | Initialize monorepo: `apps/web` (Next.js 15 + Tailwind), `services/api` (FastAPI), `packages/` (shared types) | `docker compose up` brings up web + api + postgres + redis |
| 0.2 | DB migrations via Alembic for full schema (users, payment_entities, entity_search_stats, search_events_daily, fraud_reports, report_evidences, owner_disputes, review_flags, audit_logs) | `alembic upgrade head` clean; tables verified in psql |
| 0.3 | AuthN: email/OTP or phone OTP + JWT refresh; RBAC roles (USER/ANALYST/SENIOR_ANALYST/SUPERADMIN) | curl signup/login flow returns tokens; role enforced on protected routes |
| 0.4 | Redis wiring + token-bucket rate limiter middleware | Hammering endpoint > limit → 429 |
| 0.5 | Airflow-free job scheduler (APScheduler or cron container) placeholder for: search-stats daily rollup, anti-brigading checks | clock job exists & runs on schedule |
| 0.6 | CI (GitHub Actions): lint (ruff + eslint), typecheck, unit tests, docker build | Green pipeline on PR |

### Phase 0 Demo
- `GET /healthz` returns `{"status":"ok","version":"0.1.0"}` behind auth.

---

## Phase 1 — Payment Identity Resolver (The Core Index)

**Goal**: Users can enter accounts / scan QR codes and get a canonical identity.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 1.1 | Bank directory (ID/MY/TH/SG/VN/PH): code→name, BIC, checksum rules, min/max length | Unit-tested mapping; missing bank returns explicit "unsupported bank" |
| 1.2 | Account normalizer: strip, canonical key, HMAC-SHA256 hash | `014-123456-7`, `014 1234567`, `0141234567` → same hash |
| 1.3 | EMVCo TLV parser (QRIS/DuitNow/PromptPay/PayNow/VietQR/QRPh) + CRC-16 validation | Parses fixture payloads; rejects bad CRC; extracts NMID, merchant name/city, amount |
| 1.4 | QR decode from image upload + camera (client `html5-qrcode`; server `pyzbar`/`opencv`) | Scanning QRIS fixture image returns correct TLV string |
| 1.5 | Entity upsert + search endpoint `GET /api/v1/entities/{hash}` returning masked profile | Exact lookup by hash returns masked entity; miss returns 404 |
| 1.6 | Client: entity search page + QR scan modal + masked display | Search/scan → canonical masked entity card |

### Test Vectors (commit to `packages/test-vectors`)
- Indonesian QRIS TLV string + image
- Malaysian DuitNow TLV string
- Thai PromptPay TLV string
- Account variants across banks

### Phase 1 Demo
- Scan QRIS → profile card shows Merchant Name, City, NMID, masked account, scheme, risk placeholder.

---

## Phase 2 — Reports, Evidence & AI Forensics

**Goal**: Victims report fraud with evidence; AI redacts PII, OCRs slips, and detects tampering async; reports publish as "Unverified".

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 2.1 | `POST /api/v1/reports` (entity, category, severity, amount, currency, incident_date, description) | Returns 202 + report_id; non-blocking |
| 2.2 | Signed upload flow for evidence (R2/S3 presigned POST): quarantine bucket + public bucket | File lands in quarantine; public URL not yet present |
| 2.3 | Async worker: PII redaction (blur balance/address/IDs/faces) via Gemini Vision | Redacted copy stored in public bucket; original stays quarantine; `is_blurred_pii=true` |
| 2.4 | Async worker: slip OCR (sender, recipient, refId, time, amount) + tamper detection heuristics | `ai_forensic_notes` populated; `ai_tampering_detected` flag correct on tampered fixture |
| 2.5 | Async worker: pHash duplicate-evidence detection | Same image submitted to 2 reports → dup signal flagged |
| 2.6 | Async worker: NLP scam typology + NER PII extraction with masking hints | Free text classified to taxonomy; NER entities captured |
| 2.7 | Report status polling (`GET /api/v1/reports/{id}` → PROCESSING/PUBLISHED) + web client status UI | UI shows processing → published transition |
| 2.8 | Review feed UI: severity bars, category badges, evidence gallery (redacted), helpful votes | Report appears on entity profile after publish |

### Phase 2 Demo
- Submit report with slip image → watch it flip to "published with redacted evidence" + `ai_tampering_detected` displayed.

---

## Phase 3 — Search Intelligence, AI Summary & Fact-Check Enrichment

**Goal**: Lookup profiles carry popularity/recency signals + a grounded AI summary + optional fact-check links.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 3.1 | Increment `search_events_daily` on every lookup (async, non-blocking) | Counter increments; hot path stays <45ms |
| 3.2 | Daily rollup job: `searches_7d`, `searches_30d`, `total_searches`, `last_searched_at` | State matches insert/update fixtures after rollup |
| 3.3 | `screen/account` + `screen/qr` responses include `search_intelligence` (rounded, threshold-gated) | Under-threshold entities omit `total_searches`; over-threshold show "~1.2k" |
| 3.4 | Grounded AI entity summary (Gemini, template prompt over structured fields; cache per entity; invalidate on report/dispute change) | Summary only contains facts present in provided JSON; no hallucinated content (tested w/ adversarial prompts) |
| 3.5 | Google Fact Check Tools wrapper (`FACTCHECK_API_KEY` optional) → `related_fact_checks[]` | With key: returns claims for fixture; without key: empty array + no crash |
| 3.6 | Profile UI renders search stats + AI summary + fact-check links (graceful empty states) | UI shows all sections; mock/keyless safe |

### Phase 3 Demo
- Lookup an account → see "~1.2k times searched, 48 this week, last searched 3 hours ago", AI summary, and (if key present) fact-check links.

---

## Phase 4 — Community Moderation (Review Flags & Upvotes)

**Goal**: Community can upvote/downvote and **report invalid reviews**; flags route to admin queue.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 4.1 | Upvote/downvote on reports (`helpful` voted table), vote-weighted into risk score | Vote counts update; score factor recomputed |
| 4.2 | `POST /api/v1/reports/{id}/flags` with reason enum (DEFAMATION_SPAM/INCORRECT_ACCOUNT/OFFENSIVE_CONTENT/OTHER) + details; dedupe per user | Flag created; duplicate by same user+reason rejected |
| 4.3 | Flag moderation queue for admins (PENDING→UPHELD/DISMISSED) with audit log | Admin action recorded in `audit_logs` |
| 4.4 | Enforcement: hidden report → UI badge; reporter warned/banned; score recompute | Hidden report excluded from score; banned reporter can't submit |
| 4.5 | Public "report this review" button + status feedback for flag creator | UI path complete; flag status visible to creator |

### Phase 4 Demo
- Flag a review as spam → admin upholds → review hidden, score recalibrated, reporter warned.

---

## Phase 5 — Owner Claim, Dispute & Safe-Harbor Freeze

**Goal**: Legitimate owners claim entities and dispute reviews — with proof + reason + admin adjudication (never automatic removal).

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 5.1 | `POST /api/v1/entities/{hash}/claim` with ownership proof tier (passbook/mbanking/merchant portal NMD/micro-deposit) | Claim created; AI doc verification invoked |
| 5.2 | AI doc verification: OCR name+account/NMID match → `AI_VERIFYING`→`UNDER_REVIEW` or `REJECTED_IDENTITY` | Fixtures: matching → under review; mismatching → rejected |
| 5.3 | Micro-deposit tier (T2): generate deposit with OTP note, verify OTP entry | Correct OTP → ownership proven; wrong → rejected |
| 5.4 | Dispute submission: reason enum + justification + counter-evidence URLs | Dispute rows link to entity + target report |
| 5.5 | Safe-harbor: on `UNDER_REVIEW`, set `is_under_dispute=true`, cap score ≤45, public "Dispute" badge | Score frozen at cap; badge appears on public profile |
| 5.6 | Admin dispute panel: side-by-side reporter evidence vs owner counter-evidence + AI signals + decision actions | Admin can APPROVED_REMOVED / REJECTED_UPHELD / SETTLEMENT with audit trace |
| 5.7 | Enforcement: on APPROVED_REMOVED hide review + penalize bad-faith reporter; clear freeze on REJECTED_UPHELD | State machine transitions verified by tests |
| 5.8 | Owner response feature (T1 verified owner can pin public response under their entity) | Verified owner response pinned & labeled |

### Dispute State-Machine Tests (required)
- SUBMITTED → AI_VERIFYING → UNDER_REVIEW → APPROVED_REMOVED
- SUBMITTED → AI_VERIFYING → UNDER_REVIEW → REJECTED_UPHELD
- SUBMITTED → REJECTED_IDENTITY
- UNDER_REVIEW → SETTLEMENT

### Phase 5 Demo
- Owner claims account with matching passbook → dispute badge + frozen score → admin approves removal → review hidden, spammer penalized.

---

## Phase 6 — Risk Score Engine, Anti-Brigading & Admin Portal Polish

**Goal**: Full explainable 0–100 scoring, velocity detection, and admin experience.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 6.1 | Implement Bayesian scorer (ADR-003) with factor breakdown returned in API + UI | Factorization reproducible by hand for fixtures |
| 6.2 | Velocity / anti-brigading detector: 3 reports in 3h from low-rep users → `ANOMALY_SPIKE_DETECTED`, dampen 0.45, admin priority | Fixture triggers correctly; normal traffic unaffected |
| 6.3 | Gov blacklist mock adapter (feed `GOV_BLACKLISTED` fixtures) → score 100 override | Mock gov entry forces score=100 in API |
| 6.4 | Merchant KYC (-20) factor + dispute cap + settlement discount wiring | Factors apply in correct precedence |
| 6.5 | Admin dashboard: queues (pending reports, flags, disputes), AI-assist panel, side-by-side, audit log viewer | Full moderation workflow usable end-to-end |

### Phase 6 Demo
- Surface an entity with factor breakdown "72 = admin + community, dampened 0.85×" and a mock gov-blacklisted account showing 100.

---

## Phase 7 — MVP Hardening, Tests & Launch Demo

**Goal**: Production-quality MVP for hackathon/demo.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 7.1 | Unit/integration coverage ≥ 70% core modules (normalizer, parser, scorer, dispute workflow, flags, screen API) | `pytest` + `vitest` green |
| 7.2 | E2E smoke suite (Playwright): search→report→publish→flag→admin resolve→claim→dispute→resolve | E2E green in CI |
| 7.3 | Seed fake data script (10 entities incl. QRIS, 20 reports, 2 disputes, mock gov entry) | `npm run seed` populates demo dataset |
| 7.4 | OpenAPI 3.0 export + interactive docs (Swagger UI) for public endpoints | Docs render; sample calls work in sandbox |
| 7.5 | Security pass: rate limits, JWT, key scopes, PII masking, quarantine bucket policy | Internal @security review checklist passes |
| 7.6 | Demo script + walkthrough (search, scan, report, moderation, claim/dispute, API curl) | All demo flows rehearsed successfully |

---

## Appendix A — Delivery Order (Milestone Cheatsheet)

| Milestone | Phase | What you can show |
|-----------|-------|-------------------|
| M1 Scaffold | 0 | Compose stack up; healthcheck; auth works |
| M2 Resolver | 1 | Search/scan a bank account & QRIS → canonical profile |
| M3 Reporting | 2 | Report with slip → AI redacts & OCRs async, evidence gallery |
| M4 Intelligence | 3 | Search stats, AI summary, fact-checks on profile |
| M5 Moderation | 4 | Community flags → admin uphold → enforce |
| M6 Disputes | 5 | Owner claims, safe-harbor freeze, admin removes spam |
| M7 Full Risk | 6 | Explainable score + anti-brigading + gov mock override |
| M8 Launch | 7 | Polished demo + tests + seed data |

---

## Appendix B — Sequencing Logic & Dependencies

```
Phase0 ─▶ Phase1 ─▶ Phase2 ─▶ Phase3 ─▶ Phase4 ─▶ Phase5 ─▶ Phase6 ─▶ Phase7
         (index)   (reports)  (intel)    (moderation)(disputes)(risk)   (hardening)
```

- Phase 3 depends only on Phase 1 (search) + Phase 2 (reports exist). Can run parallel to Phase 4.
- Phase 5 needs Phase 2 (evidence) for counter-evidence and Phase 4 enforcement patterns.
- Phase 6 needs all prior (scorer consumes reports, flags, disputes, gov signal).
- Gov adapter real integrations (B2G) are intentionally **after Phase 7** (post-MVP, permissions pending) — see blueprint §6.7.

---

## Appendix C — Definition of Done for Each Task

- Code committed with conventional message (`feat/fix/test/refactor`, scoped).
- Unit test(s) added for the task's acceptance criteria.
- Lint + typecheck + tests pass locally.
- Workflows/state transitions verified by tests (not just manually).
- UI (where applicable) renders the feature with graceful empty/error states.

---

*Continue reading: [01 — Product Blueprint](01-product-blueprint.md)*