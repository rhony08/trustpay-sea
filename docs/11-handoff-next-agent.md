# 06 — Handoff: Next Agent Status, Gaps & Notes

**Snapshot**: `main` @ `87360eb` (2026-10-14). Phases 0–7 **core** implemented and merged. This document is the continuation guide: what's done, what's deliberately mocked/deferred, gaps found during implementation, and the recommended next work. Read alongside `05-gap-analysis.md` (open product decisions) and `04-implementation-plan.md` (per-phase acceptance criteria + status lines).

---

## 1. Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Scaffold (schema, auth, rate limit, CI) | ✅ done |
| 1 | Resolver / bank directory | ✅ done (393-institution SEA reference, seeded) |
| 2 | Reports, evidence & AI forensics | ✅ done (mock-first AI) |
| 3 | Search intel, AI summary, fact-check | ✅ done |
| 3B | Web-first community & engagement | ✅ done (3B.1–3B.10) |
| 4 | Community moderation (votes, flags) | ✅ done |
| 4B | Security-awareness features | ✅ done (4B.1–4B.7) |
| 5 | Owner claim, dispute, safe-harbor | ✅ done |
| 6 | Risk engine, anti-brigading, admin portal | ✅ done (backend + minimal UI) |
| 7 | Hardening, tests, launch | 🟡 core done; 7.4 keys / 7.5 security review / 7.6 demo script deferred |

**Tests**: 135 passing, ~81% coverage (`--cov-fail-under=70` in CI). **Web**: typecheck/lint/build green; Playwright smoke (3 specs) green.

---

## 2. What Is Real vs Mocked (read before trusting a demo)

**Real**: bank directory + seeder, HMAC account hashing/normalization, EMVCo parser + CRC, QR image decode, report lifecycle + quotas + idempotency, evidence upload guards (magic bytes, pixel cap, EXIF-strip re-encode), pHash duplicate detection, grounded AI **summary** (fact template + grounding check), search stats + rollup, votes/flags/admin resolution, hash-chained audit, badge/trust/watchlist/quiz/playbook/receipts, claim/dispute/safe-harbor, explainable scorer + factor breakdown, anti-brigading dampen, mock gov override, four-eyes approvals, **Malaysia gov checker (PDRM Semak Mule — bank + telefon)**.

**Mocked / stubbed** (swap before production):
- **AI inference**: `AI_PROVIDER=mock` is the default. `gcp` (Vertex AI) and `openrouter` providers are implemented but have **never been exercised against live models** (no keys in this repo). OCR, tamper detection and PII-redaction *detection* are mock; the real providers request JSON (PII boxes / slip fields / tamper signals) and redaction is drawn locally.
- **Evidence storage**: local-disk shim (`app/storage.py`). S3/R2 presigned uploads, ClamAV AV scan, and the separate cookieless media domain are **not** implemented (Phase 7 target).
- **Notifications**: in-app `user_notifications` always written; **email-first delivery implemented** (G-15, pluggable `NotificationChannel` — console default, SMTP env-gated) on watcher/flag/dispute events. Recipient-preference UI is minimal.
- **Gov registry**: **Malaysia (PDRM Semak Mule) is real** — bank + telefon checkers (`app/services/semakmule.py`), surfaced on MY lookups and persisted at report time; enabled only when `SEMAKMULE_API_KEY` is set (env-only secret). All other countries use the in-memory mock feed (`gov_adapter`). Real cekrekening.id / SG / TH / VN / PH connectors remain post-MVP.
- **Account ownership proof**: mock verification (NMID tier is deterministic; document tiers auto-accept). Micro-deposit OTP is real but delivered in-band (dev).

---

## 3. Not Done / Deferred (by area)

