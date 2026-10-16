# 13 — GCP Deployment & Run Plan

**Goal**: run the full TrustPay SEA stack on Google Cloud Platform. The hackathon
requires **Compute Engine (GCE)**, so the recommended path is a single VM running a
self-contained Docker Compose stack. Cost math lives in [`07-gce-cheap-usecase-notes.md`](07-gce-cheap-usecase-notes.md)
(one `e2-small` in Jakarta ≈ **$21.65/mo**, covered by the $300 credit).

> **Important**: the root `docker-compose.yml` is written for the *current* shared
> host — it reuses external Postgres/Redis and joins the `be-remote-reporter_default`
> network. It will **not** boot on a fresh VM. Use the standalone bundle in
> [`deploy/gcp/`](../deploy/gcp/).

---

## 1. What runs where

| Component | Runtime | Notes |
|---|---|---|
| `web` (Next.js PWA) | container | built with `NEXT_PUBLIC_API_URL=$PUBLIC_URL` (same-origin) |
| `api` (FastAPI) | container | runs `alembic upgrade head` on boot; scheduler enabled |
| `postgres` | container | data on a persistent Docker volume (`pgdata`) |
| `redis` | container | rate-limit / cache / scheduler lock (`redisdata`) |
| `caddy` | container | reverse proxy + automatic TLS on 80/443 |
| AI (Vertex Gemini) | managed | `AI_PROVIDER=gcp`, via the VM service account (ADC) |
| evidence storage | VM volume | local-disk shim on `trustpay_evidence` (see §8) |

Single VM = monolith stays monolithic (ADR-008), no Cloud SQL/Memorystore bills.

---

## 2. Prerequisites

```bash
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
# Enable what we need
gcloud services enable compute.googleapis.com aiplatform.googleapis.com
```

---

## 3. Create the VM (Jakarta, ~$22/mo)

```bash
gcloud compute instances create trustpay-sea \
  --zone=asia-southeast2-a --machine-type=e2-small \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --tags=http-server,https-server \
  --metadata=startup-script='#! /bin/bash
    apt-get update && apt-get install -y docker.io docker-compose-plugin git
    systemctl enable --now docker
    usermod -aG docker $(getent passwd 1000 | cut -d: -f1) || true'

# Allow HTTP/HTTPS (Caddy)
gcloud compute firewall-rules create trustpay-web \
  --allow=tcp:80,tcp:443 --target-tags=http-server,https-server
```

> Demo-day stability: prefer on-demand (above). Spot (`--provisioning-model=SPOT
> --instance-termination-action=STOP`) cuts it to ~$7/mo but can be preempted mid-demo.

---

## 4. Deploy the stack

```bash
# On the VM
git clone <repo> && cd trustpay-sea
cp deploy/gcp/.env.gcp.example deploy/gcp/.env.gcp
$EDITOR deploy/gcp/.env.gcp        # set DOMAIN, PUBLIC_URL, POSTGRES_PASSWORD, AI_PROVIDER

COMPOSE="docker compose -f deploy/gcp/docker-compose.gcp.yml --env-file deploy/gcp/.env.gcp"

# 4a. Build images (web bakes PUBLIC_URL at build time)
$COMPOSE build

# 4b. Generate the RS256 JWT keypair ONCE into the secrets volume.
#     prod refuses to self-generate, so do this one-off with ENVIRONMENT=dev.
$COMPOSE run --rm -e ENVIRONMENT=dev --entrypoint sh api -c "python -m app.generate_dev_keys"

# 4c. Start everything (api runs migrations automatically)
$COMPOSE up -d

# 4d. Seed reference + demo data (idempotent)
$COMPOSE exec api python -m app.seeds.seed_banks
$COMPOSE exec api python -m app.seeds.seed_demo

# 4e. Verify
$COMPOSE ps
curl -fsS localhost/healthz         # {"status":"ok",...}
curl -fsS localhost/api/v1/hotlines?country=ID | head -c 200
```

Demo admin login: `analyst@trustpay.dev` / `demo-analyst-pass`.

---

## 5. Turn on real AI (Vertex AI)

The AI is fully wired (`app/ai/providers/`) and defaults to `mock` (no key). To enable
live Gemini on GCP:

1. Grant the **VM service account** the Vertex role:
   ```bash
   SA=$(gcloud compute instances describe trustpay-sea --zone=asia-southeast2-a \
        --format='value(serviceAccounts[0].email)')
   gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
     --member="serviceAccount:$SA" --role="roles/aiplatform.user"
   ```
   (GCE VMs already expose Application Default Credentials via the metadata server.)
2. In `deploy/gcp/.env.gcp` set:
   ```
   AI_PROVIDER=gcp
   GCP_PROJECT=<YOUR_PROJECT_ID>
   GCP_LOCATION=asia-southeast1
   ```
3. Recreate the API:
   ```bash
   $COMPOSE up -d api
   ```
   `app/ai/providers/__init__.py` falls back to `mock` if init fails, so a missing
   role/SDK never breaks a demo. Redaction failures stay **fail-closed** regardless.

Alternative: `AI_PROVIDER=openrouter` + `OPENROUTER_API_KEY=...` (no GCP IAM needed).

---

## 6. Secrets & keys

