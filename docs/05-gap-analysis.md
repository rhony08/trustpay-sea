# 05 — Gap Analysis & Open Decisions (Handoff Notes)

**Doc Version**: 1.0 · **Status**: Living document — update as decisions are confirmed
**Purpose**: Records everything that is currently a **GAP / OPEN QUESTION / RECOMMENDATION / PENDING DECISION** so no future agent loses context. Built from the 3-subagent review (PM brainstorm, Security audit, Reviewer consistency audit) plus follow-up product discussion.

---

## 1. What Was Already Resolved (Done — see Docs 01–04)

These gaps surfaced in review and were **already folded into the plan**:

| Gap | Resolution | Where |
|-----|-----------|-------|
| Dampen factor contradiction (0.45 vs 0.85) | Unified to **0.45** | 02 §5.1, 01 §7.2 |
| Missing report lifecycle states | Added `processing_status` (`PROCESSING/PUBLISHED/FAILED`) | 02 §3.3 |
| Three category taxonomies | **One canonical enum** shared by DB, NLP, API (`EVENT_TICKET_FRAUD` included) | 02 §3.3, §4.3 |
| Dispute states missing | Added `REJECTED_IDENTITY`, `REJECTED_UPHELD`, `UNCLAIMED`, `SETTLEMENT` | 02 §3.5 |
| Unverified entity shows green "safe" | Badge driven by `verification_status`; new entities render Amber "Unverified" | 01 §7.1 |
| Gov "Phase 5+" label collision | Renamed everywhere to **"Post-MVP · B2G"** | 01, 02, 03, 04, README |
| Risk-engine ordering | Phase 4/5 acceptance criteria now reference minimal scorer; full scorer Phase 6 | 04 |
| Score example not reconcilable | Worked example corrected to `35 adm + 37 community ≈ 72` | 01 §7.2 |
| `risk_level` naming vs bands | Shared enum `0-20 LOW` / `21-50 CAUTION` / `51-79 HIGH` / `80-100 CRITICAL` | 02 §7.2 |
| Missing vote table | Added `report_votes` with per-user PK (anti double-vote) | 02 §3.8 |
| Gov badge naming mismatch | `GOV_BLACKLISTED` = enum; `GOV_VERIFIED_FRAUD` = public badge label | 02 §3.2, 01 §6.7 |
| QR API narrower than blueprint | `screen/qr` now accepts image OR payload, full response shape | 02 §7.2 |
| Two-step claim flow | `dispute_reason`/`justification` nullable until ownership proven | 02 §3.5 |
| Settlement / owner response | `RESOLVED_BY_SETTLEMENT` status + `owner_response` column | 02 §3.2, §3.3 |
| Missing MCC | Added `mcc` to `payment_entities` | 02 §3.2 |
| Boolean flags not representable | Added `is_gov_blacklisted`, `is_owner_verified` | 02 §3.2 |
| KMS/HSM account hashing | ADR-013 replaces single global HMAC salt (rotation possible via `hash_version`) | 02 §2.1, ADR-013 |
| Identity-graph anti-brigading | ADR-014; new users `identity_trust` = 10 (not 50) | 02 §3.1, §5.2 |
| Anti-gaming freeze | Rise-only freeze; T3/human-verified access to challenge verified fraud | 02 §6, ADR-014 |
| Failing PII redaction | Fail-closed: never publish unredacted evidence | 02 §9.1 |
| Upload safety | Magic bytes, re-encode, AV, max pixels, cookieless media domain | 02 §9.1 |
| SSRF | Never fetch user URLs server-side | 02 §9.5 |
| Prompt injection | Untrusted-input model + JSON-schema + grounding check + CI adversarial suite | 02 §9.6, ADR-013 |
| MFA + dual-control + tamper-evident audit | WebAuthn, four-eyes, hash-chained `audit_logs` | 02 §9.3 |
| `user_notifications` table | Events + anti-spam | 02 §10.4 |
| Police / STPLP capture | `police_report_number` + `is_legal_hold` | 02 §3.3, §10.5 |

---

## 2. Recommendations at This Moment (Proposed — NOT yet confirmed)

These are recommendations **I currently endorse** but the product owner has **not yet confirmed**. Each needs a decision before implementation.

### R-1 — Contextual Account/Name Masking (Discussion started — unresolved)

**Question raised**: "Do we really need to mask account name & numbers if the goal is just to check whether an account has been reported?"

**My recommendation**:
- Keep masking as the **default** (prevents reverse-scraping into a doxing database, defamation liability under UU ITE / PDPA / POFMA, and bulk enumeration).
- **BUT add exact-match disclosure**: when a user checks an entity with the *full* account number or a scanned QR (i.e., they already hold the identifier), the profile SHOULD show the **holder / merchant name** — this is the **single most valuable anti-scam signal** (scammer says "Joko," account holder is "Budi" → obvious scam).
- Distinguish name confidence: display **"Verified owner name"** only when owner-claimed/proven; otherwise **"Reported recipient name (from N reports) — verify independently."**
- Surfaces: exact-match check → reveal; partial search/autocomplete → masked (search likely not needed in MVP); any "list of reported accounts" view → masked forever.
- Admin/verified-fraud entities → full disclosure allowed.

