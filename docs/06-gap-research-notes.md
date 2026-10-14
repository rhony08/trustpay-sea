# 06 — Gap Research Notes (New Gaps Found by Audit, 2026-10-14)

**Purpose**: second-pass gap hunt over docs (01–05), code (Phase 0/1 state: 49 tests green,
`/check` PWA page, resolver APIs), the fresh `gcp/` kit, and 2025–2026 external evidence.
Numbered **NG-1…NG-20** so they don't collide with the G-series in `05-gap-analysis.md`.
Nothing here overrides an owner decision — each ends with the question to confirm.

Related open items this builds on: G-3 (evidence-grade weights), G-6 (who are admins),
G-7 (hosting → **proposed resolved by `gcp/` kit, needs owner confirm**), G-8 (bank directory
licensing), G-11 (currency scope), G-12 (Terms/Privacy), G-13 (erasure vs HMAC index),
G-15 (notification provider), R-3/R-4.

---

## A. Attacker-model gaps (scammers adapt to us, not just to banks)

### NG-1 — Quishing: physical QR-sticker overlay is outside the current threat model

Docs model the enemy as mule-account operators. 2025 evidence shows a second enemy:
**fake QR stickers pasted over real merchant codes** (parking meters, car parks, restaurant
tables, mailed packages). Victim scans → phishing page or wrong NMID → pays the attacker.
TrustPay's planned "QR changed since last seen" alert (04 §3.7) only fires *after* someone
reports the swapped code — the first victims have no protection, and merchants have no
self-check ("is the QR on my counter still mine?").

- UK Action Fraud: ~£3.5M lost, 780+ quishing reports Apr 2024–Apr 2025; BBC: reports up
  **~14-fold 2019–2024**, organised-crime driven.
- NordVPN via CNBC: **73% scan QR codes without verifying**; 26M+ redirected to malicious sites.
- Feb 2026: "fancy" styled QR codes (logos, colors, rounded modules) defeat visual inspection
  and some detection tooling.
- https://www.bbc.com/news/articles/cq6yznmv3gzo
- https://www.independent.co.uk/news/uk/home-news/qr-code-warning-car-park-quishing-b2773806.html
- https://www.cnbc.com/2025/07/27/cybersecurity-scams-quishing-qr-code-consumer-risks-hackers.html
- https://it.nc.gov/blog/2026/02/09/alert-raleigh-new-york-fancy-qr-codes-make-quishing-more-dangerous