- **JWT (RS256)**: generated once in §4b into the `trustpay_secrets` volume at
  `/run/secrets/jwt_private.pem` / `jwt_public.pem`. Persist this volume across
  redeploys. To rotate, delete the two files and re-run §4b (invalidates sessions).
- **Account HMAC / receipt signing keys**: env-driven; keep them out of git. For a
  hackathon the in-container defaults are acceptable; for anything real, mount them
  from Secret Manager and add them to `.env.gcp`.
- **`.env.gcp` is gitignored** (only `.env.gcp.example` is tracked). Never commit secrets.

---

## 7. Migrations & seeding

- Migrations run automatically in the API entrypoint (`alembic upgrade head`).
- Manual: `$COMPOSE exec api alembic upgrade head`
- If you ever hit `relation ... already exists` (schema created out-of-band),
  reconcile with `$COMPOSE exec api alembic stamp head`.
- Seeds are idempotent; safe to re-run.

---

## 8. Persistence & evidence storage

- Postgres data → `pgdata` volume; Redis → `redisdata`; evidence → `trustpay_evidence`
  (mounted at `/data/evidence`, served at `$PUBLIC_URL/media`).
- The evidence backend is the **local-disk shim** (`EVIDENCE_STORAGE_BACKEND=local`).
  That is fine for the demo. Moving to **Cloud Storage** (Phase 7 in `docs/11`) means
  implementing the S3/GCS adapter behind the existing `Storage` interface — no API change.
- **Backups**: schedule boot-disk snapshots (≈$1.50/mo for 30 GB):
  ```bash
  gcloud compute resource-policies create snapshot-schedule trustpay-daily \
    --region=asia-southeast2 --max-retention-days=7 \
    --on-source-disk-delete=apply-retention-policy
  ```

---

## 9. Reverse proxy, domain, CORS, WebAuthn

- **Caddy** (in the bundle) terminates TLS and routes `/api/*`, `/media/*`,
  `/healthz`, `/docs*`, `/openapi.json` → `api:8000`; everything else → `web:3000`.
- Point a DNS `A` record at the VM's external IP; set `DOMAIN` + `PUBLIC_URL` to that
  hostname and Caddy fetches a Let's Encrypt cert automatically.
- For an IP-only demo (no domain), set `DOMAIN=:80` and `PUBLIC_URL=http://<VM_IP>`.
- **CORS** is set to `PUBLIC_URL`; because the browser calls the same origin, it just works.
- **WebAuthn** (admin passkeys) requires `WEBAUTHN_RP_ID=$DOMAIN` and
  `WEBAUTHN_ORIGIN=$PUBLIC_URL` — already wired in the compose. Passkeys will not work
  over plain HTTP on an IP.
- The existing `deploy/nginx/trustpay.quesitive.com.conf` is an equivalent nginx setup
  if you prefer nginx over Caddy (proxy to `127.0.0.1:3000` / `:8000`).

---

## 10. Operations

```bash
COMPOSE="docker compose -f deploy/gcp/docker-compose.gcp.yml --env-file deploy/gcp/.env.gcp"
$COMPOSE logs -f api          # tail logs
$COMPOSE up -d --build        # redeploy after a git pull (web rebuilds with PUBLIC_URL)
$COMPOSE down                 # stop (volumes/data persist)

# Cost control
gcloud compute instances stop trustpay-sea --zone=asia-southeast2-a   # VM hours $0
gcloud compute instances start trustpay-sea --zone=asia-southeast2-a
```
Set a billing budget alert at $25/$50. Never leave a reserved-but-unused static IP
($7.30/mo). Attach a static IP only once the demo hostname is fixed.

---

## 11. Alternative (parked): Cloud Run + Cloud SQL + Memorystore

Serverless split (`web` + `api` on Cloud Run, managed DB/cache) is ~**$85–100/mo** at
demo scale (Cloud SQL `db-g1-small` ≈ $33 + Memorystore ≈ $35–50). It is more "cloud
native" but: the evidence shim needs GCS, the API needs a VPC connector for Memorystore,
and the hackathon mandates GCE anyway. Revisit post-hackathon (see `docs/06` NG-7).

---

## 12. Pre-flight checklist

- [ ] `gcloud services enable compute aiplatform`
- [ ] VM created (`e2-small`, `asia-southeast2-a`, tags `http-server,https-server`)
- [ ] Firewall allows tcp 80/443
- [ ] `deploy/gcp/.env.gcp` filled (DOMAIN, PUBLIC_URL, strong `POSTGRES_PASSWORD`)
- [ ] `$COMPOSE build` succeeds
- [ ] JWT keys generated (§4b)
- [ ] `$COMPOSE up -d` → all services `healthy`
- [ ] `seed_banks` + `seed_demo` run
- [ ] `curl localhost/healthz` returns `ok`
- [ ] Public URL loads the PWA; `/check`, `/report`, `/tools/scam-message` work
- [ ] `AI_PROVIDER` set as intended; deal-check/message analyzer return `engine` accordingly
- [ ] Billing budget alert created
- [ ] Boot-disk snapshot schedule created

---

*Builds on [`07-gce-cheap-usecase-notes.md`](07-gce-cheap-usecase-notes.md) (cost) and
[`11-handoff-next-agent.md`](11-handoff-next-agent.md) (deferred storage/auth hardening).*
