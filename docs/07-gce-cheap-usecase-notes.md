# 07 — Cheapest Compute Engine Usecase Notes (GCE-mandatory hackathon)

**Constraint**: hackathon requires GCP **Compute Engine** (so the `gcp/` Cloud Run plan
is parked — see 06 NG-7). **Goal**: lowest possible bill with zero code changes.
**Verdict up front**: one `e2-small` on-demand VM in **Jakarta** running the existing
`docker-compose.yml` as-is ≈ **$21.65/mo**, fully covered by the $300 credit
(~13 months). Details + proof below.

---

## 1. Verified Jakarta price table (Oct 2026)

| Item | Price | Source |
|---|---|---|
| `e2-small` (2 shared vCPU, 2 GB) on-demand, Jakarta | **$16.44/mo** ($0.0225/hr) | https://gcloud-compute.com/asia-southeast2/e2-small.html |
| `e2-small` Spot, Jakarta | **$3.57/mo** ($0.0049/hr, −78%) | same |
| `e2-small` 1-yr CUD / 3-yr CUD | $10.36 / $7.40 | same |
| `e2-medium` (2 shared vCPU, 4 GB) on-demand, Jakarta | **$32.89/mo** | https://gcloud-compute.com/asia-southeast2/e2-medium.html |
| `e2-medium` Spot, Jakarta | **$7.15/mo** (−78%) | same |
| `e2-micro` Singapore (ref; Jakarta ≈ +10%) | $7.54/mo on-demand, $4.53 Spot | https://gcloud-compute.com/asia-southeast1/e2-micro.html |
| 30 GB `pd-standard` boot disk, Jakarta ($0.052/GB) | **$1.56/mo** | https://gcloud-compute.com/asia-southeast2.html |
| External IP in use (standard VM) $0.005/hr | **$3.65/mo** | https://cloud.google.com/vpc/network-pricing |
| External IP on Spot VM $0.0025/hr | **$1.83/mo** | same |
| Reserved-but-unused IP $0.01/hr | $7.30/mo — **never reserve idle** | same |
| Jakarta egress to internet | from **$0.08/GiB** (Premium) | https://cloud.google.com/vpc/pricing |

Discount rules that matter:
- E2 has **no sustained-use discounts** (baked into low on-demand instead); 1-yr CUD is a
  flat **−37%**; Spot can't combine with CUD/SUD/free tier.
  https://cloud.google.com/spot-vms/pricing ·
  https://developers.google.com/compute/vm-instance-pricing