> **⚠️ Needs confirmation**: adopt or reject revised masking policy. Pending, the *current* docs still default to full masking with only masked display.

### R-2 — Final MVP Feature Scope (Phase 3B / 4B selection)

Not decided which proposed features are **must-have** vs **stretch** for the hackathon. Candidates (all web-first; chat bots deferred via ADR-015):

- **Strong recommend (build)**: Recipient Name Check (R-1), Fresh bad-review interstitial, High-risk cooling-off timer, Hotline one-tap directory, Scam Playbook library (1-2 pages), Scam Simulator, Trust Rank Ladder (lite), Pioneer Warn badge, Diligence Receipt.
- **Good but optional**: Share-to-Check, Watchlist alerts, Verified Reporter badge, Warning card generator, Recovery wizard, too-good-to-be-true checker, 3-2-1 rule.
- **Skip for hackathon MVP** (roadmap only): everything in post-MVP lists (bots, extension, IVR, syndicate graph, white-label widget, community squads, etc.).

> **⚠️ Needs confirmation**: final MVP cut-list so Phase 0 scaffolding can proceed.

### R-3 — Which reports move the risk score

Recommendation: only `admin_verified` or high-confidence-forensic reports ("evidence-grade rule") can move the score *band*; raw community reports influence but cannot alone push to CRITICAL. Accept? (Partially in docs §5.1/§5.2; precise weighting TBD during Phase 6.)

### R-4 — Real government integration priority queue

Post-MVP, order suggested: **(1) cekrekening.id mock → (2) real cekrekening.id → (3) PDRM Semak Mule (MY) → (4) SPF ASC (SG)**. Confirm as the B2G roadmap sequence.

### R-5 — Launch market for seed data

Recommendation: **Indonesia (QRIS + BCA/BRI/Mandiri + GoPay/OVO)** first for the demo data; other countries in schema but empty. Confirm.

---

## 3. Gaps & Open Questions Requiring CONFIRMATION

These are **explicit confirm-later items** — a future agent must ask the product owner before/while resolving:

| # | Open item | Type | Who confirms |
|---|-----------|------|--------------|
| G-1 | Masking policy (R-1) — exact-match name disclosure | Product decision | Owner |
| G-2 | Final MVP feature cut-list (R-2) | Product decision | Owner |
| G-3 | Evidence-grade scoring weight (R-3) | Product/tech | Owner + Developer |
| G-4 | B2G country priority (R-4) | Product decision | Owner |
| G-5 | Launch market seed data (R-5) | Product decision | Owner |
| G-6 | Team/admin model for MVP — who are the admins in the demo? | Ops | Owner |
| G-7 | Hosting/cloud preference (Vercel/Railway/Fly.io/R2 vs AWS) | Tech ops | Owner |
| G-8 | Real bank directory licensing — using real bank code maps OK in demo? | Legal/compliance | Owner + Legal |
| G-9 | Gemini API key / Google Cloud project for the demo (or mock-only?) | Ops | Owner |
| G-10 | Language scope for MVP UI (`en` + `id` only, or more?) — i18n §10.1 | Product | Owner |
| G-11 | Currency scope — is IDR the only demo currency, or multi-currency in seed data? | Product | Owner |
| G-12 | Do we need Terms/Privacy pages drafted for the demo, or placeholder links? | Legal/ops | Owner |
| G-13 | Reviewer flagged "right to erasure" vs "HMAC index" tension — need erasure semantics spec confirmed (tombstone approach) | Tech/legal | Developer + Owner |
| G-14 | Are we comfortable showing **reported-account listing** anywhere in MVP (doxxing surface)? Recommend NO. | Product | Owner |
| G-15 | Notification provider (Resend/Postmark/Twilio for SMS?) — env-gated | Tech ops | Developer + Owner |

---

## 4. Recommended Next Steps (for whoever picks this up)

1. **Confirm G-1/G-2 first** — they gate Phase 0/1 scope.
2. **Scaffold Phase 0** (repo, docker compose, alembic migrations for the full schema incl. `report_votes`, `user_notifications`, hash-chained `audit_logs`, `search_events_daily`, `entity_search_stats`).
3. Build resolver (Phase 1) with **exact-match name disclosure** (if G-1 confirmed) + homoglyph guard.
4. Phase 2 reporting with fail-closed redaction + upload security + quotas.
5. Then Phase 3/3B intel + engagement features per confirmed cut-list.
6. Re-run the 3-agent review at end of Phase 2 for course-correction.

---

*Continue from the handoff message appended to the README.*