# TrustPay on one GCE VM (hackathon path)

Implements **docs/07 Option A**: a single `e2-small` in Jakarta running the stock
`docker-compose.yml` unchanged — ≈ **$21.65/mo**, inside the $300 credit.

## Deploy

```bash
# 0. secrets — OPTIONAL for dev, required for prod/keys. The startup script skips
# absent secrets so stock fallbacks win (compose DB/Redis URLs, dev JWT self-gen).
# Only run this if you need real JWT keys, Gemini, or FactCheck:
#   PREFIX=trustpay-dev PROJECT_ID=<proj> REGION=asia-southeast2 \
#     DB_PRIVATE_IP=unused REDIS_HOST=unused DB_PASS=unused \
#     ./gcp/scripts/bootstrap-secrets.sh
# (DB/REDIS shells stay unused on GCE — the VM runs its own postgres+redis.)

# 1. VM
PROJECT_ID=<proj> REPO_URL=https://github.com/<org>/trustpay-sea.git \
  ./gcp/gce/deploy.sh
# stretch: MODE=mig (size-1 MIG + autohealer + stateful pgdata, $0 extra)

# 2. open http://<ip>:3000 and http://<ip>:8000/docs
```

## How it works

- `startup.sh` (runs as root every boot): installs docker + compose plugin, mounts the
  `pgdata` disk at `/mnt/pgdata` (formats only if unformatted — safe on autoheal),
  points Docker's `data-root` at it so **images + volumes survive VM recreation**,
  clones/pulls the repo, builds `.env` + JWT PEMs from Secret Manager, brings up
  `docker-compose.yml` + a `docker-compose.gce.yml` override that mounts the PEMs at
  `/run/secrets/*`, then polls `/healthz` for 10 min.
- `deploy.sh`: least-privilege SA (logs + metrics + secret read), daily snapshot
  schedule (7-day retention), web firewall, then VM (own 10 GB data disk, static IP)
  or MIG (template + `:8000/healthz` autohealer with 300 s boot delay + stateful
  `pgdata` that survives autoheal — docs/08 §6/§6b).

## Day-2

- Redeploy: `git pull && docker compose -f docker-compose.yml -f docker-compose.gce.yml up -d --build` on the VM (or bump `GIT_REF` + recreate for MIG).
- Park it: `gcloud compute instances stop` — VM hours $0, disk+IP ≈ $5/mo.
- Kill it: delete VM + disks + address (`gcloud compute instances delete`,
  `disks delete`, `addresses delete`) — reserved-but-unused IPs bill $7.30/mo.
- Budget tripwire: `gcp/terraform/budget.tf` (NG-8 closed) — set `billing_account_id`.

## Don't

- Don't put secrets in instance metadata (it's visible to anyone with compute read).
- Don't expose 5432/6379 — firewall opens 80/443/3000/8000 only.
- Don't run Spot for judging (preemption); Spot is fine for dev nights (docs/07 §4).