1. **Live AI validation** — enable `AI_PROVIDER=gcp` (Vertex + ADC) or `openrouter`, add keys, run the report pipeline against real slips, validate JSON parsing/grounding/fail-closed.
2. **Storage hardening** — R2/S3 presigned POST, quarantine encryption (AES-GCM), ClamAV, cookieless public media domain (retention purge job ✅ done — `docs/10`).
3. ~~**Auth hardening**~~ — ✅ **DONE 2026-10-15 (ADR-020)**: HttpOnly `tp_access`/`tp_refresh` cookies + double-submit CSRF (`X-CSRF-Token`, enforced only for cookie-authenticated mutations), WebAuthn passkeys (`webauthn_credentials`, `py_webauthn`) with MFA login step for ANALYST+, `mfa_at` step-up guard on approval endpoints, `MFA_REQUIRED_FOR_ADMINS` prod gate (no passkey → no admin login). Bearer mode still supported for non-browser clients.
4. **Admin portal UI** — backend endpoints exist (`/admin/dashboard`, `/admin/audit`, `/admin/approvals`, `/admin/flags`, `/admin/disputes`), but the `/admin` page is a read-only dashboard. No queue action UI, no side-by-side evidence review, no approvals UI.
5. **Partner/Open API** — **screen API keys implemented** (`docs/09`): `api_keys` table, `X-API-Key` auth, tiers (visitor keyless / demo / partner / enterprise), per-tier daily quotas + `X-RateLimit-*`, distinct-entity probe detection, issue/rotate/revoke/usage endpoints, audit-logged; public `/api/v1/screen/account|qr` are privacy-safe (no holder names). **Still deferred**: App Check/reCAPTCHA handoff, partner webhooks, freshness labels, key-scoped `reports:write` ingestion endpoint.
6. ~~**Dual-control coverage**~~ — ✅ **DONE 2026-10-15 (ADR-021)**: four-eyes extended to `hide_report` (flag UPHELD), `remove_report` (dispute APPROVED_REMOVED) and `settlement`; approvals expire after 72h; requester-only cancel endpoint; flag/dispute resolve endpoints now *request* approval instead of executing. `gov_override`/`ban_user` unchanged. Still single-step by design: flag DISMISSED (non-destructive).
7. **Legal/consent** — report consent checkbox exists; **ToS/Privacy pages are not drafted** (G-12). DSAR export/erase implemented as *hard delete* (G-13 semantics: docs mention tombstone + search removal — not fully implemented).
8. **i18n** — `en` + `id` catalog exists, but most Phase 3B–6 UI surfaces are English-only.
9. **E2E** — Playwright smoke (static routes) + backend journey test only; no full browser flow (report→publish→flag→claim) through a running API.
10. **Coverage** — overall 81%, but low on `moderation_service` (~41%), `dsar` (~42%), `dispute_service` (~62%), `watchlist_service` (~60%). Uplift these.

---

## 4. Gaps & Deviations Found

