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
- `GET /healthz` returns `{"status":"ok","version":"0.1.0"}`. (Public — compose/Docker healthchecks and uptime probes need it unauthenticated; the original "behind auth" wording is superseded. Auth is demonstrated by `GET /api/v1/auth/me` + the RBAC-gated `/protected-ping`.)
- **Status 2026-10-14**: ✅ DONE — stack boots via `docker compose up`; 11-table schema migrates clean; argon2id + RS256 JWT with refresh-rotation/reuse-detection; token-bucket 429 verified; scheduler placeholders registered; 14 tests green; CI workflow in place. See ADR-017 for implementation choices.

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
- **Status 2026-10-14**: ✅ DONE — bank directory (393 institutions across 6 countries incl. commercial/Islamic/digital banks + major e-wallets, sourced from `app/data/banks/*.json`), normalizer (formatting variants → same KMS-keyed HMAC hash, H11 collision guards, length validation), EMVCo TLV parser w/ CRC-16 + scheme detection + homoglyph detector, server-side QR image decode (`POST /api/v1/qr/decode`, upload guards), `GET /api/v1/entities/account` + `POST /api/v1/entities/qr` (exact-match only; lookups never insert rows §10.3; ADR-016 holder-name labels), `/check` PWA page. 59 tests green. Implementation notes: opencv pinned `<5` (5.0.0 QRCodeEncoder segfaults on arm64); QR fixture PNG committed (encoder unusable in-wheel); CV2 multi-decode arity handled defensively.
- **Bank reference → controlled vocabulary (2026-10-14)**: `banks` DB table + Alembic migration `47312e3b6363`; seed with `python -m app.seeds.seed_banks` (idempotent upsert); public `GET /api/v1/banks?country=ID&bank_type=E_WALLET` so reports/reporter UI select an institution instead of free text. The same JSON is the resolver's source of truth (single taxonomy). G-8 still applies: real bank code maps are demo-grade pending licensing review.

---

## Phase 2 — Reports, Evidence & AI Forensics

**Goal**: Victims report fraud with evidence; AI redacts PII, OCRs slips, and detects tampering async; reports publish as "Unverified".

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 2.1 | `POST /api/v1/reports` (entity, category, severity, amount, currency, incident_date, description) with `Idempotency-Key`; per-user/day + per-entity/hour quotas | Returns 202 + report_id; non-blocking; duplicate key rejected; quota 429 over limit |
| 2.2 | Signed upload flow for evidence (R2/S3 presigned POST): quarantine bucket + public bucket; magic-byte check, max pixel cap, re-encode+EXIF strip, ClamAV scan | File lands in quarantine after validation; oversized/exec/polyglot rejected; public URL not yet present |
| 2.3 | Async worker: PII redaction (blur balance/address/IDs/faces) via Gemini Vision — **fail-closed** | Redacted copy stored in public bucket; **if redaction fails report stays `PROCESSING`/`FAILED`, never published**; original stays quarantine |
| 2.4 | Async worker: slip OCR (sender, recipient, refId, time, amount) + tamper detection heuristics | `ai_forensic_notes` populated; `ai_tampering_detected` flag correct on tampered fixture |
| 2.5 | Async worker: pHash duplicate-evidence detection | Same image submitted to 2 reports → dup signal flagged |
| 2.6 | Async worker: NLP scam typology (canonical enum) + NER PII extraction with masking hints; untrusted-input/JSON-schema output | Free text classified to canonical taxonomy; NER captured; injection text does not alter output |
| 2.7 | Report status polling (`GET /api/v1/reports/{id}` → PROCESSING/PUBLISHED/FAILED) + web client status UI | UI shows processing → published (or failed w/ admin notice) transition |
| 2.8 | Review feed UI: severity bars, category badges, evidence gallery (redacted), helpful votes | Report appears on entity profile after publish |

### Phase 2 Demo
- Submit report with slip image → watch it flip to "published with redacted evidence" + `ai_tampering_detected` displayed.
- Bonus: submit a `.exe` masked as image → rejected at upload; submit 6 reports in 1h from a burner account → quota 429.

