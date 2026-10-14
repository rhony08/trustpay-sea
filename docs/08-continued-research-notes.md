# 08 — Continued Research Notes (Batch 2, 2026-10-14)

Follow-up to 06/07. Each item: what was found, TrustPay mapping, source URLs.

---

## 1. Fact Check Tools API — design-ready (fills the `FACTCHECK_API_KEY` blank)

`claims.search` (GET, key auth): params `query`, `languageCode` (BCP-47, e.g. `id`,
`en-US`), `pageSize`, `maxAgeDays`, `offset`/`pageToken`, `reviewPublisherSiteFilter`.
Response: `claims[]` → `{text, claimant, claimDate, claimReview[]}` where each review has
`publisher{name,site}`, `url`, `title`, `reviewDate`, `textualRating`, `languageCode`.
Also `claims.imageSearch` (image as query — fits Phase 2 evidence flow) and a pages
CRUD for ClaimReview markup (not needed).

- https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search
- https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims
- https://developers.google.com/fact-check/tools/api

**TrustPay mapping (04 §3.5)**: query = merchant/recipient name + scam terms
(`penipuan`, `scam`, `investasi bodong`), `languageCode=id/en`, cache per entity,
invalidate on dispute change (same cache key as AI summary). **Limitation to record**:
fact-check coverage is news-claim-centric; mule accounts and QRIS merchants are rarely
fact-checked, so enrichment stays supplementary — consistent with ADR-012 "optional".
Empty-array-when-keyless behavior already specified; no change needed.

## 2. cekrekening.id deep-dive (R-4 step 1, mock-adapter spec material)

Komdigi portal (formerly Kominfo): **Periksa Rekening** (Bank / E-Wallet / crypto;
bank+number → report count + chronology, or "Belum Pernah Dilaporkan") and **Lapor
Rekening** (account data + owner name + bank + fraud category + chat/transfer screenshots;
all reports verified first; reporter PII required). Data pooled from public, police,
banks, e-commerce. Fronted by reCAPTCHA. **No public API** — confirms the 04 plan:
mock adapter first, real integration post-MVP behind MoU.

Two findings that shape TrustPay:
- Report form says **"Nomor Rekening (Bukan QRIS atau Virtual Account)"** — QRIS/VA are
  *excluded* from cekrekening.id reports. TrustPay's QR coverage fills a real hole the
  national portal leaves open. Say this in the demo narrative.
- Urgent path is separate: **Indonesia Anti-Scam Centre (IASC)** for fund-freeze speed;
  cekrekening.id is informational. Recovery wizard (4B.5) must route IASC/bank/police
  first, cekrekening.id second — matches the indonesiainorder.com case flow.

- https://cekrekening.id/home · https://cekrekening.id/lapor-rekening
- https://indonesiabaik.id/infografis/cara-cek-rekening-aman-penipuan-atau-tidak
- https://www.cnnindonesia.com/edukasi/20260904100447-561-1399886/cara-cek-rekening-penipu-online-cari-tahu-sebelum-kirim-uang
- https://indonesiainorder.com/cekrekening-id-cek-lapor-rekening-ewallet-penipuan
- https://kiaton.kontan.co.id/news/cek-rekening-penipu-di-cekrekeningid-begini-cara-verifikasi-dan-lapor-ke-kominfo-1

## 3. reCAPTCHA Enterprise assessment wiring (FastAPI-ready)

Backend-only `projects.assessments.create` (never from browser): send client token +
`expectedAction` (must match the action passed at `execute()` time) + optional
`hashedAccountId` (HMAC-SHA256, stable secret) for Account Defender. Response:
`tokenProperties.valid` (+`invalidReason`), `riskAnalysis.score` 0.0–1.0 (1.0 = legitimate)
with `reasons[]` ClassificationReasons, `accountDefenderAssessment.labels`
(`PROFILE_MATCH` etc.), plus carding/chargeback and password-leak verdicts. Then
**`assessments.annotate`** with LEGITIMATE/FRAUDULENT once the event outcome is known —
a built-in feedback loop that sharpens site-specific models (use for report/flag
outcomes; feeds NG-3 probe detection and 06 NG-10 triage).

