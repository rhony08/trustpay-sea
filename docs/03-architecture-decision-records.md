# 03 — Architecture Decision Records (ADRs): TrustPay SEA

**Status**: Approved for planning · **Version**: 1.0

This document captures the key engineering decisions with their context, options considered, chosen decision, and consequences. New ADRs are added as material decisions are made during implementation.

---

## Index

- [ADR-001: Hybrid Client-Side & Server-Side EMVCo QR TLV Parsing](#adr-001-hybrid-client-side--server-side-emvco-qr-tlv-parsing)
- [ADR-002: Salted HMAC-SHA256 Canonical Lookup Index (No Cleartext Account Storage)](#adr-002-salted-hmac-sha256-canonical-lookup-index-no-cleartext-account-storage)
- [ADR-003: Explainable Bayesian Composite Risk Scoring vs. Black-Box Deep Learning](#adr-003-explainable-bayesian-composite-risk-scoring-vs-black-box-deep-learning)
- [ADR-004: Multi-Tier Owner Verification with "Under Dispute" Safe-Harbor Freeze](#adr-004-multi-tier-owner-verification-with-under-dispute-safe-harbor-freeze)
- [ADR-005: Asynchronous Forensics Pipeline with Mandatory PII Redaction](#adr-005-asynchronous-forensics-pipeline-with-mandatory-pii-redaction)
- [ADR-006: Open Public API First — Gov Platform Connectors as Later Adapters](#adr-006-open-public-api-first--gov-platform-connectors-as-later-adapters)
- [ADR-007: Sub-50ms B2B Screening via Redis Caching & Token-Bucket Rate Limiting](#adr-007-sub-50ms-b2b-screening-via-redis-caching--token-bucket-rate-limiting)
- [ADR-008: Event-Driven Modular Monolith (Single Deployable Service)](#adr-008-event-driven-modular-monolith-single-deployable-service)
- [ADR-009: AI-Assisted Admin Moderation (Human-in-the-Loop)](#adr-009-ai-assisted-admin-moderation-human-in-the-loop)
- [ADR-010: Neutral Risk Language & PII Masking as Legal Shield (UU ITE / PDPA)](#adr-010-neutral-risk-language--pii-masking-as-legal-shield-uu-ite--pdpa)
- [ADR-011: Aggregate, Privacy-Safe Search Intelligence Counters](#adr-011-aggregate-privacy-safe-search-intelligence-counters)
- [ADR-012: AI Augmentation & Google Fact Check Tools as Optional Enrichment](#adr-012-ai-augmentation--google-fact-check-tools-as-optional-enrichment)
- [ADR-013: HSM/KMS-Keyed Account Hash + Prompt-Injection-Proof AI Boundary](#adr-013-hsmkms-keyed-account-hash--prompt-injection-proof-ai-boundary)
- [ADR-014: Identity-Graph Anti-Brigading & Freeze-Thats-Rise-Only](#adr-014-identity-graph-anti-brigading--freeze-thats-rise-only)
- [ADR-015: Web-First Scope for Hackathon MVP (No Chat Bots)](#adr-015-web-first-scope-for-hackathon-mvp-no-chat-bots)
- [ADR-016: Contextual Exact-Match Name Disclosure (Masking + Holder-Name Reveal)](#adr-016-contextual-exact-match-name-disclosure-masking--holder-name-reveal)
- [ADR-017: Python Backend Runtime & Security Primitives](#adr-017-python-backend-runtime--security-primitives)

---

## ADR-001: Hybrid Client-Side & Server-Side EMVCo QR TLV Parsing

**Status**: Accepted

### Context
Users encounter scam QR codes (QRIS in Indonesia, DuitNow in Malaysia, PromptPay in Thailand) on e-commerce, social media, or physical stickers. We need to extract merchant name, city, acquirer AID, and National Merchant ID (NMID) from camera scans or image uploads.

### Options Considered
1. **Server-only parsing**: Upload image → server decodes QR and parses TLV. Simple but adds latency and server load on low-quality scans.
2. **Client-only parsing**: Decode + parse entirely in browser JS. Instant feedback but trusts client input; an attacker could tamper the submitted payload.
3. **Hybrid (Selected)**: Client decodes for instant UI preview; server re-parses, validates CRC-16 (Tag 63), canonicalizes, and stores the standardized result.

### Decision
Implement the **Hybrid Model**. Frontend uses `html5-qrcode`/`jsQR` for instant preview; backend owns the authoritative parse and CRC validation.

### Consequences
- **+**: Zero perceived latency for preview; reduced server load on garbage scans.
- **−**: Parser must be maintained in both TS and Python (kept thin/symmetric via shared TLV test vectors).

---

## ADR-002: Salted HMAC-SHA256 Canonical Lookup Index (No Cleartext Account Storage)

**Status**: Accepted

### Context
Bank accounts are sensitive personal data (PDPA/UU PDP). Raw storage enables bulk scraping and leaks PII. But screening needs deterministic exact lookup.

### Options Considered
1. **Cleartext storage + SQL ILIKE**: simple, but scrapable and non-compliant.
2. **Homomorphic encryption**: secure, far too slow for sub-50ms lookups.
3. **Canonical normalization + HMAC-SHA256 index (Selected)**: strip formatting → canonical key `country:institution:account` → `HMAC_SHA256(key, server_salt)` stored as the unique index. Public surfaces show only masked (`883-****-831`).

### Decision
Use **KMS-keyed HMAC-SHA256 canonical lookup index** (see ADR-013) with per-row `hash_version`. Salt/key lives in the KMS/HSM (never beside the DB); rotation is possible because a `hash_version` and re-encryption path are planned from day one.

### Consequences
- **+**: No cleartext enumeration; compliant with data minimization; deterministic exact match.
- **−**: No fuzzy/partial substring search — users must enter (or scan) the exact correct number; we enforce exact input with client-side format hints and QR scanning to reduce typos. Low-entropy accounts are brute-forceable if the key leaks → hence KMS/HSM key management and lookup-oracle rate limiting (ADR-013).

---

## ADR-003: Explainable Bayesian Composite Risk Scoring vs. Black-Box Deep Learning

**Status**: Accepted

### Context
BFSI contexts demand explainability when a merchant disputes a score. A pure DNN "score = 73" with no rationale is not acceptable for defamation defense.

### Options Considered
1. **End-to-end DNN**: high pattern recognition, unexplainable.
2. **Majority voting**: simple count; easily review-bombed.
3. **Explainable Bayesian composite scorer (Selected)**: formulaic combination of gov sanctions, admin verifications, community volume/severity/upvotes, forensic signals, dispute freeze, merchant KYC. Each score ships with a factor breakdown.

### Decision
Adopt the **Explainable Bayesian Composite Scorer** with public factor breakdown and velocity dampening.

### Consequences
- **+**: Fully auditable, defensible in disputes, simple to calibrate, easy to unit-test.
- **−**: Requires periodic re-calibration as scam patterns evolve; we add new factors via ADR when needed.

---

## ADR-004: Multi-Tier Owner Verification with "Under Dispute" Safe-Harbor Freeze

**Status**: Accepted

### Context
Legitimate merchants, MSMEs, freelancers are vulnerable to review-bombing, extortion, competitor sabotage. Owners need a fair way to challenge reviews, but scammers must not be able to erase valid fraud warnings.

### Options Considered
1. **Instant automatic takedown on owner request**: far too abusable.
2. **Admin-only manual adjudication only**: slow; merchant reputation burns while waiting.
3. **Multi-tier proof + instant safe-harbor freeze + admin removal (Selected)**: Owner must prove identity (passbook/mbanking/NMID/micro-deposit); once proven, entity gets `is_under_dispute`, score capped at ≤45, public "Dispute" badge. Removal still requires admin adjudication.

### Decision
Implement multi-tier verification with immediate safe-harbor score freeze. **Removal of a review is never automatic** — it always passes through admin or settlement confirmation.

### Consequences
- **+**: Defends against smears; prevents scammer takedowns; legally defensible.
- **−**: Requires robust document forgery detection on owner KYC (OCR + human review for low-confidence docs).

---

## ADR-005: Asynchronous Forensics Pipeline with Mandatory PII Redaction

**Status**: Accepted

### Context
Victims upload screenshots full of PII (balances, IDs, addresses, messenger avatars). Public display of unredacted evidence violates privacy law and hurts trust.

### Options Considered
1. **Client-side manual cropping/redaction**: unreliable, victims will miss things.
2. **Synchronous server redaction**: blocks submission by 4–8s.
3. **Async event-driven redaction + forensics (Selected)**: Accept report `202` immediately → queue → worker redacts PII, OCRs, tamper-checks, pHash-dedups. Public bucket holds only redacted copies; originals live in encrypted quarantine.

### Decision
Adopt **asynchronous event-driven forensics** via Redis Streams (or RabbitMQ), with mandatory PII redaction before any public persistence.

### Consequences
- **+**: Fast UX; privacy compliance by construction; enables automated fraud-slip detection.
- **−**: Requires queue infra + worker observability; means report status has a "processing" state in UI.

---

## ADR-006: Open Public API First — Gov Platform Connectors as Later Adapters

**Status**: Accepted

### Context
The user explicitly wants SEA government integration (cekrekening.id, PDRM Semak Mule, SPF ASC, MDES AOC, NCSC, BSP IACAT) but obtaining official permissions/MoUs takes a long time. We must not block the product on approvals.

### Options Considered
1. **Hard-code integration with cekrekening.id now**: blocked by permissions, fragile, stalls progress.
2. **Wait until permissions, then build integration**: delays any ecosystem value; unknown timeline.
3. **Open Public API first + adapter layer later (Selected)**: Build a documented, versioned public API now. Government/ecosystem connectors become adapters *over our own API* (or pulling their feeds via `GovAdapter` interface) that we activate when permissions are granted. Ship a **mock adapter + fixtures** in MVP to prove the flow.

### Decision
**Public API is an MVP deliverable.** The `GovAdapter` interface is defined in code and docs now; real national integrations are **Post-MVP · B2G** post-permission wiring.

### Consequences
- **+**: Ecosystem value (communities, gateways, NGOs) delivered early; gov integration becomes "just build one adapter"; demo shows B2G direction.
- **−**: MVP does not yet have *real* gov data; we clearly label mock data and design the risk engine to accept the gov signal later.

---

## ADR-007: Sub-50ms B2B Screening via Redis Caching & Token-Bucket Rate Limiting

**Status**: Accepted

### Context
Banking/e-wallet integrations will call our screening API mid-transfer; >100ms creates friction. Commercial SLA requires <45ms.

### Options Considered
1. **Direct PostgreSQL queries**: 80–180ms typical; read-heavy.
2. **Redis-accelerated cache + token-bucket rate limiting (Selected)**: Precompute entity assessment; cache by account_hash/QR with TTL 15min; write-through invalidation on report/score change; token bucket per API key/IP.

### Decision
Cache risk assessments in Redis with write-through invalidation; enforce rate limits via token bucket.

### Consequences
- **+**: Meets <45ms target; absorbs traffic spikes (payday, festivals).
- **−**: Requires cache invalidation discipline; Redis failover needed for prod (single box OK for MVP/sandbox).

---

## ADR-008: Event-Driven Modular Monolith (Single Deployable Service)

**Status**: Accepted

### Context
A hackathon-scale product must be buildable by a small team in weeks, yet remain evolvable into services (when B2B/B2G demand separates concerns).

### Options Considered
1. **Full microservices**: infra overhead too high for MVP.
2. **Single-file app (one package, no internal boundaries)**: too entangled to evolve cleanly.
3. **Modular monolith with event bus (Selected)**: One deployable FastAPI app, but clear modules (resolver, reports, disputes, admin, scoring) with in-process boundaries, plus Redis Streams as the asynchronous cut point for AI workers.

### Decision
Implement as an **event-driven modular monolith**. AI/non-blocking work is decoupled via the queue so modules can later be extracted to workers without re-architecture.

### Consequences
- **+**: Fast iteration, single deploy, testable DB; scale path ready.
- **−**: Discipline required to keep module boundaries clean.

---

## ADR-009: AI-Assisted Admin Moderation (Human-in-the-Loop)

**Status**: Accepted

### Context
Automated takedowns/approvals would risk unfairness and legal exposure; pure manual moderation is slow. We need AI to *assist* without *deciding* high-stakes outcomes.

### Options Considered
1. **Full auto-moderation by AI**: dangerous for defamation and disputes.
2. **Manual everything**: slow queue, poor UX, low admin throughput.
3. **AI-assisted triage (Selected)**: AI computes credibility scores, OCR/tamper signals, duplicate matches, typology; admins review a rich side-by-side panel and make the final call. Low-risk actions (e.g., obvious spam) can be AI-suggested but admin-confirmed. Audit-log everything.

### Decision
Human-in-the-loop moderation with AI decision support for all actions that alter published content, scores, or ownership.

### Consequences
- **+**: Fair, defensible, scalable admin workload.
- **−**: Admin recruitment/training needed; AI signals must be displayed transparently in the admin panel.

---

## ADR-010: Neutral Risk Language & PII Masking as Legal Shield (UU ITE / PDPA)

**Status**: Accepted

### Context
Operating a fraud-intelligence registry in SEA exposes us to defamation laws (Indonesia UU ITE, Malaysia Defamation Act, Singapore POFMA/POHA) and data-protection regulations (PDPA, UU PDP). Labeling an unverified person a "criminal" is dangerous.

### Options Considered
1. **Verdict-style language** ("PENIPU", "scammer"): high legal risk, community-friendly.
2. **Fully anonymized, no labels**: loses utility.
3. **Neutral, objective, masked (Selected)**: "3 community reports of unfulfilled delivery" instead of "scammer"; masked account numbers; evidence redacted; dispute safe-harbor; full audit trail.

### Decision
Adopt neutral risk language + mandatory PII masking + transparent due process across UI, API, and evidence media.

### Consequences
- **+**: Legally defensible, builds trust with merchants and regulators.
- **−**: Slightly less punchy marketing copy; requires careful UX copywriting guidelines.

---

## ADR-011: Aggregate, Privacy-Safe Search Intelligence Counters

**Status**: Accepted

### Context
The product spec calls for showing "times searched", "searches 7d/30d", and "last searched" on entity lookup profiles — a strong engagement signal for users checking whether an account/QR is being actively watched. But directly storing per-user search behavior and showing individual history raises privacy concerns (PDPA/UU PDP).

### Options Considered
1. **Per-user search logs + per-user history**: powerful feature (like Truecaller history) but stores sensitive behavioral data and risks law-enforcement/lawyer subpoena burden; heavier compliance.
2. **No search stats at all**: misses the requested value.
3. **Aggregate, rounded, threshold-gated counters (Selected)**: store only daily aggregate counts per entity (`search_events_daily`), roll into 7d/30d/all-time windows via cron; display rounded ("~1.2k") only when above a minimum threshold; never persist which user searched.

### Decision
Track **aggregate, privacy-safe search counters** only. No per-user search history. Display gated by rounding + minimum threshold.

### Consequences
- **+**: Useful popularity/recency signal; fully privacy-compliant; avoids risky behavioral data.
- **−**: Cannot offer per-user "search history" feature later without a new ADR re-consenting users.

---

## ADR-012: AI Augmentation & Google Fact Check Tools as Optional Enrichment

**Status**: Accepted

### Context
Users searching an entity benefit from (a) an instant plain-language summary of its report history, and (b) related public fact-checks about the scam type. The product direction mentions integrating "AI Search or Google Fact Checker".

### Options Considered
1. **Authoritative AI "verdict" generation** ("this account is a scammer"): risky, hallucination-prone, defamation exposure.
2. **No enrichment**: the raw report list is less helpful for laypeople.
3. **Grounded AI summary + external fact-check links (Selected)**:
   - AI summary is **template-driven over internal structured data only**, with strict system instructions not to invent facts (Gemini, cached per entity).
   - **Google Fact Check Tools API** (`factchecktools.googleapis.com`) queried by category/keywords → returned as external `related_fact_checks[]` references, explicitly labeled, **never as a verdict on the specific entity**.
   - Entire fact-check integration is **optional** (env-gated `FACTCHECK_API_KEY`); mock-first, graceful empty state.

### Decision
Ship **grounded AI entity summaries** as a core feature, and **Google Fact Check Tools as optional enrichment** behind a config flag.

### Consequences
- **+**: Big UX jump in "search intelligence"; aligns with AI Search direction; low legal risk by keeping summaries grounded and fact-checks external.
- **−**: Requires explicit source-grounded prompting + evaluation tests; fact-check API requires Google account/API key (optional); needs graceful degradation offline.

---

## ADR-013: HSM/KMS-Keyed Account Hash + Prompt-Injection-Proof AI Boundary

**Status**: Accepted

### Context
Security audit (A-C5, A-C3) flagged two architectural weaknesses: (1) a single low-entropy HMAC key would let a DB/key compromise reverse the whole account registry (and salt rotation was impossible without re-collecting); (2) the public AI entity summary ingests attacker-controlled report/OCR text, enabling prompt-injection that could poison the summary shown to every future payer.

### Options Considered
1. **Keep single global HMAC salt**: fast but single point of permanent compromise (rejected).
2. **HSM/KMS-keyed HMAC with `hash_version` + envelope encryption (Selected)**: high-entropy key in KMS/HSM; envelope-encrypt account under a data key (reversible ciphertext), HMAC as the index; rotation = re-encrypt, not re-collect; `hash_version` on each row.
3. **Raw LLM summary from free text**: fastest but permits injection (rejected).
4. **Structured-output + grounding contract for all AI (Selected)**: treat all report/OCR/metadata text as untrusted; force JSON-schema output; derive human summaries server-side from validated fields; grounding check rejects facts not present in input; adversarial injection test suite is a blocking CI gate.

### Decision
Implement **KMS/HSM-keyed HMAC with envelope encryption + `hash_version`**, and enforce an **untrusted-input / structured-output AI boundary** with a grounding check for every public-facing AI output.

### Consequences
- **+**: Registry not permanently reversible on key leak; AI summary not poisonable by report text; defensible under UU PDP/PDPA audits.
- **−**: Slightly higher infra cost (KMS/HSM); AI prompts must be engineered as templates, not free-form.

---

## ADR-014: Identity-Graph Anti-Brigading & Freeze-That-Rises-Only

**Status**: Accepted

### Context
Security audit (A-C1, A-C2): the original anti-brigading detector counted "distinct users" with a reputation default of 50 — above the 40 threshold, so a sock-puppet network was invisible. Separately, the dispute freeze capped the *whole entity* at ≤45, letting a mule-operator claiming ownership drag an 88-score fraud account down to 45.

### Options Considered
1. **Keep raw count + default rep 50**: vulnerable (rejected).
2. **Human-identity graph + trust-weighted velocity (Selected)**: identity = device ∩ (IP/ASN + phone-verified) ∩ payment instrument; unverified-new accounts start at trust 10; EWMA z-score over 7-day baseline catches spaced-out attacks; per-entity hourly cap.
3. **Freeze that sets whole score=45**: abusable (rejected).
4. **Freeze that caps only score *increases* (Selected)**: `effective = max(score_without_recent_unverified, prior_verified_baseline)` — never lowers a verified/high score; badges inform, never mask.

### Decision
Adopt **identity-graph anti-brigading** and a **rise-only dispute freeze**. Ownership proof tiers T1/T2 prove control only; only T3 business-KYC or human-verified ownership may contest admin-verified/gov records.

### Consequences
- **+**: The score — the product's core asset — can't be gamed by sock puppets or mule operators.
- **−**: Requires device-fingerprint + phone-verification infrastructure; privacy constraints apply to identity clustering (fingerprints stored hashed, TTL-limited).

---

## ADR-015: Web-First Scope for Hackathon MVP (No Chat Bots)

**Status**: Accepted

### Context
Competing ideas (WhatsApp/Telegram check bot, IVR line, mobile-extension overlays) are high-wow, but the hackathon priority is a **web-based PWA** that works flawlessly end-to-end. Chat/telephony channels add deployment, bot-approval, and runtime complexity that dilute the core demo.

### Options Considered
1. **Build bot channel now**: high demo wow, but depends on external platform approval + long-running service; risk to hackathon delivery.
2. **Web-first (Selected)**: prioritize the Next.js PWA + Public API; deliver chat/SMS/IVR channels as **post-MVP roadmap** (documented in blueprint, implemented later behind the same `screen/*` API).
3. **Ignore non-web channels entirely**: loses a major distribution narrative (rejected).

### Decision
**Web-first MVP.** All MVP phases target the PWA + Public API. Non-web channels are post-MVP roadmap items, designed from day one to reuse the `screen/account` and `screen/qr` contracts.

### Consequences
- **+**: Single focused demo surface; faster delivery; the Public API keeps future channel options open.
- **−**: No WA/TG quick-check in the MVP demo (trade-off accepted for hackathon quality).

---

## ADR-016: Contextual Exact-Match Name Disclosure (Masking + Holder-Name Reveal)

**Status**: Accepted (owner-confirmed 2026-10-14 — closes G-1 / R-1)

### Context
The registry's most valuable anti-scam signal is a **name mismatch**: a scammer says the recipient is "Joko," but the account/QR holder is actually "Budi." Full masking (the pre-decision default) hides this signal. But unqualified name disclosure creates a doxing/defamation surface (UU ITE / PDPA / POFMA) and enables reverse-scraping into a "reported names" database.

### Options Considered
1. **Full masking everywhere (status quo)**: maximum legal safety, loses the name-mismatch signal — rejected as under-delivering on core value.
2. **Full name disclosure on every lookup**: strongest utility, highest defamation/doxing/enumeration risk — rejected.
3. **Contextual exact-match disclosure (Selected)**: the name is only revealed when the user *already holds the identifier in full* (typed the complete account number, or scanned the QR). Partial/autocomplete/list views stay masked forever — those are the enumerable surfaces.

### Decision
Adopt **contextual exact-match disclosure**:
- **Exact-match surface** (full account number submitted, or QR scanned/pasted EMVCo payload) → reveal holder/merchant name with a confidence label:
  - `"Verified owner name"` — only when ownership is proven (T1/T2/T3 or analyst-set `is_owner_verified`).
  - `"Reported recipient name (from N reports) — verify independently"` — otherwise.
- **Partial / autocomplete / any listing surface** → masked, forever. No "list of reported accounts" view ships in MVP (G-14 = NO).
- **Admin / `GOV_BLACKLISTED` / `ADMIN_CONFIRMED_FRAUD`** entities → full disclosure allowed.
- The reveal is conditional on *the requester already possessing the identifier* — we do not leak identifiers; we only confirm/refute the name against one the payer already holds.

### Consequences
- **+**: Catches the dominant SEA scam pattern (mule account under a different name) at the moment of payment decision.
- **−**: Name data sits closer to the public surface; mitigated by confidence labelling, exact-match-only gating, rate limiting, and the standing prohibition on bulk/list views.
- The `payment_entities.merchant_name` (QR merchant name from the EMVCo payload) was always shown — this ADR extends disclosure to the **holder name for bank-account lookups**, sourced from owner-KYC proof (verified) or report narratives (unverified, labelled as such).

---

## ADR-017: Python Backend Runtime & Security Primitives

**Status**: Accepted (2026-10-14 — Phase 0 implementation record)

### Context
Doc 02 fixes the stack at FastAPI / Python 3.11 / PostgreSQL 16 / Redis 7 / SQLAlchemy 2.0 / Alembic, but leaves the concrete runtime and security-primitive choices open. Phase 0 needs these pinned so the scaffold, auth, rate limiter, and tests are consistent from commit one.

### Decisions

| Area | Choice | Rationale / rejected alternatives |
|------|--------|-----------------------------------|
| DB access | **Async SQLAlchemy 2.0 + asyncpg + async Alembic** | FastAPI is async-native; sync SQLAlchemy would block the event loop under load. aiosqlite rejected for tests — we test against real PG (compose/CI services) so migrations and CHECK constraints are exercised. |
| JWT | **PyJWT, RS256 pinned, keypair on disk (`/run/secrets/*.pem`)** | Doc 02 §9.2 requires RS256/ES256 pinned and alg-confusion resistance; algorithm comes from config, never from the token header. python-jose rejected (historical CVEs). HS256 rejected (shared secret = verification key leakage risk). Dev keypair generated at container start; prod keys injected via secret manager. |
| Password hashing | **argon2id via `argon2-cffi`** (`time_cost=2, memory_cost=64MiB, parallelism=2`) | Doc 02 schema specifies argon2id. bcrypt rejected (no memory hardness). Params tunable via env later if needed. |
| Refresh-token rotation | **Token *family* tracked in Redis** (`auth:family:<id>` set of used refresh `jti`s, TTL 7d) | §9.2 requires rotation + reuse detection. No DB table exists for sessions in Doc 02's schema and adding one would drift from the approved data model; Redis is already infrastructure. Reuse of a burned `jti` → revoke the whole family (all tokens from that login session). Logout = family delete. |
| Scheduler | **APScheduler in-process (`AsyncIOScheduler`, UTC)** | Phase 0.5 acceptance only requires "clock job exists & runs on schedule". Airflow/cron containers rejected for MVP as infra overhead; jobs are written as plain async functions so a later move to a cron container or Celery beat is a config change, not a rewrite. Scheduler disable flag (`SCHEDULER_ENABLED=false`) for tests. |
| Canonical enums | **Shared `app/enums.py` (`StrEnum`)** mirroring DB CHECK constraints | Invariant: one taxonomy shared by DB, NLP, API. Python StrEnum is imported by models (CHECK constraint generation), API schemas, and later the NLP worker; DB CHECKs are generated from the same enum members so drift is a test failure, not a prod surprise. Native PG ENUM types rejected (harder to evolve; Alembic migration noise). |
| Rate limiting | **Redis Lua token bucket** (`rl:<scope>:<identity>`, continuous refill) | Matches ADR-007. Fixed-window rejected (burst-at-edge). Middleware implemented as a FastAPI dependency so it is testable per-route. |
| Tests | **pytest + pytest-asyncio + httpx ASGI client; real Postgres + Redis from compose / CI service containers** | Acceptance criteria demand migration-clean DB and real Redis rate limiting; mocking either would let schema/CHECK regressions slip through. |
| Web server | **uvicorn[standard]** behind Docker; single process for MVP | Modular monolith (ADR-008): one deployable. Multi-worker/process manager deferred to deploy phase. |

### Consequences
- **+**: Phase 0 scaffold is fully consistent with the security invariants (pinned alg, rotation with reuse detection, canonical enums); every primitive is directly testable.
- **−**: Local dev requires Docker (PG + Redis) — no pure-py fallback; APScheduler in-process means jobs don't survive multi-replica deployments (fine for MVP single-instance; documented as a Phase 7 deploy concern).
- Dev JWT keypair must never be reused in prod — the container generates one only when no key files are mounted.

---

## ADR-018: Hosting — GCE-first with a Portable Docker Compose

**Status**: Accepted (2026-10-14 — resolves G-7; owner-confirmed: must run on GCP, must also run on the owner's VPS)

### Context
The hackathon requires running on GCP **Compute Engine** (docs/07), which parked the earlier Cloud Run/Cloud SQL/Memorystore kit (`gcp/`). The same artifact must also deploy on the owner's plain VPS. Two hosting surfaces (managed vs single VM) and a "must work in both" constraint.

### Decision
- **One portable deploy unit**: the repo-root `docker-compose.yml` (postgres + redis + api + web) runs unchanged on a GCE `e2-small` VM *and* on a plain VPS. GCP is treated as "a bigger docker host", not a special case.
- **GCE is the primary cloud target**; the Cloud Run kit in `gcp/cloudrun` is retained as an optional alternative, not the primary path.
- **Dev conveniences are isolated** in `docker-compose.override.yml` (host-published DB/Redis ports), auto-loaded locally; production runs `docker compose -f docker-compose.yml` to skip them.
- **`NEXT_PUBLIC_API_URL` is a build arg** (inlined into the client bundle at build time) — documented, not a runtime env.
- Managed DB/cache (Cloud SQL + Memorystore) and a MIG are deferred to post-demo scale; the compose monolith (ADR-008) stays monolithic.

### Consequences
- **+**: identical image/runtime everywhere; no code paths specialised for GCP; the demo can be validated locally and on the VPS before GCP.
- **+**: satisfies the GCE-mandatory constraint while keeping the Cloud Run kit available.
- **−**: self-hosted Postgres on the boot/data disk means backups are snapshot-based (docs/07 §3, §6b), not managed PITR; single-VM means no horizontal scale (acceptable at demo scale).
- **−**: prod must remember `-f docker-compose.yml` to avoid the dev override.

---

## ADR-019: Pluggable AI Provider (mock | gcp | openrouter)

**Status**: Accepted (2026-10-14 — supersedes the "mock-only" reading of ADR-012)

### Context
ADR-012 fixed mock-first AI (no key required for dev). Real Gemini access is now available and the product deploys on GCP, so the forensics/classification/summary pipeline must be able to call a real model — while dev/CI keep running with no key and no network.

### Decision
- `AI_PROVIDER = mock | gcp | openrouter` (default `mock`). `gcp` = **Vertex AI via Application Default Credentials** (google-genai SDK, SEA region-pinned); `openrouter` = OpenAI-compatible gateway (openai SDK). SDKs lazy-imported.
- A configured provider that **cannot initialise** (missing creds/SDK) falls back to `mock` with a warning — dev/CI never need cloud credentials.
- All capabilities (PII-region detection, slip OCR, tamper signals, taxonomy classification, NER) go through one `StructuredAIProvider` contract: fixed prompt → JSON → validated domain objects + PII masking.
- **Redaction is fail-closed regardless of provider**: a provider error leaves the report `PROCESSING`/`FAILED`, never publishing unredacted evidence. Non-critical enrichment (OCR/tamper/typology/NER) degrades to the local heuristics on outage.
- The grounded entity **summary stays server-templated** (facts-only + grounding check), not model-generated.

### Consequences
- **+**: one switch for all AI; prod uses Vertex, alternatives use OpenRouter, dev/tests use mock — no code divergence.
- **+**: preserves ADR-012's "runs with no key" property and the fail-closed/grounded security invariants.
- **−**: real providers are not exercised in CI (no keys) — live validation is an explicit follow-up task.
- **−**: prompt/JSON parsing and masking must stay robust to arbitrary model output (fences, wrong categories) — covered by unit tests with fake providers.

---


*Next: [04 — Implementation Plan](04-implementation-plan.md)*