- **Status 2026-10-14**: ✅ DONE — `POST /api/v1/reports` (auth + consent, `Idempotency-Key`, per-user/day + per-entity/hour quotas → 202 PROCESSING), `POST /api/v1/reports/{id}/evidence` (magic-byte + decompression-bomb pixel cap + EXIF-stripping re-encode → quarantine), async worker (fail-closed PII redaction, slip OCR/tamper heuristics, real pHash duplicate detection, canonical-taxonomy NLP + NER), `GET /api/v1/reports/{id}` status polling, published-reports feed on the entity profile, and the `/report` PWA page (auth → submit → processing→published polling) + report feed in `/check`. AI is mock-first per ADR-012 (no Gemini key). Evidence storage is a local-disk shim (S3/R2 presigned = Phase 7). 77 API tests green; web typecheck/lint/build green.

---

## Phase 3 — Search Intelligence, AI Summary & Fact-Check Enrichment

**Goal**: Lookup profiles carry popularity/recency signals + a grounded AI summary + optional fact-check links.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 3.1 | Increment `search_events_daily` on every lookup (async, non-blocking) | Counter increments; hot path stays <45ms |
| 3.2 | Daily rollup job: `searches_7d`, `searches_30d`, `total_searches`, `last_searched_at` | State matches insert/update fixtures after rollup |
| 3.3 | `screen/account` + `screen/qr` responses include `search_intelligence` (rounded, threshold-gated) | Under-threshold entities omit `total_searches`; over-threshold show "~1.2k" |
| 3.4 | Grounded AI entity summary (Gemini, template prompt over structured fields; **untrusted-input model + JSON-schema output + grounding check**; cache per entity; invalidate on report/dispute change) | Summary only contains facts present in provided JSON; adversarial prompt-injection suite blocks CI; no hallucinated content |
| 3.5 | Google Fact Check Tools wrapper (`FACTCHECK_API_KEY` optional) → `related_fact_checks[]` | With key: returns claims for fixture; without key: empty array + no crash |
| 3.6 | Profile UI renders search stats + AI summary + fact-check links (graceful empty states) | UI shows all sections; mock/keyless safe |
| 3.7 | Unicode normalization + homoglyph/lookalike-name detector + "QR changed since last seen" alert | Cyrillic/zero-width lookalike merchant fixture triggers warning |

### Phase 3 Demo
- Lookup an account → see "~1.2k times searched, 48 this week, last searched 3 hours ago", AI summary, and (if key present) fact-check links.

- **Status 2026-10-14**: ✅ DONE — every lookup records `search_events_daily` + `entity_search_stats`; `search_intelligence` returned rounded + threshold-gated (ADR-011); daily rollup job recomputes 7d/30d/total; grounded AI entity summary (templated from validated facts only + grounding check, Redis-cached with version invalidation); Google Fact Check Tools wrapper (keyless-safe); unicode NFKC + zero-width/homoglyph hardening and `qr_changed_since_last_seen` alert; `/check` UI renders search stats + AI summary + fact-check links. 88 API tests green; web typecheck/lint/build green.

---

## Phase 3B — Web-First Community & Engagement Features

**Goal**: Lock in retention + status loops on the web PWA (post-MVP only for chat/SMS channels per ADR-015).

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 3B.1 | Trust Rank Ladder: derive public tier from `users.reputation_score`; badge on profile; tier privileges | Reporter sees ladder + upgrades on reputation change |
| 3B.2 | Verified Reporter Badge: phone/ID-lite verification; weight reports in score + anti-brigading | Verified reporter's report weights higher; unverified new accounts weighted low (trust 10) |
| 3B.3 | Pioneer Warn badge: first reporter of entity that later becomes admin/gov-verified | Micro-badge grants on verification event |
| 3B.4 | Watchlist + alerts: save entity, subscribe to report/band/dispute/gov events | Push/email fired on watched-entity events; no cross-user privacy leak |
| 3B.5 | Scam Vaccine quiz: 3 archetype scenarios → "Anti-Scam Aware" badge | Quiz completion grants badge; stored once |
| 3B.6 | Share-to-Check: PWA share target accepts images → decode+screen in one tap | Share a QR screenshot from another app → profile opens |
| 3B.7 | Diligence Receipt: generate PDF/QR cert of a look-up (timestamp, masked entity, risk at-check-time) | Receipt exports and re-verifies current risk on open |
| 3B.8 | High-risk cooling-off timer + pre-payment checklist | High/Critical entity blocks the confirm button with countdown + checklist |
| 3B.9 | Scam Simulator: scripted walkthrough → intercept moment | Demo launches from home page |
| 3B.10 | Scam Playbook library: SEO pages per taxonomy entry | Pages render from canonical category enum; JSON-LD structured data |