- IAM: `roles/recaptchaenterprise.agent` on the runtime SA; first 10k assessments/mo free.
- Python: `google-cloud-recaptchaenterprise` client (`create_assessment`).
- https://cloud.google.com/recaptcha/docs/create-assessment-website
- https://cloud.google.com/recaptcha/docs/reference/rest/v1/projects.assessments/create
- https://cloud.google.com/recaptcha/docs/reference/rest/v1/projects.assessments

**TrustPay mapping**: gate `POST /reports`, `POST /flags`, signup with score-based keys
(`action=report_submit` etc.); score < threshold → challenge or manual-review lane, and
*annotate* on admin uphold/dismiss. Fits existing `deps.py` middleware pattern.

## 4. App Check custom-backend verification (FastAPI-ready, answers NG-3 in part)

Web client: `getToken(appCheck)` → send as **`X-Firebase-AppCheck` header** (never query
params). FastAPI: `firebase_admin.app_check.verify_token(token)` → 401 on failure; use
`consume=True` + `getLimitedUseToken()` on the client for **replay protection (beta)** on
high-value endpoints (report submit, screen API). Attestation provider for web =
reCAPTCHA Enterprise (same key family as §3 — one integration, two uses). Requires the
"Firebase App Check Token Verifier" role if verifying outside default creds.

- https://firebase.google.com/docs/app-check/custom-resource-backend
- https://firebase.google.com/docs/app-check/web/custom-resource
- https://firebase.google.com/docs/reference/admin/python/firebase_admin.app_check
- https://github.com/firebase/firebase-admin-python/blob/master/firebase_admin/app_check.py

**TrustPay mapping**: session tokens for normal lookups; limited-use tokens for
report/flag/screen calls. Combined with per-key quotas this is the concrete NG-3
(screen-oracle) mitigation — spec it in the 06 NG-9 key-design task.

## 5. Gemini Batch API — halve the forensics/eval bill (non-realtime only)

`batchGenerateContent`: async, **50% of standard cost**, 24h target (usually much faster),
higher rate limits. Two submit modes: **inline** (<20 MB total) or **JSONL file** via File
API (≤2 GB), user-defined keys map responses. Supports `response_mime_type:
application/json` + `response_schema` — the same structured-output contract as realtime,
so one schema serves both paths.

- https://ai.google.dev/gemini-api/docs/batch-api
- https://ai.google.dev/gemini-api/docs/batch-api.md
- https://ai.google.dev/gemini-api/docs/structured-output
- https://developers.googleblog.com/en/scale-your-ai-workloads-batch-mode-gemini-api/

**TrustPay mapping**: realtime path stays sync (report publish, entity summary on
invalidation); move to batch: nightly summary backfills, prompt-injection **eval suites**
(blocking CI gate per 02 §9.6 can run cheaper), Scam Playbook page generation (3B.10),
duplicate-report clustering experiments. No code change to prompts — only transport.

## 6. Single-VM MIG autohealer (extends 07 — $0 extra stability)

HTTP health check → `:8000/healthz` + `gcloud compute instance-groups managed create
--size 1 --health-check … --initial-delay 300`: crashed/hung app gets the VM recreated
automatically (~10 min monitoring warmup; keep checks conservative or busy demo moments
trigger rebuilds). Caveats found:
- **Recreate deletes the boot disk unless stateful** — with Postgres data on the boot PD,
  either declare a stateful disk or accept snapshot-based restore. For the hackathon:
  stateful-disk config + daily snapshot schedule (07 §3) together.
- Standalone VMs already get `automaticRestart` (host-failure reboots) for free — MIG
  adds *app-level* healing on top.