**Recommend**: (1) merchant QR self-check flow (scan-your-own-sticker → "matches registered
NMID" or "UNKNOWN — reprint"); (2) first-seen/NMID-change timeline per entity, not just a
boolean alert; (3) Scam Playbook page on sticker-overlay (cheap, fits R-2 set).
**Ask owner**: is merchant self-check in MVP scope or roadmap?

### NG-2 — Score polarity confusion vs ScamAdviser-style tools

TrustPay: **higher = riskier** (80–100 CRITICAL). ScamAdviser/Truecaller-style tools users
know: **higher = safer**. Anyone cross-checking will misread a bare "72". Docs show band
labels in UI (§7.1/§7.2) but no explicit rule against displaying bare numbers (API, receipts,
warning cards, Diligence Receipt 3B.7).

**Recommend**: hard rule — every rendered score carries band label + color + direction cue
("Risk 72/100 · HIGH RISK — higher means riskier"). Add to Definition of Done.
**Ask owner**: confirm wording; confirm Diligence Receipt shows band, not number alone.

### NG-3 — The public screen API is a free oracle for scammer QA (no adversarial-use design)

04 fronts an **Open Public API** (`screen/account`, `screen/qr`) with rate limiting, but no
analysis of adversarial use: a mule operator can screen their own accounts to learn which
are flagged, then rotate to clean ones — TrustPay becomes free QA for the enemy. Rate
limits slow this, they don't stop distributed probing, and threshold-gated
`search_intelligence` (04 §3.3) leaks via repeated lookups.

**Recommend**: (1) API keys required even for "public" tier (7.4 already plans key hashing —
extend with per-key quotas + lookup-pattern anomaly: one key screening many distinct
entities = scammer-QA signature → throttle/challenge); (2) consider noisy/bucketed
responses for unauthenticated callers; (3) log screen-API lookups into the same identity
graph as reports (ADR-014) so probe networks are detectable.
**Ask owner**: auth-required vs open screen API for MVP demo? (Open is better demo, worse
abuse posture — needs explicit call.)

### NG-4 — iPhone ceiling on PWA alerts (watchlist + notifications over-promise)

3B.4 (watchlist alerts) and 7.7 (PWA push) assume push works. iOS as of Oct 2026:
push **only for Home-Screen-installed apps**, permission must follow a user tap, every push
must show a visible notification (silent push = permission revoked), **no Background Sync /
Periodic Sync / Background Fetch**, no install prompt, no notification action buttons/images.
Camera/geolocation/share all work (QR scanning unaffected).

- https://dev.to/wavx_solutions_1c671328ad/pwas-on-iphone-what-works-and-what-does-not-october-2026-5cgf
- https://web.dev/blog/push-notifications-in-all-modern-browsers
- https://firebase.google.com/docs/web/pwa

**Recommend**: (1) email-first notifications (settles half of G-15), push as enhancement;
(2) install-gated alert UX ("add to Home Screen to enable watchlist alerts" + detect
`display-mode: standalone`); (3) sync-on-open instead of background sync for offline queue.
**Ask owner**: email provider pick (Resend/Postmark — closes G-15) + is Home-Screen-gated
alert UX acceptable for demo?

---

## B. Legal / regulatory gaps (beyond UU ITE defamation)

### NG-5 — OJK may classify TrustPay as FSTI (aggregator / alternative scoring)

Docs cover UU ITE defamation (ADR-010/016) and PDP (G-13/7.8) but not OJK perimeter:
- **POJK 4/2025** (effective Feb 2025): financial-services aggregators (PAJK — gathering/
  filtering/comparing product info) are FSTI operators needing OJK posture.
- **POJK 30/2025** (effective 1 Jul 2026): governance + risk management for FSTI incl.
  **Alternative Credit Scoring and Aggregators** — min 2 directors, risk reports, cyber/legal/
  reputation risk management.
- **POJK 6/2026** (Jun 2026): "financial influencer" conduct rules for parties disseminating
  financial-sector info that influences public decisions — a risk-score publisher is
  uncomfortably close to this definition.
- Payments edge is clean (no funds touched → no BI PJP licence under PBI 22/23/2020), but
  that non-custody stance is nowhere stated.

- https://www.ojk.go.id/en/berita-dan-kegiatan/siaran-pers/Documents/Pages/OJK-Issues-Regulation-on-the-Operation-of-Financial-Services-Aggregators/50%20%5BPress%20Release%5D%20OJK%20Terbitkan%20Peraturan%20Penyelenggara%20Agregasi%20Jasa%20Keuangan_EN.pdf
- https://www.ojk.go.id/en/berita-dan-kegiatan/siaran-pers/Pages/OJK-Issues-Regulation-on-Financial-Services-Sector-Information-Provider-Finfluencer-for-Public-Protection.aspx
- https://www.ojk.go.id/en/berita-dan-kegiatan/siaran-pers/Documents/Pages/OJK-Regulations-Enhancing-Governance-and-Risk-Management-for-FSTI-Sector-and-DFA/SP%2031%20%5bPress%20Release%5d%20OJK%20Terbitkan%20Aturan%20Perkuat%20Tata%20Kelola%20dan%20Manajemen%20Risiko%20Inovasi%20Teknologi%20Sektor%20Keuangan%20Serta%20Aset%20Keuangan%20Digital_EN.pdf

**Recommend**: legal review before public launch (extends G-8/G-12): recordation/sandbox path
assessment, ToS "informational purposes, not financial advice" + no-recommendation language,
explicit non-custody statement. Hackathon demo unaffected — note as launch gate.
**Ask owner**: engage counsel now or post-hackathon? (Recommend: post-hackathon, pre-public.)

### NG-6 — Retention vs legal-hold vs erasure needs one coherent spec (sharpens G-13)

Three features each assume different data fate: 7.8 retention job purges originals after N
days; `is_legal_hold` (02 §3.3/§10.5) keeps rows for police; G-13 tombstone-erasure keeps the
HMAC row so others stay protected. No single spec reconciles them (e.g., does legal hold
block DSAR delete? does erasure tombstone the HMAC or the report body?).

**Recommend**: Phase 7 pre-task — per-table fate matrix (users / reports / evidences /
entities / audit_logs) × (DSAR delete / retention expiry / legal hold / dispute freeze).
**Ask owner**: default original-evidence retention N (recommend 90d to match bucket lifecycle
in `gcp/terraform/main.tf`).

---

## C. Technical / ops gaps (incl. drift from the new `gcp/` kit)

### NG-7 — TDD ↔ implementation drift after the GCP kit (proposes closing G-7)

02 §1 still says Cloudflare WAF, R2/S3, Gemini 1.5 Flash, Redis/RabbitMQ option. Reality now:
GCS evidence bucket, no WAF resource in Terraform (Armor only in notes), Gemini 3.x pricing,
APScheduler+Redis. Also G-7's option list (Vercel/Railway/Fly.io/R2/AWS) is superseded.

**Recommend**: ADR-018 (GCP Jakarta-primary hosting) + touch-ups to 02 §1/§10 and README stack
table (R2/S3 → GCS primary). No code impact.
**Ask owner**: confirm GCP as the answer to G-7 (kit is landed; this just records the decision).

### NG-8 — No cost guardrails in Terraform

`gcp/terraform` has no `google_billing_budget` alert, no billing export to BigQuery. A brigading
flood or Gemini retry storm bills real money with no tripwire.

**Recommend**: add budget module (dev cap alert at $50/$200 thresholds → email + Pub/Sub →
optional Cloud Run minScale→0 function). Small task, fits Phase 7.
**Ask owner**: monthly budget numbers per env.

### NG-9 — Screen-API key design missing (blocks 7.4 + NG-3)

7.4 promises hashed keys + scopes + rotation + last-4 display, but 02 has no key-issuance
flow (who gets keys, free-tier quota, scope granularity `screen:read` vs `reports:write`,
revocation path). Without it, NG-3 mitigations have nowhere to attach.

**Recommend**: mini-spec in 02 §7 before Phase 6: key tiers (demo/open/partner), per-tier
quotas, rotation + revocation endpoints, abuse-pattern hooks.
**Ask owner**: do demo/partner keys exist for hackathon, or is 7.4 docs-only?

### NG-10 — Moderation-queue flood has no SLA or capacity plan (sharpens G-6)

Phase 4 builds flag queues; nothing sets review-latency targets, triage ordering
(evidence-grade first?), or what happens at 10× report volume. Mass-reporting a legit
merchant is brigading-by-process — distinct from vote brigading (ADR-014) and unaddressed.

**Recommend**: queue SLO (e.g., P95 first-review <24h demo / <4h prod), severity-ordered triage,
auto-escalation on spike, analyst headcount assumption for G-6.
**Ask owner**: who staffs the demo queue (G-6) + acceptable demo SLO?

### NG-11 — DSAR/erasure semantics per table (implements G-13)

Deleting a `payment_entities` HMAC row un-protects everyone who would look that account up;
deleting a report body is straightforward. Spec needed per NG-6 matrix: tombstone HMAC +
purge PII, keep anonymized counters for scoring integrity.

**Recommend**: fold into NG-6 fate matrix task.
**Ask owner**: same as NG-6.

### NG-12 — Currency scope blocks cross-border fixtures (sharpens G-11)

Seed is IDR-first (G-5), but QRIS cross-border TLVs carry THB/MYR/SGD (tags 53/54) and 3B/4B
features (cooling-off thresholds, amount-aware friction 4B.3) need currency-aware amounts.
No decision → fixtures and threshold logic can't be written consistently.

**Recommend**: IDR-primary + store `amount_minor + currency` verbatim; thresholds configured
per currency with IDR fallback rate table (static, documented as demo-grade).
**Ask owner**: confirm (closes G-11 as a side effect).

---

## D. Already-tracked-but-worth-naming (Phase 7 backlog, no action now)

- **NG-13** E2E Playwright suite (7.2), **NG-14** seed script (7.3), **NG-15** WebAuthn MFA +
  dual-control UI (7.5/9.3) — all scheduled, just unstarted (expected at Phase 0/1).
- **NG-16** No web test harness (7.1 cites `vitest`, `apps/web` has none) — add with first
  3B UI task.
- **NG-17** `packages/types` is README-only — generate shared screen-API types with 7.4.
- **NG-18** OpenCV `<5` pin + committed fixture PNG (04 Phase 1 notes) — revisit unpin
  quarterly; tracked in-plan.
- **NG-19** Evidence-bucket 90-day lifecycle vs `is_legal_hold` — hold must exempt rows AND
  objects; covered by NG-6 matrix.
- **NG-20** `GET /healthz` "behind auth" wording superseded (04 Phase 0 demo already notes
  this) — sweep remaining "behind auth" mentions in 01/02 when touching those sections.

---

## E. Proposed next-note topics (parking lot)

1. Adversarial test plan for NG-3 (probe-pattern fixtures for the screen API).
2. Merchant self-check UX sketch (NG-1) + NMID-change timeline query design.
3. OJK counsel brief one-pager (NG-5) once owner confirms timing.
4. Budget-alert Terraform module (NG-8) with per-env numbers.
5. Fate-matrix draft table (NG-6/NG-11) ahead of Phase 7.
