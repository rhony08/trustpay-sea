#!/usr/bin/env bash
# TrustPay SEA — single-VM GCE deploy (the docs/07 Option A, scripted).
#
# Usage:
#   PROJECT_ID=my-proj REPO_URL=https://github.com/org/trustpay-sea.git \
#     ./gcp/gce/deploy.sh
# Optional: REGION=asia-southeast2 ZONE=asia-southeast2-a MACHINE=e2-small
#   ENV=dev GIT_REF=main MODE=standalone|mig STATIC_IP=1
#
# MODE=standalone (default): one VM + 10 GB pgdata disk + daily snapshots.
# MODE=mig: instance template + size-1 MIG with HTTP autohealer (:8000/healthz)
#   + stateful pgdata disk (survives autoheal) — $0 extra, see docs/08 §6/§6b.
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"; : "${REPO_URL:?set REPO_URL}"
REGION="${REGION:-asia-southeast2}"
ZONE="${ZONE:-asia-southeast2-a}"
ENV="${ENV:-dev}"
PREFIX="trustpay-${ENV}"
MACHINE="${MACHINE:-e2-small}"
GIT_REF="${GIT_REF:-main}"
MODE="${MODE:-standalone}"
STATIC_IP="${STATIC_IP:-1}"
CORS_ORIGINS="${CORS_ORIGINS:-}"

echo "→ $PREFIX @ $PROJECT_ID/$ZONE ($MACHINE, mode=$MODE)"

# 0. Service account (least privilege: logs + metrics + secret read) ------------
SA="${PREFIX}-gce@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" --project="$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "${PREFIX}-gce" --project="$PROJECT_ID" \
       --display-name="TrustPay GCE runtime ($ENV)" >/dev/null
for role in roles/logging.logWriter roles/monitoring.metricWriter \
            roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role="$role" --condition=None >/dev/null 2>&1 || true
done

# 1. Snapshot schedule (daily 02:00, 7-day retention) ---------------------------
gcloud compute resource-policies describe trustpay-daily --region="$REGION" \
  --project="$PROJECT_ID" >/dev/null 2>&1 || \
gcloud compute resource-policies create snapshot-schedule trustpay-daily \
  --project="$PROJECT_ID" --region="$REGION" \
  --max-retention-days=7 --on-source-disk-delete=apply-retention-policy \
  --daily-schedule --start-time=02:00 >/dev/null
echo "  ✓ snapshot schedule trustpay-daily"

# 2. Firewall (web only; API exposed for demo — tighten to LB/IAP post-hackathon) --
gcloud compute firewall-rules describe trustpay-web --project="$PROJECT_ID" \
  >/dev/null 2>&1 || \
gcloud compute firewall-rules create trustpay-web --project="$PROJECT_ID" \
  --allow=tcp:80,tcp:443,tcp:3000,tcp:8000 --target-tags=http-server,https-server \
  --description="TrustPay demo web+api" >/dev/null
echo "  ✓ firewall trustpay-web"

META="REPO_URL=$REPO_URL,GIT_REF=$GIT_REF,PREFIX=$PREFIX,ENVIRONMENT=$ENV"
[ -n "$CORS_ORIGINS" ] && META="$META,CORS_ORIGINS=$CORS_ORIGINS"

if [ "$MODE" = "mig" ]; then
# 3-MIG. Health check + template + size-1 MIG + stateful disk -------------------
  gcloud compute health-checks describe trustpay-api-hc --project="$PROJECT_ID" \
    --global >/dev/null 2>&1 || \
  gcloud compute health-checks create http trustpay-api-hc --project="$PROJECT_ID" \
    --global --port=8000 --request-path=/healthz \
    --check-interval=60s --timeout=10s \
    --healthy-threshold=1 --unhealthy-threshold=3 >/dev/null

  gcloud compute instance-templates describe "${PREFIX}-tpl" \
    --project="$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud compute instance-templates create-with-container "${PREFIX}-tpl" \
    --project="$PROJECT_ID" --machine-type="$MACHINE" \
    --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB --boot-disk-type=pd-standard \
    --create-disk=device-name=pgdata,size=10GB,type=pd-standard,auto-delete=no \
    --service-account="$SA" \
    --scopes=https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/devstorage.read_only \
    --tags=http-server,https-server \
    --metadata="$META" \
    --metadata-from-file=startup-script=gcp/gce/startup.sh >/dev/null

  gcloud compute instance-groups managed describe "$PREFIX" --zone="$ZONE" \
    --project="$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud compute instance-groups managed create "$PREFIX" --zone="$ZONE" \
    --project="$PROJECT_ID" --template="${PREFIX}-tpl" --size=1 \
    --health-check=trustpay-api-hc --initial-delay=300 >/dev/null

  gcloud compute instance-groups managed update "$PREFIX" --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --stateful-disk device-name=pgdata,auto-delete=never >/dev/null
  echo "  ✓ MIG $PREFIX (size 1, autoheal :8000/healthz, stateful pgdata)"
  echo "  attach snapshot schedule to the auto-created pgdata disk after first boot:"
  echo "    gcloud compute disks add-resource-policies <pgdata-disk> \\"
  echo "      --resource-policies=trustpay-daily --zone=$ZONE"
else
# 3-VM. Data disk + snapshots + standalone VM -----------------------------------
  gcloud compute disks describe "${PREFIX}-pgdata" --zone="$ZONE" \
    --project="$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud compute disks create "${PREFIX}-pgdata" --project="$PROJECT_ID" \
    --zone="$ZONE" --size=10GB --type=pd-standard \
    --description="TrustPay docker state (images+pgdata)" >/dev/null
  gcloud compute disks add-resource-policies "${PREFIX}-pgdata" --zone="$ZONE" \
    --project="$PROJECT_ID" --resource-policies=trustpay-daily >/dev/null 2>&1 || true
  echo "  ✓ data disk ${PREFIX}-pgdata (+ daily snapshots)"

  ADDR_ARG=""
  if [ "$STATIC_IP" = "1" ]; then
    gcloud compute addresses describe "${PREFIX}-ip" --region="$REGION" \
      --project="$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud compute addresses create "${PREFIX}-ip" --project="$PROJECT_ID" \
      --region="$REGION" >/dev/null
    ADDR_ARG="--address=${PREFIX}-ip"
  fi

  gcloud compute instances describe "$PREFIX" --zone="$ZONE" \
    --project="$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud compute instances create "$PREFIX" --project="$PROJECT_ID" --zone="$ZONE" \
    --machine-type="$MACHINE" --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud --boot-disk-size=30GB \
    --boot-disk-type=pd-standard --disk=name="${PREFIX}-pgdata",device-name=pgdata,mode=rw,boot=no \
    --service-account="$SA" \
    --scopes=https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write \
    --tags=http-server,https-server $ADDR_ARG \
    --metadata="$META" \
    --metadata-from-file=startup-script=gcp/gce/startup.sh >/dev/null
  echo "  ✓ VM $PREFIX"
fi

IP="$(gcloud compute instances describe "$PREFIX" --zone="$ZONE" \
  --project="$PROJECT_ID" --format='value(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || echo '<pending>')"
echo "done. external IP: $IP"
echo "  web → http://$IP:3000   api → http://$IP:8000/docs   health → http://$IP:8000/healthz"
echo "  logs: journalctl -u google-startup-scripts / tail /var/log/trustpay-startup.log"
echo "  redeploy: bump GIT_REF + rolling-replace (MIG) or 'git pull && docker compose up -d --build' on the VM"
