# 10 — Data Fate Matrix: Retention vs Legal Hold vs Erasure vs Dispute Freeze (PROPOSED)

Reconciles 06 **NG-6/NG-11** (and sharpens G-13) into one per-table spec for the Phase 7.8
DSAR/retention build. Default: **N = 90 days** post-verification for original evidence
(matches the GCS bucket lifecycle in `gcp/terraform/main.tf` and the GCE `pgdata`
snapshot window).

Legend: KEEP · PURGE (hard delete) · TOMBSTONE (row stays, PII nulled, `deleted_at` set,
excluded from all reads except audit) · FROZEN (no state change except dispute/admin)

## 1. Matrix

| Table | DSAR delete (own data) | Retention expiry (N days) | `is_legal_hold` | Dispute freeze (`is_under_dispute`) |
|---|---|---|---|---|
| `users` (+credentials) | TOMBSTONE auth row; PURGE PII columns; keep `id` for FK integrity | n/a (account lifetime) | FROZEN (no delete) | FROZEN |
| `fraud_reports` (body) | TOMBSTONE: description→null, amount→null, keep category + timestamps for counters | TOMBSTONE body at N days | FROZEN | FROZEN |
| `report_evidences` (originals, quarantine) | PURGE object + row | PURGE object at N days | FROZEN (hold exempts objects AND rows — 06 NG-19) | FROZEN |
| `report_evidences` (redacted public copies) | Keep (anonymized, no PII by construction) | Keep | FROZEN | FROZEN |
| `payment_entities` (HMAC row) | **Never delete**: others' safety depends on lookup. TOMBSTONE display fields only | Never (aggregate counters are anonymized) | FROZEN | Rise-only cap per 04 §5.5 (≤45 unverified-rise, never lowers verified score) |
| `owner_disputes` + counter-evidence | Requester copy TOMBSTONED; decision record kept (audit) | Keep decisions, PURGE counter-evidence files at N days | FROZEN | n/a (the freeze source) |
| `report_votes`, `review_flags` | PURGE user's rows | Keep (anonymized weights) | FROZEN | Votes on frozen reports stop moving the score |
| `audit_logs` (hash-chained) | **Never delete or edit** (chain integrity); DSAR answered with export, not deletion — state this in Terms (G-12) | Never | Never | Never |
| `user_notifications` | PURGE on request | PURGE at 30 days | FROZEN | Keep dispute-related until resolution +7d |

## 2. Rules

1. Precedence: **legal hold > dispute freeze > DSAR/retention**. A hold blocks deletes;
   expiry while frozen re-queues the purge for unfreeze +7d.
2. Tombstoned rows stay countable for scoring (category/timestamp only) — erasure must
   not silently deflate a verified entity's score (06 NG-11).
3. Every purge/tombstone writes an `audit_logs` entry (actor, scope, row id, reason);
   the log entry itself is never purged (rule: chain integrity > erasure; Terms say so).
4. Retention job runs daily via scheduler (existing APScheduler hook, Phase 0.5);
   dry-run mode logs candidates without deleting (demo-safe default).

## Owner questions

1. Confirm N = 90 days for original evidence (recommend yes).
2. Confirm `audit_logs` never-deleted doctrine for Terms (recommend yes — alternative is
   redacted-summary chaining, heavier build).
3. Confirm tombstone-not-delete for entity HMAC rows (recommend yes — deletion would
   un-protect future victims).
