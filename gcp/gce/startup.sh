#!/bin/bash
# TrustPay SEA — GCE startup script (runs as root on every boot).
# Passed via --metadata-from-file startup-script=gcp/gce/startup.sh.
# Reads config from instance metadata (no secrets in metadata!):
#   REPO_URL, GIT_REF, PREFIX (e.g. trustpay-dev), ENVIRONMENT, CORS_ORIGINS (optional)
# Secrets come from Secret Manager shells created by gcp/terraform
# (filled by gcp/scripts/bootstrap-secrets.sh). VM needs a service account
# with roles/secretmanager.secretAccessor + logging/monitoring writer.
set -euo pipefail
exec > /var/log/trustpay-startup.log 2>&1

meta() { curl -sf -H 'Metadata-Flavor: Google' \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }

PROJECT_ID="$(meta project-id 2>/dev/null || curl -sf -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id)"
REPO_URL="$(meta REPO_URL)"; GIT_REF="$(meta GIT_REF 2>/dev/null || echo main)"
PREFIX="$(meta PREFIX)"; ENVIRONMENT="$(meta ENVIRONMENT 2>/dev/null || echo dev)"
CORS_ORIGINS="$(meta CORS_ORIGINS 2>/dev/null || echo '')"
APP_DIR=/opt/trustpay
DATA_MOUNT=/mnt/pgdata

echo "→ trustpay boot: prefix=$PREFIX env=$ENVIRONMENT ref=$GIT_REF"

# 1. Docker (Ubuntu LTS) + compose plugin -------------------------------------
if ! command -v docker >/dev/null; then
  apt-get update && apt-get install -y docker.io docker-compose-plugin git
  systemctl enable --now docker
fi

# 2. Data disk → holds ALL docker state (images + pgdata volume). -------------
# Device name 'pgdata' appears as /dev/disk/by-id/google-pgdata. Formatting is
# guarded by blkid so reboots/autoheal never wipe the disk.
if [ -e /dev/disk/by-id/google-pgdata ]; then
  mkdir -p "$DATA_MOUNT"
  if ! blkid /dev/disk/by-id/google-pgdata >/dev/null 2>&1; then
    mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard \
      /dev/disk/by-id/google-pgdata
  fi
  mount -o discard,defaults /dev/disk/by-id/google-pgdata "$DATA_MOUNT" || true
  grep -q "$DATA_MOUNT" /etc/fstab || \
    echo "/dev/disk/by-id/google-pgdata $DATA_MOUNT ext4 discard,defaults,nofail 0 2" >> /etc/fstab
  mkdir -p "$DATA_MOUNT/docker"
  if [ "$(docker info -f '{{.DockerRootDir}}')" != "$DATA_MOUNT/docker" ]; then
    mkdir -p /etc/docker
    printf '{"data-root":"%s/docker"}\n' "$DATA_MOUNT" > /etc/docker/daemon.json
    systemctl restart docker
  fi
else
  echo "  ! no pgdata disk attached — docker state lives on boot disk (demo-only)"
fi

# 3. Repo ----------------------------------------------------------------------
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --all && git -C "$APP_DIR" checkout "$GIT_REF" \
    && git -C "$APP_DIR" pull --ff-only || true
else
  git clone --branch "$GIT_REF" "$REPO_URL" "$APP_DIR"
fi

# 4. Secrets → /opt/trustpay/.env (0600, never logged) --------------------------
# Empty/missing secrets are SKIPPED so stock fallbacks win: compose's own
# DATABASE_URL/REDIS_URL, dev JWT self-generation (prod refuses — mount real keys).
get_secret() { gcloud secrets versions access latest --secret="$1" \
  --project="$PROJECT_ID" 2>/dev/null || echo ''; }
put_if_set() { [ -n "$2" ] && echo "$1=$2"; }
umask 077
{
  echo "ENVIRONMENT=$ENVIRONMENT"
  put_if_set DATABASE_URL "$(get_secret "${PREFIX}-database-url")"
  put_if_set REDIS_URL "$(get_secret "${PREFIX}-redis-url")"
  put_if_set ACCOUNT_HMAC_KEY "$(get_secret "${PREFIX}-account-hmac-key")"
  echo "JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem"
  echo "JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem"
  [ -n "$CORS_ORIGINS" ] && echo "CORS_ALLOW_ORIGINS=$CORS_ORIGINS"
  put_if_set GEMINI_API_KEY "$(get_secret "${PREFIX}-gemini-api-key")"
  put_if_set FACTCHECK_API_KEY "$(get_secret "${PREFIX}-factcheck-api-key")"
} > "$APP_DIR/.env"
mkdir -p "$APP_DIR/secrets"
for k in "jwt-private-pem:jwt_private.pem" "jwt-public-pem:jwt_public.pem"; do
  short="${k%%:*}"; file="${k##*:}"
  pem="$(get_secret "${PREFIX}-${short}")"
  # absent/empty → no file, so dev self-gen kicks in (prod refuses loudly)
  if [ -n "$pem" ]; then printf '%s' "$pem" > "$APP_DIR/secrets/$file";
  else rm -f "$APP_DIR/secrets/$file"; fi
done
chmod 600 "$APP_DIR/secrets/"*.pem 2>/dev/null || true

# 5. Compose up. Override mounts only PEMs that exist; when absent the API -----
# container self-generates dev keys in its own writable layer (prod refuses).
cd "$APP_DIR"
VOLUMES=""
[ -f secrets/jwt_private.pem ] && VOLUMES="$VOLUMES
      - ./secrets/jwt_private.pem:/run/secrets/jwt_private.pem:ro"
[ -f secrets/jwt_public.pem ] && VOLUMES="$VOLUMES
      - ./secrets/jwt_public.pem:/run/secrets/jwt_public.pem:ro"
printf 'services:\n  api:\n    volumes:%s\n' "$VOLUMES" > docker-compose.gce.yml
COMPOSE="docker compose -p trustpay -f docker-compose.yml -f docker-compose.gce.yml"
$COMPOSE up -d --build

# 6. Wait for health (generous: first boot pulls images + runs migrations) -------
for i in $(seq 1 60); do
  if curl -sf localhost:8000/healthz >/dev/null; then
    echo "✓ API healthy after ${i}x10s"; exit 0; fi
  sleep 10
done
echo "✗ API never became healthy — see: docker compose -p trustpay logs api"
$COMPOSE ps || true
exit 1