- **ADR-012 superseded in practice**: mock-first is now a *pluggable provider* (`mock|gcp|openrouter`) — recorded as **ADR-019**. GCP hosting (GCE-first + portable compose) is **ADR-018**.
- **Scorer is not the ADR-003 Bayesian model**: it's a transparent weighted sum with the documented factors. Exact weights are approximate; the public "rounded factor labels" rule (§5.3) is not enforced (raw weights are returned).
- **Anti-brigading is simplified**: uses distinct reporter identities + `identity_trust` + a 7-day z-score. The full device/IP/phone identity graph and hashed fingerprint store (ADR-014) are not built.
- **`media_url` sentinel**: evidence rows use `media_url = ""` until fail-closed redaction produces the public copy (`NOT NULL` preserved). Public serializers only expose evidence when a report is `PUBLISHED`.
- **Rate limiting** is a single anonymous/IP token bucket. No per-user/per-API-key buckets, no lookup-oracle detection.
- **`next start` warning**: `next.config.mjs` sets `output: "standalone"` but CI/E2E run `next start` (works, warns). Either use `node .next/standalone/server.js` or drop `standalone`.
- **Frontend static mirror**: `apps/web/lib/api.ts` still hard-codes a small `BANKS` list for `/check` (the report page uses `/api/v1/banks`). Migrate `/check` to the API endpoint.
- **Bugs fixed this session** (context, don't reintroduce): `_report_stats` multi-column `scalar()` unpack; Indonesian bank-code collision (`213`=Bank SMBC/ex-BTPN, **BCA Syariah = 536**); Vietcombank BIC corrected to `BFTVVNVX`.
- **Migrations**: four revisions, not squashed. `d60dfef6a8d1` adds `NOT NULL` columns with server defaults (safe for existing rows).

---

## 5. Open Product Decisions (see `05-gap-analysis.md`)

Still open / confirm with owner: **G-6** (admin accounts for demo), **G-8** (bank-directory licensing — data is demo-grade), **G-11** (currency scope; assume IDR-primary), **G-12** (ToS/Privacy pages), **G-13** (erasure/tombstone semantics), **G-15** (notification provider), plus post-MVP **G-3/G-4/G-7**.

---

## 6. How to Run & Verify

```bash
cp .env.example .env
docker compose up -d postgres redis

cd services/api
python -m app.seeds.seed_banks    # 393-institution reference (idempotent)
python -m app.seeds.seed_demo     # demo users/entities/reports/dispute/gov entry
# demo login: analyst@trustpay.dev / demo-analyst-pass  (ANALYST)

pytest -q --cov=app --cov-fail-under=70
uvicorn app.main:app --reload     # http://localhost:8000/docs

cd ../../apps/web && npm install
npm run typecheck && npm run lint && npm run build
npx playwright install chromium && npm run test:e2e
```

**AI provider**: set `AI_PROVIDER=gcp` (+ `GCP_PROJECT`, `GCP_LOCATION`, ADC creds) **or** `AI_PROVIDER=openrouter` (+ `OPENROUTER_API_KEY`). Unset → `mock`. Redaction stays fail-closed regardless of provider (a provider error ⇒ report `FAILED`, never publishes unredacted evidence).

---

## 7. Recommended Next Work (ordered)

1. **Live AI validation** — run the pipeline against a real invoice/slip on Vertex; verify JSON schema, grounding, fail-closed (ADR-019 records the provider design).
2. **Storage hardening** — S3/R2 presigned uploads, AV scan, cookieless media domain, retention/legal-hold job. **Retention/legal-hold job now implemented (`docs/10`, Phase 10; dry-run by default).** Remaining: S3/R2 presigned uploads, AV scan, cookieless media domain.
3. ~~**Auth hardening**~~ — ✅ done 2026-10-15 (ADR-020): HttpOnly cookie sessions + CSRF; WebAuthn MFA mandatory for admins (`MFA_REQUIRED_FOR_ADMINS=true` in prod). Next possible step: Playwright virtual-authenticator e2e for the MFA flow + retire the `localStorage` token fallback in `lib/api.ts`.
4. **Admin portal UI** — flag/dispute queues, approve/resolve actions, approvals UI (ADR-021 queue + approve buttons exist), side-by-side evidence.
5. **Conversions/keys** — partner API keys + scopes + rotation; move `/check` off the static bank mirror.
6. **Coverage + E2E** — lift low-coverage services to ≥80%; add a full browser flow test with a running API.
7. **i18n + legal** — translate the new surfaces; draft ToS/Privacy (G-12) and settle G-13 erasure semantics.

---

## 8. Do-Not-Regress Invariants

- Accounts stored only as **KMS-keyed HMAC** (`hash_version`); public surfaces masked; holder-name disclosure exact-match-only (ADR-016).
- **Fail-closed redaction**: never publish unredacted evidence; redaction failure ⇒ `PROCESSING`/`FAILED`.
- **Rise-only dispute freeze**: `apply_dispute_cap` never lowers an existing/high score; gov listings stay 100.
- **Hash-chained append-only** `audit_logs`; every trust-altering admin action audited (four-eyes for destructive ops).
- All report/OCR/merchant text is **untrusted data**, never instructions; JSON-schema output + grounding check; summary templated server-side.
- One canonical **report-category taxonomy** shared by DB/NLP/API; the SEA bank reference is the single source of truth for the resolver + reporting UI.
- Moderate when in doubt: **ask the product owner before overriding any G-item or R-recommendation.**

---

*Predecessor handoff: `docs/README.md` → "Handoff Message". This document continues it after Phases 2–7 were implemented (2026-10-14).*
