# 05 — Gap Analysis & Open Decisions (Handoff Notes)

**Doc Version**: 1.1 · **Status**: Living document — update as decisions are confirmed
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
| Masking policy (G-1/R-1) | **ADOPTED**: contextual exact-match name disclosure — see ADR-016 | ADR-016, 02 §9.1 |
| MVP cut-list (G-2/R-2) | **DECIDED**: strong-recommend set — Recipient Name Check, fresh bad-review interstitial, cooling-off timer, hotline directory, Scam Playbook (1-2 pages), Scam Simulator, Trust Rank Ladder (lite), Pioneer Warn badge, Diligence Receipt. Optional set + post-MVP items → roadmap | 04 Phases 3B/4B |
| Launch market (G-5/R-5) | **CONFIRMED**: Indonesia first (QRIS + BCA/BRI/Mandiri + GoPay/OVO); other SEA countries in schema, empty | 01 §11 |
| Gemini / language (G-9/G-10) | **CONFIRMED**: mock AI (no key — fixtures, graceful degradation per ADR-012); UI ships `en` + `id` | 02 §10.1 |

---

## 2. Recommendations at This Moment (Proposed — NOT yet confirmed)

These are recommendations **I currently endorse** but the product owner has **not yet confirmed**. Each needs a decision before implementation.

### R-1 — Contextual Account/Name Masking ✅ ADOPTED 2026-10-14 → ADR-016

Owner confirmed the recommendation: keep masking as default; reveal holder/merchant name on **exact-match** lookups only, with confidence labels ("Verified owner name" vs "Reported recipient name (from N reports) — verify independently"). Partial/list views masked forever; no reported-accounts listing in MVP (G-14 = NO). Full decision record: **ADR-016**.

### R-2 — Final MVP Feature Scope ✅ DECIDED 2026-10-14

Owner confirmed the **strong-recommend set** for Phases 3B/4B:
- **Build**: Recipient Name Check (implements ADR-016), Fresh bad-review interstitial, High-risk cooling-off timer, Hotline one-tap directory, Scam Playbook library (1-2 pages), Scam Simulator, Trust Rank Ladder (lite), Pioneer Warn badge, Diligence Receipt.
- **Roadmap only** (not hackathon): Share-to-Check, Watchlist alerts, Verified Reporter badge, Warning card generator, Recovery wizard, too-good-to-be-true checker, 3-2-1 rule, and all post-MVP lists.

### R-3 — Which reports move the risk score

Recommendation: only `admin_verified` or high-confidence-forensic reports ("evidence-grade rule") can move the score *band*; raw community reports influence but cannot alone push to CRITICAL. Accept? (Partially in docs §5.1/§5.2; precise weighting TBD during Phase 6.)

### R-4 — Real government integration priority queue

Post-MVP, order suggested: **(1) cekrekening.id mock → (2) real cekrekening.id → (3) PDRM Semak Mule (MY) → (4) SPF ASC (SG)**. Confirm as the B2G roadmap sequence.

### R-5 — Launch market for seed data ✅ CONFIRMED 2026-10-14

**Indonesia first** (QRIS + BCA/BRI/Mandiri + GoPay/OVO) for demo seed data; other SEA countries present in schema but empty. Closes G-5.

---

## 3. Gaps & Open Questions Requiring CONFIRMATION

These are **explicit confirm-later items** — a future agent must ask the product owner before/while resolving:

| # | Open item | Type | Who confirms | Status |
|---|-----------|------|--------------|--------|
| G-1 | Masking policy (R-1) — exact-match name disclosure | Product decision | Owner | ✅ **RESOLVED 2026-10-14 — ADR-016** |
| G-2 | Final MVP feature cut-list (R-2) | Product decision | Owner | ✅ **RESOLVED 2026-10-14 — strong-recommend set** |
| G-3 | Evidence-grade scoring weight (R-3) | Product/tech | Owner + Developer | Open (Phase 6) |
| G-4 | B2G country priority (R-4) | Product decision | Owner | Open (post-MVP) |
| G-5 | Launch market seed data (R-5) | Product decision | Owner | ✅ **RESOLVED 2026-10-14 — Indonesia first** |
| G-6 | Team/admin model for MVP — who are the admins in the demo? | Ops | Owner | Open (Phase 0/seed) |
| G-7 | Hosting/cloud preference (Vercel/Railway/Fly.io/R2 vs AWS) | Tech ops | Owner | Open (Phase 7) |
| G-8 | Real bank directory licensing — using real bank code maps OK in demo? | Legal/compliance | Owner + Legal | Open (Phase 1) |
| G-9 | Gemini API key / Google Cloud project for the demo (or mock-only?) | Ops | Owner | ✅ **RESOLVED 2026-10-14 — mock AI, no key** |
| G-10 | Language scope for MVP UI (`en` + `id` only, or more?) — i18n §10.1 | Product | Owner | ✅ **RESOLVED 2026-10-14 — `en` + `id`** |
| G-11 | Currency scope — is IDR the only demo currency, or multi-currency in seed data? | Product | Owner | Open (assume IDR-primary per G-5) |
| G-12 | Do we need Terms/Privacy pages drafted for the demo, or placeholder links? | Legal/ops | Owner | Open (Phase 7) |
| G-13 | Reviewer flagged "right to erasure" vs "HMAC index" tension — need erasure semantics spec confirmed (tombstone approach) | Tech/legal | Developer + Owner | Open (Phase 7/DSAR) |
| G-14 | Are we comfortable showing **reported-account listing** anywhere in MVP (doxxing surface)? Recommend NO. | Product | Owner | ✅ **RESOLVED via ADR-016 — NO listing view in MVP** |
| G-15 | Notification provider (Resend/Postmark/Twilio for SMS?) — env-gated | Tech ops | Developer + Owner | Open (Phase 7) |

---

## 4. Recommended Next Steps (for whoever picks this up)

1. ~~Confirm G-1/G-2 first~~ — ✅ **DONE 2026-10-14** (ADR-016 + strong-recommend cut-list). Phase 0/1 scope is unblocked.
2. **Scaffold Phase 0** (repo, docker compose, alembic migrations for the full schema incl. `report_votes`, `user_notifications`, hash-chained `audit_logs`, `search_events_daily`, `entity_search_stats`).
3. Build resolver (Phase 1) with **exact-match name disclosure** (G-1 confirmed → ADR-016) + homoglyph guard.
4. Phase 2 reporting with fail-closed redaction + upload security + quotas.
5. Then Phase 3/3B intel + engagement features per confirmed cut-list (R-2 strong set).
6. Re-run the 3-agent review at end of Phase 2 for course-correction.

---

*Continue from the handoff message appended to the README.*