- Health-state-change logs bill past the free Logging allotment — disable them for demo.

- https://docs.cloud.google.com/compute/docs/instance-groups/autohealing-instances-in-migs
- https://docs.cloud.google.com/compute/docs/tutorials/high-availability-autohealing

## 6b. Stateful-MIG + snapshots: copy-paste completion of §6 (researched)

Best-practice correction to §6: keep Postgres data on a **separate 10 GB `pd-standard`
data disk** (`pgdata`, ≈ $0.52/mo) with a **stateless boot disk** — this also survives
boot-filesystem corruption, per Google's own guidance. Then:

```bash
# data disk + attach
gcloud compute disks create trustpay-pgdata --size=10GB --type=pd-standard \
  --zone=asia-southeast2-a
# mount at /var/lib/postgresql/data via fstab or compose volume mapping,
# with device-name=pgdata in the instance template

# stateful policy: disk survives autoheal/recreate/update; never auto-deleted
gcloud compute instance-groups managed update trustpay-mig \
  --stateful-disk device-name=pgdata,auto-delete=never --zone=asia-southeast2-a

# daily snapshots, 7-day retention
gcloud compute resource-policies create snapshot-schedule trustpay-daily \
  --max-retention-days=7 --on-source-disk-delete=apply-retention-policy \
  --daily-schedule --start-time=02:00 --region=asia-southeast2
gcloud compute disks add-resource-policies trustpay-pgdata \
  --resource-policies=trustpay-daily --zone=asia-southeast2-a
```

Docs: stateful-disk config (preserved on autohealing/update/recreate regardless of
delete rule; `auto-delete=never` also protects on permanent deletion):
- https://cloud.google.com/compute/docs/instance-groups/configuring-stateful-disks-in-migs
- https://cloud.google.com/compute/docs/instance-groups/how-stateful-migs-work
- https://cloud.google.com/compute/docs/instance-groups/preserved-state
- https://docs.cloud.google.com/compute/docs/instance-groups/create-mig-with-basic-stateful-disks
Snapshot schedules:
- https://docs.cloud.google.com/compute/docs/disks/scheduled-snapshots
- https://docs.cloud.google.com/compute/docs/disks/manage-snapshot-schedules

## 7. Gov comparables for R-4 (MY + SG models to cite/imitate)

- **MY SemakMule** (`semakmule.rmp.gov.my`): PDRM report-linked account/phone check +
  in-portal reporting; official line: *"No Record Found ≠ clean"* — adopt the same
  disclaimer wording for TrustPay unverified entities. Hotline: **NSRC 997 (24/7)**.
  Mule penalties: Penal Code §424B, RM10k–100k / 1–7 yrs. Private wrapper **PenipuMY**
  proves the adapter pattern: SemakMule API + search counts + Truecaller + URL analyzer
  in one result card — the closest existing product to TrustPay's vision.
- **SG ScamShield** (OGP-built): app + website + **1799 helpline (24/7)** + AI classifier
  for number/message/link + OS-level block/filter + authority-reviewed reports; 120k+
  entities blocklisted, 900k+ downloads. Model for TrustPay's check→report→block loop
  and for the 4B.4 hotline directory (ID ? / MY 997 / SG 1799).

- http://semakscam.com/en · https://penipu.my/features
- https://www.scamshield.gov.sg/ · https://www.scamshield.gov.sg/check-for-scams/how-to-check-for-scams-on-scamshield-app
- https://www.tech.gov.sg/products-and-services/for-citizens/scam-prevention/scamshield
- https://www.rhbgroup.com/-/media/Files/others/highlights/announcements/H20260902-3.pdf (NSRC 997 + SemakMule guidance)

---

## Next queued threads (not yet researched)

### 9. Kredibel.co.id teardown — closest private competitor (researched, answers queue #4)

