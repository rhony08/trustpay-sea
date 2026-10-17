#!/usr/bin/env bash
# TrustPay SEA — bring up the stack ON the GCE VM (run from the repo root).
#
# Writes deploy/gcp/.env.gcp with strong generated secrets if absent, builds the
# images, generates the JWT keypair, starts everything, and seeds the DB.
#
# Usage (on the VM, from the repo root):
#   DOMAIN=trustpay.example.com ./deploy/gcp/remote-deploy.sh
set -euo pipefail

: "${DOMAIN:?set DOMAIN e.g. trustpay.example.com (or ':80' for IP-only)}"
PUBLIC_URL="${PUBLIC_URL:-https://$DOMAIN}"
ENV_FILE="deploy/gcp/.env.gcp"
COMPOSE=(docker compose -f deploy/gcp/docker-compose.gcp.yml --env-file "$ENV_FILE")

rand() { openssl rand -hex 32; }

if [ ! -f "$ENV_FILE" ]; then
  echo "→ writing $ENV_FILE with generated secrets"
  cat > "$ENV_FILE" <<EOF
DOMAIN=$DOMAIN
PUBLIC_URL=$PUBLIC_URL
POSTGRES_USER=trustpay
POSTGRES_PASSWORD=$(rand)
POSTGRES_DB=trustpay
ENVIRONMENT=prod
MFA_REQUIRED_FOR_ADMINS=true
ACCOUNT_HMAC_KEY=$(rand)
RECEIPT_SIGNING_KEY=$(rand)
AI_PROVIDER=${AI_PROVIDER:-mock}
GCP_PROJECT=${GCP_PROJECT:-}
GCP_LOCATION=${GCP_LOCATION:-asia-southeast1}
GCP_VISION_MODEL=gemini-2.5-flash
GCP_TEXT_MODEL=gemini-2.5-flash
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
SEMAKMULE_API_KEY=${SEMAKMULE_API_KEY:-}
EOF
else
  echo "→ reusing existing $ENV_FILE"
fi

echo "→ building images (this takes a few minutes on e2-small)"
"${COMPOSE[@]}" build

echo "→ generating JWT keypair (one-off, ENVIRONMENT=dev so it self-generates)"
"${COMPOSE[@]}" run --rm -e ENVIRONMENT=dev --entrypoint sh api \
  -c "python -m app.generate_dev_keys"

echo "→ starting the stack"
"${COMPOSE[@]}" up -d

echo "→ waiting for API health"
for i in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T api python -c \
      "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz',timeout=3).status==200 else 1)" 2>/dev/null; then
    echo "  API healthy"; break
  fi
  sleep 5
done

echo "→ seeding bank reference + demo data"
"${COMPOSE[@]}" exec -T api python -m app.seeds.seed_banks
"${COMPOSE[@]}" exec -T api python -m app.seeds.seed_demo

echo
echo "✔ Deployed. Open $PUBLIC_URL"
echo "  Demo admin: analyst@trustpay.dev / demo-analyst-pass"
echo "  Status:     ${COMPOSE[*]} ps"