### Phase 3B Demo
- Watch it work together: share a QR from a chat app → scanned → cooling-off timer on a high-risk entity → generate a Diligence Receipt.

- **Status 2026-10-14**: ✅ DONE — Trust Rank Ladder (tier from `reputation_score`), Verified Reporter via dev phone-OTP (+identity trust/reputation, badge), Pioneer Warn badge on entity verification, Watchlist + in-app watcher notifications on publish, Scam Vaccine quiz (Anti-Scam Aware badge), Scam Playbook library keyed to the canonical taxonomy, HMAC-signed Diligence Receipts, cooling-off timer on high/critical entities, Scam Simulator, and PWA Share-to-Check (`/share` → QR decode → `/check?qr=`). Backend: `user_badges` + `watchlist_entries` (migration `d8352d63f0c3`), `GET/POST /api/v1/profile/*`, `GET /api/v1/playbook`, `POST /api/v1/receipts/account`. 107 API tests green; web typecheck/lint/build green.

---

## Phase 4 — Community Moderation (Review Flags & Upvotes)

**Goal**: Community can upvote/downvote and **report invalid reviews**; flags route to admin queue.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 4.1 | Upvote/downvote on reports (`report_votes` table, one vote per user per report, PK) + reputation-weighted score factor | Vote counts update; double-vote blocked at DB level; score factor recomputed |
| 4.2 | `POST /api/v1/reports/{id}/flags` with reason enum (DEFAMATION_SPAM/INCORRECT_ACCOUNT/OFFENSIVE_CONTENT/OTHER) + details; dedupe per user; per-user flag rate cap | Flag created; duplicate by same user+reason rejected; rapid flagging throttled |
| 4.3 | Flag moderation queue for admins (PENDING→UPHELD/DISMISSED) with audit log | Admin action recorded in `audit_logs` (hash-chained) |
| 4.4 | Enforcement: hidden report → UI badge; reporter warned/banned; score recompute | Hidden report excluded from score; banned reporter can't submit |
| 4.5 | Public "report this review" button + status feedback for flag creator | UI path complete; flag status visible to creator |
| 4.6 | Bad-faith flagger detection: upheld-vs-dismissed ratio per flagger; auto-warning on abuse | Flagger with 90% dismissed flags enters warned state |

### Phase 4 Demo
- Flag a review as spam → admin upholds → review hidden, score recalibrated, reporter warned.

- **Status 2026-10-14**: ✅ DONE — up/down votes on reports (per-user PK, idempotent, counts denormalized); `POST /reports/{id}/flags` with reason enum + per-user unique + Redis hourly rate cap; admin queue + `resolve` gated to ANALYST+ (UPHELD hides the report + warns the reporter, DISMISSED keeps it); bad-faith flagger auto-warn at ≥90% dismissed (min 5); every resolution written to the hash-chained `audit_logs` (with a chain verifier); banned reporters blocked from submitting. Web: vote + "report this review" controls with status feedback on the entity feed. 114 API tests green; web typecheck/lint/build green.

---

## Phase 4B — Security-Awareness Features (Web)

**Goal**: Interrupt scam urgency and route victims to the right help — on the web surface.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 4B.1 | Fresh bad-review interstitial: modal on entities with reports in last 24–72h or active `ANOMALY_SPIKE_DETECTED`; mandatory acknowledgment | Modal shows + blocks continue until acknowledged on fixture |
| 4B.2 | Too-good-to-be-true deal checker (paste text → heuristics + tip) | Fixtures: bait copy flagged; benign copy clear |
| 4B.3 | 3-2-1 rule + amount-aware friction for large transfers | Configurable threshold; flow enforces checklist + cooling off |
| 4B.4 | Geo-aware SOS hotline buttons + redacted case-summary attach | Countries map to correct numbers; summary pack attaches |
| 4B.5 | "I just got scammed" recovery wizard: freeze steps per bank, police/cekrekening referral, incident dossier | Wizard guides to a generated referral pack |
| 4B.6 | Warning card generator (social-share card + canonical link + QR) | Card renders; link re-screens entity |
| 4B.7 | Privacy dashboard / DSAR self-serve (export/correct/delete own data) | DSAR flow verified (ties to Phase 7.8) |

### Phase 4B Demo
- Fresh-bad-review modal → cooling-off → SOS button → recovery wizard, all in one narrative against a seeded active-spike entity.

---

## Phase 5 — Owner Claim, Dispute & Safe-Harbor Freeze