Scale signals (self-reported): **72,343+ cases, 52,071+ blacklisted phones, Rp108.5M+
reported losses tracked since Jan 2018**, "4M+ users saved" claim. Model notes for TrustPay:
- **Login-to-view details**: account pages show verdict publicly ("Pernah dilaporkan" +
  rating 2.2/10 reviews) but gate name/bank/score/stats behind login — a live production
  example of NG-3 oracle mitigation + anti-scraping. TrustPay's ADR-016 exact-match reveal
  is stricter; consider matching Kredibel's "public verdict, gated details" as the
  middle tier for unauthenticated screen calls.
- **Human review before blacklist**: every report reviewed (chronology + chat/transfer
  screenshots) before blacklisting — validates 04 Phase 4/6 human-in-the-loop, and sets
  the SLO bar NG-10 asks about.
- **SEO moat**: per-bank pages (Mandiri/BRI/BNI/BCA/CIMB/Jenius/BTN/Danamon/Permata…),
  per-telco phone pages, merchant review profiles + discussion threads — the template for
  3B.10 Scam Playbook library. Note bank-code data (e.g., BTN 200, BNI 009, BTPN 213) is
  published openly per bank — useful input to G-8 (directory licensing: codes themselves
  are facts; branding/copy needs care).
- **B2B ladder**: "Kredibel For Enterprise" (Fraud Detection System, AML, KYC) — the exact
  monetization path TrustPay's Open Public API → B2B is meant to follow. Cite in pitch.
- **Legal shield text** (template for G-12 Terms): *"Kredibel merupakan forum publik yang
  menyajikan rekam jejak … berdasarkan laporan maupun ulasan pengguna, dan karena itu
  pandangan yang diungkapkan tidak mencerminkan pendapat Kredibel."*
- **M-banking name check** (OCBC article): banks already leak holder names pre-transfer
  via "Cek Rekening Tujuan" — precedent that exact-match name disclosure (ADR-016) mirrors
  existing banking UX, not a new exposure.

- https://www.kredibel.com/search/phone · https://www.kredibel.com/report
- https://www.kredibel.com/account/159753258000 (gated-detail pattern)
- https://www.kredibel.com/cek-rekening/btn (bank SEO page pattern)
- https://www.ocbc.id/id/article/2024/02/26/cek-identitas-lewat-no-rekening-bank

## Next queued threads (still open)

### 10. OJK sandbox/recordation path (researched, answers queue #3 — counsel-brief ready)

- **Current regime**: POJK 3/2024 on FSTI replaces POJK 13/2018. The old *recordation*
  step is gone — applicants apply **directly as sandbox participants** (form + test plan +
  supporting docs) under SEOJK 5/2024 mechanism. Test max **1 year**; pass → business
  license within **6 months**; fail → cease activities + execute exit policy. 108 legacy
  providers across 15 clusters were already processed (Apr 2024).
- **Shortcut that matters for TrustPay**: POJK 29/2024 (Innovative Credit Scoring) and
  POJK 4/2025 (Aggregation/FSAO) created **direct licensing tracks** — ICS/FSAO
  applications no longer go through FSTI registration. If counsel classes TrustPay's
  risk score as ICS-like and its lookup as aggregation-like, the path may be
  direct-license rather than sandbox. That is the exact question for the brief.
- **Governance load if licensed**: POJK 30/2025 (effective 1 Jul 2026) — min 2 directors,
  commissioner roles, annual GCG report + semiannual risk profile, six risk families
  (strategic/operational/cyber/legal/compliance/reputation).
- https://www.ojk.go.id/en/fungsi-utama/itsk/regulatory-sandbox/default.aspx
- https://ojk.go.id/en/fungsi-utama/itsk/perizinan-itsk-aset-keuangan-digital-aset-kripto/default.aspx
- https://www.makarim.com/storage/uploads/e7962abd-48e2-4b2a-8aa1-cb30f04423e8/Issue-6-April-2024---Refining-Digital-Financial-Innovation-New-OJK-Regulation-aims-to-enhance-Regulatory-Sandbox.pdf

