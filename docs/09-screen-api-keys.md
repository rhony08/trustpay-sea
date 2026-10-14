# 09 — Screen API Key Tiers & Anti-Probing

**Status**: ✅ **IMPLEMENTED (2026-10-14)** — `api_keys` table, `X-API-Key` auth,
per-tier daily quotas with `X-RateLimit-*` headers, distinct-entity probe detection,
issue/list/usage/rotate/revoke endpoints, audit-logged. Visitor tier stays keyless
(bucketed counts). **Deferred**: App Check / reCAPTCHA challenge handoff, partner
webhooks, freshness labels (`live/cached/unavailable`), 24h rotation grace.

Closes 06 **NG-3** (screen oracle) and **NG-9** (missing key design for 04 §7.4).
Tier shape modeled on PenipuMY's live ladder (08 §15):
Free 100/day → paid 1k/10k/day → Enterprise unlimited.

## 1. Tiers

| Tier | Auth | Quota | Response detail | Purpose |
|---|---|---|---|---|
| Visitor (no key) | IP + App Check session token | 20 lookups/day/IP | Band + masked profile only; counts bucketed (`<10`, `10+`) | Casual pre-pay checks; scammer-QA resistant |
| Demo key | `X-API-Key`, self-serve | 100/day (PenipuMY parity) | Full masked profile + `search_intelligence` (threshold-gated per 04 §3.3) | Hackathon integrators, bots |
| Partner | key + scope | 1k/day default, 10k on request | Above + freshness labels (`live/cached/cached_stale/unavailable`, 08 §15 pattern) + webhook on band change | Banks, e-wallets, communities |
| Enterprise | key + IP allowlist + contract | Unlimited + SLA | Above + bulk screen endpoint + analyst support | B2B revenue |

Rate-limit headers on every response: `X-RateLimit-Limit/Remaining` (PenipuMY parity).
Reset midnight Asia/Jakarta (WIB, UTC+7).

## 2. Key mechanics (implements 04 §7.4)

- Format `tpk_live_<32B urlsafe>`; store **SHA-256 hash + last-4 + scopes + tier**;
  raw key shown once at issuance. Rotation = new key, 24h grace on old; revocation
  immediate; all events in hash-chained `audit_logs`.
- Scopes: `screen:read` (all tiers) · `reports:write` (partner+, for community
  integrations filing on behalf of users) · `admin:read` (never on screen keys).
- Endpoints: `POST /api/v1/keys` (issue, auth'd user) · `GET /api/v1/keys/usage` ·
  `POST /api/v1/keys/{id}/rotate` · `DELETE /api/v1/keys/{id}`.

## 3. Probe-pattern detection (the NG-3 mitigation)

Computed per key (+ per IP for visitor tier), evaluated async via the identity graph
(ADR-014); violations throttle → challenge → revoke, never silent:

| Signal | Threshold (tunable) | Action |
|---|---|---|
| Distinct entities screened / hour | >50 (visitor) / >500 (demo) | reCAPTCHA challenge on screen calls |
| Screen calls with zero follow-up reports over 7d + high distinct count | classifier input | Require App Check **limited-use** tokens (`consume=True`, 08 §4) |
| Off-hours burst / datacenter ASN / rotating UA | heuristic | Step down one tier for 24h |
| Confirmed scammer-QA (key screens entity hours before its first cash-out report) | analyst verdict | Revoke + `identity_trust` penalty on owner (feeds 06 NG-10 triage) |

reCAPTCHA `annotate()` (08 §3) closes the loop: upheld/dismissed outcomes on
reports refine both the site model and probe heuristics.

## 4. Privacy posture

No PII in screen responses at any tier (counts + band + masked profile only —
PenipuMY parity, 08 §15). Exact-match holder-name reveal (ADR-016) is a **UI**
privilege for authenticated first-party users, never exposed via API keys in MVP.

## Owner questions

1. Visitor tier: allow unauthenticated screening at all for the demo? (Recommend yes —
   it's the core "check before you pay" moment; quotas contain abuse.)
2. Confirm tier numbers/pricing narrative (Free 100 → paid), or docs-only for hackathon
   (keys issued, billing post-MVP)?
3. Threshold starting values above acceptable? (Recommend yes as tunable defaults.)