**Goal**: Legitimate owners claim entities and dispute reviews — with proof + reason + admin adjudication (never automatic removal).

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 5.1 | `POST /api/v1/entities/{hash}/claim` with ownership proof tier (passbook/mbanking/merchant portal NMID/micro-deposit) | Claim created; AI doc verification invoked |
| 5.2 | AI doc verification: OCR name+account/NMID match → `AI_VERIFYING`→`UNDER_REVIEW` or `REJECTED_IDENTITY` | Fixtures: matching → under review; mismatching → rejected |
| 5.3 | Micro-deposit tier (T2): generate deposit with OTP note, verify OTP entry | Correct OTP → ownership proven; wrong → rejected |
| 5.4 | Dispute submission: reason enum + justification + counter-evidence URLs | Dispute rows link to entity + target report |
| 5.5 | Safe-harbor: on `UNDER_REVIEW`, set `is_under_dispute=true`, **rise-only** cap (new/unverified hints ≤45; never lowers verified score), public "Dispute" badge | Score capped only on increases; an 88 admin-marked entity stays visibly HIGH RISK with badge; freeze fixture proves no drop below baseline |
| 5.6 | Admin dispute panel: side-by-side reporter evidence vs owner counter-evidence + AI signals + decision actions; settlement marks report `RESOLVED_BY_SETTLEMENT` | Admin can APPROVED_REMOVED / REJECTED_UPHELD / SETTLEMENT with audit trace |
| 5.7 | Enforcement: on APPROVED_REMOVED hide review + penalize bad-faith reporter; clear freeze on REJECTED_UPHELD | State machine transitions verified by tests |
| 5.8 | Owner response feature (T1 verified owner can pin public response under their entity) → stored in `owner_response` | Verified owner response pinned & labeled |
| 5.9 | Anti-phishing for claim flows: in-app-only claim initiation, signed deep links, "we never ask for OTP by link" education, proof-doc auto-delete after decision | SPF/DKIM/DMARC configured; OTP never mailed/SMS-linked |

### Dispute State-Machine Tests (required)
- SUBMITTED → AI_VERIFYING → UNDER_REVIEW → APPROVED_REMOVED
- SUBMITTED → AI_VERIFYING → UNDER_REVIEW → REJECTED_UPHELD
- SUBMITTED → REJECTED_IDENTITY
- UNDER_REVIEW → SETTLEMENT (report marked `RESOLVED_BY_SETTLEMENT`)
- Rise-only freeze: high-score entity during dispute keeps visible risk; unverified-increase capped ≤45

### Phase 5 Demo
- Owner claims account with matching passbook → dispute badge + capped-rise score → admin approves removal → review hidden, spammer penalized.
- Anti-gaming exhibit: mule-operator tries to claim and drop an 88-score entity → score stays 88 with "Dispute active" badge.

---

## Phase 6 — Risk Score Engine, Anti-Brigading & Admin Portal Polish

**Goal**: Full explainable 0–100 scoring, velocity detection, and admin experience.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 6.1 | Implement Bayesian scorer (ADR-003) with factor breakdown returned in API + UI | Factorization reproducible by hand for fixtures |
| 6.2 | Velocity / anti-brigading detector: identity-graph-based (distinct human identities, trust-weighted; EWMA z-score for spread-out attacks) → `ANOMALY_SPIKE_DETECTED`, dampen 0.45, admin priority | Fixture triggers correctly; normal traffic unaffected; 10 sock-puppet fixture does NOT evade |
| 6.3 | Gov blacklist mock adapter (feed `GOV_BLACKLISTED` fixtures) → score 100 override + public source attribution | Mock gov entry forces score=100 in API with `gov_source` label |
| 6.4 | Merchant KYC (-20) factor + dispute-rise-cap (≤45, never reduces verified score) + settlement discount wiring | Factors apply in correct precedence; freeze fixture proves score can't drop below verified baseline |
| 6.5 | Admin dashboard: queues (pending reports, flags, disputes), AI-assist panel, side-by-side, hash-chained audit log viewer + dual-control on destructive actions | Full moderation workflow usable end-to-end; destructive action requires 2nd approver |

### Phase 6 Demo
- Surface an entity with factor breakdown "72 = admin + community, dampened 0.45×" and a mock gov-blacklisted account showing 100.

---

## Phase 7 — MVP Hardening, Tests & Launch Demo

**Goal**: Production-quality MVP for hackathon/demo.

### Tasks