- Spot discounts on shared-core E2 are ~40–78% (not the headline 91% — that's big machines);
  preemption = 30-sec best-effort notice, then STOP (disks survive, no VM-hour charge while
  TERMINATED). https://cloud.google.com/compute/docs/instances/spot

## 2. The free-tier trap (why not $0)

Always-Free `e2-micro` is **US-only** (`us-west1`/`us-central1`/`us-east1`), non-preemptible,
plus 30 GB std disk + 1 GB egress. Jakarta gets **$0 free**. A US free VM would break PDP
data residency (06 NG-5) and add ~150 ms latency to every QR lookup.
https://docs.cloud.google.com/free/docs/free-cloud-features?hl=en

## 3. Recommended usecase: "one fat-ish VM, compose as-is" (Option A)

Run the **entire** `docker-compose.yml` (postgres + redis + api + web) on a single
`e2-small` on-demand in `asia-southeast2-a`. Why it wins:

- **RAM math**: postgres:16-alpine ~100 MB + redis ~50 MB + FastAPI ~200 MB + Next
  standalone ~200 MB + Ubuntu ~300 MB ≈ 0.9–1.2 GB working set. `e2-micro` (1 GB) will
  swap/OOM under demo load; `e2-small` (2 GB) is the cheapest safe fit. `e2-medium`
  (4 GB) is the headroom pick at ~$38/mo total.
- **Kills the two big managed bills**: Cloud SQL `db-g1-small` Jakarta ≈ $33/mo and
  Memorystore 1 GB ≈ $35–50/mo become $0 (self-hosted in compose, data on the PD).
- **Zero code changes**: same images, same env names, same `alembic upgrade head` in the
  API entrypoint. GCE is just "a bigger docker host".
- **Bill**: 16.44 + 1.56 + 3.65 = **$21.65/mo** + pennies of egress. $300 credit ⇒ funded
  for the whole hackathon + ~1 year.

### Bring-up (copy-paste, ~10 min)

```bash
# 1. VM: Ubuntu LTS (simpler than COS — konlet is deprecated, use startup script)
gcloud compute instances create trustpay-sea \
  --zone=asia-southeast2-a --machine-type=e2-small \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --tags=http-server,https-server --metadata=startup-script='#! /bin/bash
    apt-get update && apt-get install -y docker.io docker-compose-plugin git
    systemctl enable --now docker
    # repo checkout + compose up happens in step 2 (or bake into image)'

# 2. firewall (Ubuntu images: allow 80/443/8000 as needed)
gcloud compute firewall-rules create trustpay-web \
  --allow=tcp:80,tcp:443 --target-tags=http-server,https-server

# 3. on the VM: clone, env, up (same flow as local dev)
git clone <repo> && cd trustpay-sea
cp .env.example .env   # contends: dev JWT self-gen is fine on throwaway VM
docker compose up -d --build
curl localhost:8000/healthz  # {"status":"ok","version":"0.1.0"}

# 4. static IP only AFTER it works (ephemeral first — unused reserved IPs cost MORE)
gcloud compute addresses create trustpay-ip --region=asia-southeast2
```

- Docs patterns used: startup-script/cloud-init for containers
  (https://docs.cloud.google.com/compute/docs/containers/deploying-containers — konlet
  deprecated, prefer startup script), compose-on-VM pattern, IP pricing above.
- Backups: scheduled snapshots of the 30 GB boot disk (snapshot storage ≈ $0.05/GB-mo;
  30 GB ≈ $1.50/mo) beat any managed-backup bill. `gcloud compute resource-policies create
  snapshot-schedule trustpay-daily --max-retention-days=7 --on-source-disk-delete=apply-retention-policy`.
- Safety: `google_billing_budget` alert at $25/$50 (fills 06 NG-8), stop VM when idle
  (`gcloud compute instances stop` — disks+IP keep billing ~$5/mo, VM hours $0).

## 4. Cheaper-but-risky variant (Option B): Spot e2-small ≈ $7/mo

Same setup with `--provisioning-model=SPOT --instance-termination-action=STOP`:
3.57 + 1.56 + 1.83 ≈ **$6.96/mo**. Catch: preemption mid-demo = downtime + cold Postgres
recovery. Mitigation (all scriptable): snapshot schedule + startup script that
`docker compose up -d` on every boot + keep a stopped on-demand twin? At that point the
twin costs more than just running on-demand. **Recommend**: Spot for overnight/dev,
on-demand for demo day and judging. One flag flip, same disk.

## 5. Rejected options (researched, don't use)

- **US free-tier e2-micro**: $0 but PDP residency breach + latency + 1 GB RAM too small.
  Only viable as a *second* throwaway (CI runner, docs host) — never for user data.
- **Splitting services across micro VMs**: 2× e2-micro Jakarta (~$17) + cross-zone traffic
  costs more than one e2-small and doubles ops. Monolith stays monolithic (ADR-008).
- **Managed SQL/Redis alongside GCE**: $70+/mo for what compose already does. Revisit only
  with real traffic (then: Cloud SQL + MIG, post-hackathon).
- **CUDs**: 1-yr lock-in for −37% makes no sense for a hackathon; Spot beats it with no lock-in.
- **COS + konlet**: deprecated path (see container docs above); Ubuntu LTS + compose plugin
  is the maintained equivalent.

## 6. Free Google stack to layer on top ($0 extra)

All verified in prior research rounds — stack these, they cost nothing at demo scale:
- **Gemini**: mock-first ($0); live fallback = Flash-Lite $0.10/$0.40 per 1M (Batch −50%).
- **Web Risk Lookup**: 100k checks/mo free — QR-payload URL intel.
- **reCAPTCHA Enterprise**: 10k assessments/mo free — report-spam defense.
- **App Check + Secret Manager** (6 versions free) + **Cloud Build** (120 min/day free quota
  class) for image builds even though runtime is GCE.
- **Cloud Storage**: evidence *metadata* stays on VM disk for demo; move to GCS only if
  the jury asks about scale (adds ~$0.02/GB).

## 7. Total-cost comparison (Jakarta, 1 month, demo scale)

| Setup | Compute | DB+cache | IP+disk | Total |
|---|---|---|---|---|
| **A: e2-small on-demand, compose** (recommended) | $16.44 | $0 | $5.21 | **≈ $21.65** |
| B: e2-small Spot, compose | $3.57 | $0 | $3.39 | **≈ $6.96** (preemptible) |
| A+: e2-medium on-demand, compose | $32.89 | $0 | $5.21 | **≈ $38.10** (headroom) |
| Cloud Run + Cloud SQL + Memorystore (parked plan) | ~$10 | ~$70–85 | ~$5 | **≈ $85–100** |

All of A/B/A+ fit inside the $300 new-customer credit
(https://cloud.google.com/free) with room for egress + snapshots.

---

## E2. (appendix) Next-note hooks

- If judges require *managed* DB after all: Cloud SQL free-trial instance (30-day,
  8 vCPU Enterprise Plus — oversized for demo, migrate back after).
  https://cloud.google.com/free
- MIG with size=1 + autohealer around the compose VM: ~$0 extra, converts crashes into
  auto-restarts. Worth it if demo-day stability is graded.
- T2D (AMD Milan) beats E2 on price/perf in some regions — not cheaper in Jakarta today
  (t2d-standard-1 ≈ $41.47/mo), recheck if sizing up.
