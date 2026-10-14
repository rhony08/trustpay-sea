# TrustPay SEA on GCP (Jakarta-primary)

Docker-compose mapping → GCP:

| Local | GCP |
|---|---|
| `postgres:16` | Cloud SQL for PostgreSQL 16 (private IP, PITR backups) |
| `redis:7` | Memorystore for Redis 7 (Basic) |
| `api:8000` | Cloud Run `trustpay-API` + `api-runtime` SA |
| `web:3000` | Cloud Run `trustpay-web` |
| evidence files | Cloud Storage bucket (90-day lifecycle) |

## First deploy (dev)

```bash
gcloud auth login && gcloud config set project <PROJECT_ID>

cp gcp/terraform/terraform.tfvars.example gcp/terraform/terraform.tfvars
# edit project_id (region defaults to asia-southeast2 Jakarta — PDP residency)

cd gcp/terraform && terraform init && terraform apply && cd ../..

PREFIX=trustpay-dev PROJECT_ID=<PROJECT_ID> REGION=asia-southeast2 \
  DB_PRIVATE_IP=$(terraform -chdir=gcp/terraform output -raw sql_private_ip) \
  REDIS_HOST=$(terraform -chdir=gcp/terraform output -raw redis_host) \
  DB_PASS='<cloud-sql trustpay password>' \
  ./gcp/scripts/bootstrap-secrets.sh

PROJECT_ID=<PROJECT_ID> REGION=asia-southeast2 ENV=dev ./gcp/scripts/deploy.sh
```

Deploy order inside the script: build images → migrate Job (`alembic upgrade head`) → API → web. First web build bakes a placeholder API URL; the script prints a rebuild hint once the real API URL exists.

## Secrets (never in git)

Shells are created by Terraform; values filled by `bootstrap-secrets.sh`:
`database-url`, `redis-url`, `jwt-private-pem`, `jwt-public-pem` (mounted at `/run/secrets/*.pem`; prod refuses self-generated keys), `account-hmac-key`, `gemini-api-key` / `factcheck-api-key` (unset = mock-first per ADR-012).

At runtime the API reads the same env names as `.env` plus:
- `CORS_ALLOW_ORIGINS` — set to the web Run URL (comma-separated for staging+prod).
- `PORT` — set by Cloud Run; Dockerfile falls back to 8000 locally.

## Google tools wired (judging checklist)

- **Cloud Run / SQL / Memorystore / Storage / CDN / Armor / Secret Manager / Build / Deploy** — hosting
- **Gemini (Vertex AI, Flash-Lite → Flash)** — forensics + explanations (`GEMINI_API_KEY` empty = mock)
- **Web Risk Lookup API** — scam URL intel (commercial API; Safe Browsing is non-commercial-only)
- **reCAPTCHA Enterprise + App Check** — anti-abuse for crowdsourced reports
- **ML Kit Code Scanner** — permissionless offline QR scan (Android); web falls back to `BarcodeDetector`/jsQR
- **Translation AI + Vision OCR** — report normalization + evidence slip OCR
- **BigQuery dataset** (`trustpay_<env>_fraud`) — score/report analytics; add Looker later

## Cost / region notes

- Jakarta (`asia-southeast2`) primary for UU PDP 27/2022 + PP 33/2026 residency. Singapore failover only.
- Indonesia/Oceania egress is $0.15/GiB — keep Run+SQL+Redis+bucket in one region, put Cloud CDN in front.
- Start `db-g1-small` + 1 GB Redis for dev; prod → `db-custom-2-4096` REGIONAL + Standard-tier Redis.
