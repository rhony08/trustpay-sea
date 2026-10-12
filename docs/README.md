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

> **Note**: `history/` contains earlier drafts from a prior AI workflow that were cut off mid-generation. This `docs/` folder is the authoritative, recrafted planning set.