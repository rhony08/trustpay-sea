#!/usr/bin/env bash
# TrustPay SEA — fill Secret Manager shells created by Terraform.
#
# Usage:
#   PREFIX=trustpay-dev PROJECT_ID=my-proj REGION=asia-southeast2 \
#     DB_PRIVATE_IP=10.x.x.x REDIS_HOST=10.x.x.x \
#     ./gcp/scripts/bootstrap-secrets.sh
#
# Optional env:
#   DB_USER / DB_PASS / DB_NAME      (default trustpay / random shown by terraform / trustpay)
#   JWT_PRIVATE_PEM / JWT_PUBLIC_PEM (paths; prod MUST provide real keys —
#                                    dev generates an ephemeral pair like
#                                    services/api/app/generate_dev_keys.py)
#   ACCOUNT_HMAC_KEY                 (generated with openssl rand if unset)
#   GEMINI_API_KEY / FACTCHECK_API_KEY (unset = mock-first per ADR-012; skipped)
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
: "${PREFIX:?set PREFIX e.g. trustpay-dev}"
: "${DB_PRIVATE_IP:?set DB_PRIVATE_IP from terraform output sql_private_ip}"
: "${REDIS_HOST:?set REDIS_HOST from terraform output redis_host}"
REGION="${REGION:-asia-southeast2}"
DB_USER="${DB_USER:-trustpay}"
DB_NAME="${DB_NAME:-trustpay}"

have() { gcloud secrets describe "$1" --project="$PROJECT_ID" >/dev/null 2>&1; }
put() { # $1=short name $2=file
  local short="$1" file="$2" full="${PREFIX}-${short}"
  if ! have "$full"; then
    echo " Gerade creating shell $full (terraform should have made it)"
    gcloud secrets create "$full" --project="$PROJECT_ID" --replication-policy=automatic >/dev/null
  fi
  gcloud secrets versions add "$full" --project="$PROJECT_ID" --data-file="$file" >/dev/null
  echo "  ✓ $full"
}

echo "→ bootstrap secrets for $PREFIX in $PROJECT_ID ($REGION)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# 1. Composite connection strings (asyncpg driver matches services/api/app/config.py)
if [ -z "${DB_PASS:-}" ]; then
  if [ -t 0 ]; then read -rsp "DB password for $DB_USER: " DB_PASS; echo; else
    echo "ERROR: set DB_PASS (terraform output random_password, or Cloud SQL user password)"; exit 1; fi
fi
printf '%s' "postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_PRIVATE_IP}:5432/${DB_NAME}" > "$tmp/database-url"
put database-url "$tmp/database-url"

printf '%s' "redis://${REDIS_HOST}:6379/0" > "$tmp/redis-url"
put redis-url "$tmp/redis-url"

# 2. RS256 JWT keypair — files mounted at /run/secrets/*.pem in Cloud Run
if [ -n "${JWT_PRIVATE_PEM:-}" ] && [ -n "${JWT_PUBLIC_PEM:-}" ]; then
  put jwt-private-pem "$JWT_PRIVATE_PEM"
  put jwt-public-pem "$JWT_PUBLIC_PEM"
else
  echo "  ! no JWT keys given — generating EPHEMERAL dev pair (prod: pass real keys)"
  openssl genrsa -out "$tmp/jwt_private.pem" 2048 2>/dev/null
  openssl rsa -in "$tmp/jwt_private.pem" -pubout -out "$tmp/jwt_public.pem" 2>/dev/null
  put jwt-private-pem "$tmp/jwt_private.pem"
  put jwt-public-pem "$tmp/jwt_public.pem"
fi

# 3. Account HMAC stand-in (Phase 7 replaces with KMS; hash_version rows allow rotation)
if [ -n "${ACCOUNT_HMAC_KEY:-}" ]; then printf '%s' "$ACCOUNT_HMAC_KEY" > "$tmp/hmac";
else openssl rand -hex 32 > "$tmp/hmac"; fi
put account-hmac-key "$tmp/hmac"

# 4. Optional integrations — absent = graceful mock (ADR-012), so skip, don't store empty
for pair in "GEMINI_API_KEY:gemini-api-key" "FACTCHECK_API_KEY:factcheck-api-key"; do
  var="${pair%%:*}"; short="${pair##*:}"
  if [ -n "${!var:-}" ]; then printf '%s' "${!var}" > "$tmp/opt"; put "$short" "$tmp/opt";
  else echo "  - $short: unset, API runs mocked (set $var to enable)"; fi
done

echo "done. Verify: gcloud secrets list --project=$PROJECT_ID --filter=name:$PREFIX"