| ID | Task | Acceptance Criteria |
|----|------|---------------------|
| 7.1 | Unit/integration coverage ≥ 70% core modules (normalizer, parser, scorer, dispute workflow, flags, screen API) | `pytest` + `vitest` green |
| 7.2 | E2E smoke suite (Playwright): search→report→publish→flag→admin resolve→claim→dispute→resolve | E2E green in CI |
| 7.3 | Seed fake data script (10 entities incl. QRIS, 20 reports, 2 disputes, mock gov entry) | `npm run seed` populates demo dataset |
| 7.4 | OpenAPI 3.0 export + interactive docs (Swagger UI) for public endpoints; API-key hash at rest + scopes + rotation | Docs render; sample calls work in sandbox; keys stored hashed with last-4 display |
| 7.5 | Security pass: rate limits, JWT + MFA (WebAuthn for admins), key scopes, PII masking, quarantine bucket policy, dual-control audit | Internal @security review checklist passes |
| 7.6 | Demo script + walkthrough (search, scan, report, moderation, claim/dispute, API curl) | All demo flows rehearsed successfully |
| 7.7 | Notifications: `user_notifications` table + email/PWA-push for dispute/flag/watch/brigade events; rate caps + signed links | Watched-entity new-report alert delivered; no unlimited notif spam |
| 7.8 | Consent + DSAR: consent checkbox in report flow (links ToS/Privacy); self-serve export/correct/delete of own data; retention job (originals purge N days post-verify) | DSAR flow works for a report/evidence/account; retention job deletes originals; legal-hold exempts flagged rows |
| 7.9 | Env & deploy docs: README Getting-Started, `.env.example`, compose profiles, deploy guide | Fresh checkout can `docker compose up` + seed and demo |

---

## Appendix A — Delivery Order (Milestone Cheatsheet)

| Milestone | Phase | What you can show |
|-----------|-------|-------------------|
| M1 Scaffold | 0 | Compose stack up; healthcheck; auth works |
| M2 Resolver | 1 | Search/scan a bank account & QRIS → canonical profile |
| M3 Reporting | 2 | Report with slip → AI redacts & OCRs async, evidence gallery, quota/upload defensive |
| M4 Intelligence | 3 | Search stats, AI summary, fact-checks, homoglyph warnings |
| M4B Engagement | 3B | Trust ladder, watchlist, share-to-check, cooling-off, playbooks, scam simulator |
| M5 Moderation | 4 | Community flags → admin uphold → enforce + security-awareness interstitials |
| M6 Disputes | 5 | Owner claims, rise-only freeze, admin removes spam, anti-gaming exhibit |
| M7 Full Risk | 6 | Explainable score + identity-graph anti-brigading + gov mock override |
| M8 Launch | 7 | Polished demo + tests + seed data + MFA/audit/DSAR/notifications/env docs |

---

## Appendix B — Sequencing Logic & Dependencies

```
Phase0 ─▶ Phase1 ─▶ Phase2 ─▶ Phase3 ─▶ Phase3B ─▶ Phase4 ─▶ Phase4B ─▶ Phase5 ─▶ Phase6 ─▶ Phase7
         (index)   (reports)  (intel)    (engage)   (moder)  (aware)  (disputes)(risk)  (hardening)
```

- Phase 3B depends on Phase 1 + Phase 3 (search stats, screen API, AI summary exist).
- Phase 4B depends on Phase 4 (flag/moderation) + Phase 3 (AI signals) + Phase 2 (evidence).
- Phase 3 depends only on Phase 1 (search) + Phase 2 (reports exist). Can run parallel to Phase 4.
- Phase 5 needs Phase 2 (evidence) for counter-evidence and Phase 4 enforcement patterns.
- Phase 6 needs all prior (scorer consumes reports, flags, disputes, gov signal).
- Gov adapter real integrations (B2G) are intentionally **after Phase 7** (post-MVP, permissions pending) — scheduled as **"Post-MVP / B2G"**, NOT Phase 5 — see blueprint §6.7.

---

## Appendix C — Definition of Done for Each Task

- Code committed with conventional message (`feat/fix/test/refactor`, scoped).
- Unit test(s) added for the task's acceptance criteria.
- Lint + typecheck + tests pass locally.
- Workflows/state transitions verified by tests (not just manually).
- UI (where applicable) renders the feature with graceful empty/error states.

---

*Continue reading: [01 — Product Blueprint](01-product-blueprint.md)*