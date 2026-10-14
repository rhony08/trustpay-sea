#!/usr/bin/env bash
# TrustPay SEA — build, migrate, deploy to Cloud Run (Jakarta-primary).
#
# Prereqs: gcloud (authenticated), envsubst (gettext), terraform applied once,
#   gcp/scripts/bootstrap-secrets.sh already run.
#
# Usage:
#   PROJECT_ID=my-proj REGION=asia-southeast2 ENV=dev ./gcp/scripts/deploy.sh
#   PROJECT_ID=my-proj SKIP_BUILD=1 ./gcp/scripts/deploy.sh  # YAML-only redeploy
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast2}"
ENV="${ENV:-dev}"
PREFIX="trustpay-${ENV}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${PREFIX}-images"
API_IMAGE="${REGISTRY}/api:${TAG}"
WEB_IMAGE="${REGISTRY}/web:${TAG}"
OUT="$(mktemp -d)"; trap 'rm -rf "$OUT"' EXIT

echo "→ $PREFIX @ $PROJECT_ID/$REGION (tag $TAG)"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  echo "→ building API image (Cloud Build)"
  gcloud builds submit ./services/api --tag "$API_IMAGE" --project="$PROJECT_ID" --quiet
  echo "→ building WEB image (NEXT_PUBLIC_API_URL baked at build time)"
  # Public API URL unknown before first deploy: build once with placeholder,
  # then rebuild after API URL is known (second run fills it correctly).
  PUBLIC_API_TMP="${PUBLIC_API_URL:-https://placeholder.invalid}"
  gcloud builds submit ./apps/web --tag "$WEB_IMAGE" --project="$PROJECT_ID" --quiet \
    --substitutions=_NEXT_PUBLIC_API_URL="$PUBLIC_API_TMP"
else
  echo "→ SKIP_BUILD=1, reusing $TAG"
fi

echo "→ reading terraform outputs"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SQL_CONN="$(terraform -chdir=gcp/terraform output -raw sql_connection_name)"
VPC_CONN="$(terraform -chdir=gcp/terraform output -raw vpc_connector)"
API_SA="$(terraform -chdir=gcp/terraform output -raw api_service_account)"
API_MIN_SCALE="$([ "$ENV" = "prod" ] && echo 1 || echo 0)"

export PROJECT_ID REGION ENVIRONMENT="$ENV" PREFIX PROJECT_NUMBER
export API_IMAGE WEB_IMAGE SQL_CONNECTION_NAME="$SQL_CONN"
export VPC_CONNECTOR="$VPC_CONN" API_SERVICE_ACCOUNT="$API_SA" API_MIN_SCALE="$API_MIN_SCALE"

echo "→ migrate (alembic upgrade head via Cloud Run Job)"
envsubst < gcp/cloudrun/migrate-job.yaml > "$OUT/migrate-job.yaml"
gcloud run jobs replace "$OUT/migrate-job.yaml" --region="$REGION" --project="$PROJECT_ID" --quiet
gcloud run jobs execute trustpay-migrate --region="$REGION" --project="$PROJECT_ID" --wait

echo "→ deploy API"
envsubst < gcp/cloudrun/api-service.yaml > "$OUT/api-service.yaml"
gcloud run services replace "$OUT/api-service.yaml" --region="$REGION" --project="$PROJECT_ID" --quiet

API_URL="$(gcloud run services describe trustpay-API --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"
echo "  API: $API_URL  (health: $API_URL/healthz)"

echo "→ deploy WEB (PUBLIC_API_URL=$API_URL)"
export PUBLIC_API_URL="$API_URL"
if [ "${SKIP_BUILD:-0}" != "1" ] && [ -z "${PUBLIC_API_URL:-}" ]; then :; fi
envsubst < gcp/cloudrun/web-service.yaml > "$OUT/web-service.yaml"
gcloud run services replace "$OUT/web-service.yaml" --region="$REGION" --project="$PROJECT_ID" --quiet

WEB_URL="$(gcloud run services describe trustpay-web --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"
echo "done. WEB: $WEB_URL  API docs: $API_URL/docs"
echo "TIP: first deploy baked a placeholder API URL into .next — rebuild web once:"
echo "  PUBLIC_API_URL=$API_URL SKIP_BUILD=0 ./gcp/scripts/deploy.sh  # or Cloud Build with _NEXT_PUBLIC_API_URL"