1. ~~Snapshot schedules + stateful-disk MIG config~~ — ✅ §6b.
2. ~~`google_billing_budget` module~~ — ✅ IMPLEMENTED (`gcp/terraform/budget.tf`).
3. ~~OJK FSTI recordation/sandbox path~~ — ✅ §10 above.
4. ~~Kredibel.co.id private-DB model~~ — ✅ §9 above.
5. ~~Gemini File API lifecycle/costs for evidence images~~ — ✅ §11 below.

### 12. IASC operating picture (researched — recovery-wizard spine for 4B.5)

OJK Satgas PASTI's Indonesia Anti-Scam Centre (`iasc.ojk.go.id`), live since 22 Nov 2024:
**702,342 reports by 30 Sep 2026** (334k via banks/PSPs, 367k direct), **1.37M reported
accounts, ~703k blocked, Rp811B blocked, Rp207B returned** across 24 banks. Model:
victim files ticket → reporter's bank validates → auto-forward to scammer's bank →
**transaction delay (block)**; OJK supervises; colocated + non-colocated bank staff.
Dual-track doctrine victims must hear: **IASC = financial freeze lane, police LP = legal
lane, both required, speed decides recovery** ("TIDAK menjamin dana kembali").

- https://iasc.ojk.go.id/ (flow: kelengkapan → kirim → nomor tiket → lacak)
- https://ojk.go.id/id/berita-dan-kegiatan/siaran-pers/Pages/IASC-Berhasil-Kembalikan-Rp161-Miliar-Dana-Masyarakat-Korban-Scam.aspx
- https://keuangan.kontan.co.id/news/iasc-terima-702342-laporan-kasus-penipuan-hingga-september-2026
- https://keuangan.kontan.co.id/news/satgas-pasti-iasc-terima-515345-laporan-kasus-penipuan-masyarakat-per-31-maret-2026

