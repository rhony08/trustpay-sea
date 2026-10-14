# TrustPay SEA — Planning Documentation

**Product**: BFSI: Intelligent Risk, Fraud & Financial Experiences
**Working Name**: TrustPay SEA — *The Truecaller & Google Reviews for Southeast Asian Digital Payments*

This folder contains the complete planning, design, and implementation documentation for the product. All documents are self-contained and can be read in any order, but the recommended reading order is numbered.

## Document Index

| # | Document | Purpose |
|---|----------|---------|
| 01 | [Product Blueprint](01-product-blueprint.md) | Vision, problem context, personas, workflows, feature spec (incl. search intelligence, AI augmentation, web-first community features, security-awareness features), MVP scope, success metrics, roadmap |
| 02 | [Technical Design Document](02-technical-design.md) | System architecture, data model, API contracts, AI/forensics pipeline, risk scoring, security & hardening appendix, non-functional requirements, operations |
| 03 | [Architecture Decision Records](03-architecture-decision-records.md) | 15 engineering decisions (ADRs) with context, options, and rationale |
| 04 | [Implementation Plan](04-implementation-plan.md) | Phased delivery plan (Phase 0–7 + 3B/4B) with granular tasks, acceptance criteria, and verification plan |
| 05 | [Gap Analysis & Open Decisions](05-gap-analysis.md) | Resolved gaps, current recommendations (incl. masking-policy recommendation), all open questions needing owner confirmation, handoff notes |

## Quick Summary

TrustPay SEA is a **community-driven payment-risk & reputation registry** for Southeast Asia that:

1. Lets anyone **look up a bank account or scan a QR code** (QRIS, DuitNow, PromptPay, PayNow, VietQR, QR Ph) before paying.
2. Lets victims **submit fraud reports** (account/QR + reason + optional image evidence).
3. Lets the community **review and upvote/downvote** reports — the Truecaller / Google Reviews experience.
4. Lets users **flag invalid reviews** (spam, defamation, incorrect account).
5. Lets a legitimate **account owner claim & dispute** reviews — but they must prove ownership *and* provide a reason, protecting against both smear-campaigns and greedy takedowns by scammers.
6. Supports **admin manual verification** with AI-assisted forensics (slip OCR, tamper detection, duplicate detection, review-bomb detection).
7. Produces an **explainable 0–100 trust/risk score** for every entity.
8. Shows **search intelligence** on every lookup — if it was ever reported, how many times it's been searched, 7d/30d trends, last-searched recency — plus a **grounded AI entity summary** and optional **Google Fact Check Tools** enrichment.
9. Ships an **open Public API** (OpenAPI 3.0, `screen/account`, `screen/qr`), so communities, payment gateways, and *future government platforms* can integrate with our standard (real gov integration with cekrekening.id / PDRM Semak Mule / SPF ASC / MDES AOC / NCSC / BSP IACAT is "Post-MVP · B2G", behind permissions).

The long-term vision turns this into a **B2G/B2B infrastructure**: syncing with government fraud registries, and exposing a sub-50ms pre-transfer screening API for banks & e-wallets. **Note**: real government integrations require permissions/MoUs that take time — so we deliver the Open Public API first, and wire gov connectors as adapters later.

---

## 🤖 Handoff Message for the Next AI Agent

> **You are resuming work on TrustPay SEA** (product: BFSI — Intelligent Risk, Fraud & Financial Experiences). Target market: SEA. Stack direction fixed in Doc 02: Next.js 15 PWA + FastAPI + PostgreSQL 16 + Redis + R2/S3 + Gemini. **Web-first scope** (no chat bots — see ADR-015).
>
> **✅ G-1/G-2 ARE RESOLVED (2026-10-14, owner-confirmed)** — Phase 0/1 scope is unblocked:
> - **G-1 → ADR-016**: contextual exact-match name disclosure. Exact full-account/QR lookup reveals holder/merchant name with confidence label ("Verified owner name" only when ownership proven, else "Reported recipient name (from N reports) — verify independently"). Partial/list views masked forever; no reported-accounts listing in MVP.
> - **G-2 → strong-recommend cut-list** for Phases 3B/4B: Recipient Name Check, fresh bad-review interstitial, cooling-off timer, hotline directory, Scam Playbook (1-2 pages), Scam Simulator, Trust Rank Ladder (lite), Pioneer Warn badge, Diligence Receipt. Optional set + post-MVP → roadmap only.
> - **G-5**: Indonesia first (QRIS + BCA/BRI/Mandiri + GoPay/OVO seed data). **G-9**: mock AI, no Gemini key. **G-10**: UI ships `en` + `id`. **G-14**: NO listing view (via ADR-016).
>
> **Before writing any code, read in this order:**
> 1. **`05-gap-analysis.md`** — open items still needing owner input (G-3…G-15 minus resolved) + recommendations. Ask the owner before overriding any G-item or R-recommendation.
> 2. `01-product-blueprint.md` — vision, personas, feature spec, trust-band semantics.
> 3. `02-technical-design.md` — architecture, full SQL schema (incl. `report_votes`, `user_notifications`, hash-chained `audit_logs`, `identity_trust`, KMS-keyed account hashing), API contracts, risk formula, Security/Hardening appendix, non-functional requirements.
> 4. `03-architecture-decision-records.md` — 16 ADRs; the recent ones (013/014/015/016) encode critical security & scope decisions. DO NOT silently reverse them.
> 5. `04-implementation-plan.md` — Phase 0–7 + 3B/4B tasks with acceptance criteria. Follow the phases in order; each phase must produce a verifiable demo.
>
> **Critical invariants you must preserve (do not regress):**
> - Account numbers stored only as **KMS-keyed HMAC** with `hash_version` — never cleartext index. Public surfaces masked by default; holder-name disclosure is exact-match-only (ADR-016).
> - AI summaries are **grounded/untrusted-input** (prompt-injection-proof); report/OCR/metadata text is never treated as instructions; adversarial injection tests are a **blocking CI gate**.
> - **Rise-only** dispute freeze — never reduce a verified/high score. Identity-graph anti-brigading (`identity_trust` starts at 10, not 50).
> - Fail-closed PII redaction: unredacted evidence is never published.
> - MFA (WebAuthn) + four-eyes dual-control + hash-chained audit for admin destructive actions.
> - One canonical report-category enum shared by DB, NLP, and API.
> - Moderate when in doubt: **ask the product owner before overriding any G-item or R-recommendation.**
>
> **Conventions**: conventional commits (`feat/fix/docs/refactor/test` scoped); tests gate every todo item; auto-commit after each verified task. Docs are the source of truth — update them when implementation reveals a change.
>
> — *Handover recorded on 2026-10-12. G-1/G-2 resolved 2026-10-14. Repo: github.com/rhony08/trustpay-sea*