**TrustPay mapping**: 4B.5 recovery wizard = IASC ticket first (with evidence checklist:
transfer proof, both account records, chat logs, URLs/usernames, don't delete anything),
police LP second, cekrekening.id third (informational). Channels: Kontak OJK **157**,
WA **081-157-157-157**, `konsumen@ojk.go.id`, `sipasti.ojk.go.id` for illegal
investment/pinjol. Also note the **fake-IASC impersonation scam** warning — TrustPay's
own brand will be impersonated the same way; warning-card + verified-domain education
belongs in 4B.6.

### 13. Context caching — app-level summary cache stays, Gemini caching doesn't apply

- **Implicit** (default, 2.5+): 90% off cache hits on Vertex, no storage cost — but
  **minimum 1,024–4,096 input tokens** (Flash 1024–4096 by version, Pro 4096) and no
  hit guarantee; prefix-stable prompts hit best.
- **Explicit** (beta, generateContent only): guaranteed 90% (2.5+) / 75% (2.0) on
  referenced tokens + storage $/TTL (default 1h, no max).
- **Design consequence for 04 §3.4**: per-entity summary prompts are a few hundred
  tokens — far under every minimum — so Gemini-side caching yields **nothing** here.
  The specified app-level cache (Redis/DB row per entity, invalidate on report/dispute
  change) is the correct and only effective layer. Revisit explicit caching only if
  prompts grow (e.g., batched multi-entity adjudication dossiers >4k tokens).
- https://ai.google.dev/gemini-api/docs/caching
- https://cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview

### 11. Gemini File API lifecycle (researched — design consequence for forensics worker)

- Storage **free**, caps: **20 GB/project**, **2 GB/file**; files **auto-delete after 48h**
  (manual `files.delete` available); user-uploaded files can't be re-downloaded, only
  referenced by URI; images billed as input tokens (≈ 560 tokens/image at Flash rates —
  fractions of a cent).
- **Critical**: Files API is **Gemini Developer API only — not supported on Vertex AI**.
  TrustPay prod (Vertex, per prior notes) must therefore inline small evidence images
  (base64 `inlineData`) or reference **GCS URIs**; File API URIs fit only the AI-Studio-key
  dev path and §5 batch jobs submitted via Developer API.
- Worker rule: evidence ≤ a few MB → inline base64 (no lifecycle to manage); batch
  forensics via Developer API may use File API URIs but must tolerate 48h expiry
  (re-upload per job) — matches the 90-day GCS evidence lifecycle staying authoritative.
- https://ai.google.dev/gemini-api/docs/files
- https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/File_API.ipynb

### 14. SP4N-LAPOR! — the escalation lane (completes the gov-reporting map)

National complaint router run by KemenPAN-RB + Kemendagri + Komdigi + KSP + Ombudsman
(Perpres 76/2013, PermenPANRB 62/2018, mandatory app via KepmenPANRB 680/2020):
**679+ agencies connected**, "no wrong door policy", police/criminal matters routed via
v3.5 track, 2 MB attachments, anonymous/secret report options, ~4-day first-response
expectation. Judi-online complaints among the top topics.

- https://www.lapor.go.id/ · https://kolakatimurkab.lapor.go.id/
- https://web.bnpb.go.id/ppid//theme/file/Laporan_Tahunan_SP4N_LAPOR_2024_.pdf (2024 annual report)

**TrustPay mapping**: recovery-wizard lane order is now complete — IASC (freeze) →
police LP (legal) → cekrekening.id (intel) → **LAPOR! (escalation/grievance, e.g.
bank slow to act on IASC ticket)**. LAPOR! is not a freeze path; position it as such.

### 15. PenipuMY API — the reference design for TrustPay's own public API (feeds 09)

Live v1 (`penipu.my/api/v1/docs`), `X-API-Key` header auth, key from account settings:
- Tiers: **Free 100 req/day → Starter RM29/mo 1k/day → Business RM199/mo 10k/day →
  Enterprise RM999/mo unlimited → bonus +500 RM15 one-time**; reset midnight MYT;
  `X-RateLimit-Limit/Remaining` headers. Copy this ladder for 7.4 pricing narrative.
- Endpoints mirror TrustPay's planned surface: `GET /search?q=&type=`,
  `/phone`, `/bank`, profile details, `/stats`. Response carries **freshness labels**:
  `police_report_status: live | cached (≤24h) | cached_stale | unavailable` —
  adopt the same enum for gov-adapter fields (graceful degradation is designed in).
- **Privacy-safe by construction**: no PII in API responses (counts + flags only) —
  precedent for TrustPay's masked screen responses.
- Engagement: "Most Wanted" loss leaderboard (#1 RM281k) ≈ Trust Rank Ladder energy.

- https://penipu.my/api/v1/docs · https://penipu.my/features · https://penipu.my/

### 16. Search grounding economics — dynamic retrieval + cache, never per lookup

- Gemini 3: **per executed search query** — 5k free/mo shared, then **$14/1k queries**;
  one prompt can trigger several billable queries. 2.5/older: per grounded prompt
  ($35/1k, 1.5k/day free). Daily cap 1M queries/day.
- **Dynamic retrieval threshold** (default 0.7): model scores whether grounding helps;
  below threshold no search runs (and on Gemini billing, ungrounded responses aren't
  search-billed). Search tools **can't combine with function calling** in one request.
  Citations arrive as `url_citation` annotations — render them, don't paraphrase away.
- **Design consequence for 04 §3.4**: ground only at summary (re)computation time
  (report/dispute/gov change invalidates), serve lookups from the app-level cache.
  Grounded-summary cost ≈ tokens + ~1–3 queries each — trivial at demo scale, and the
  5k/mo free tier covers ~1.5k+ entity summaries.
- https://ai.google.dev/gemini-api/docs/generate-content/google-search.md
- https://ai.google.dev/gemini-api/docs/grounding?lang=rest
- https://ai.google.dev/pricing?hl=en
