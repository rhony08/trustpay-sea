#!/usr/bin/env bash
# TrustPay SEA — provision a single GCE VM for the self-contained stack.
#
# Creates: a static external IP, a 80/443 firewall rule, and one Ubuntu VM with
# Docker + a 2 GB swapfile (headroom for image builds). Idempotent — safe to
# re-run. Does NOT deploy the app; see docs/13-gcp-deployment.md §4.
#
# Usage:
#   PROJECT_ID=my-proj DOMAIN=trustpay.example.com ./deploy/gcp/provision.sh
#
# Optional env: REGION, ZONE, INSTANCE, MACHINE_TYPE, DISK_SIZE, ADDRESS_NAME
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID (gcloud config get-value project)}"
: "${DOMAIN:?set DOMAIN e.g. trustpay.example.com}"

REGION="${REGION:-asia-southeast2}"
ZONE="${ZONE:-asia-southeast2-a}"
INSTANCE="${INSTANCE:-trustpay-sea}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-small}"
DISK_SIZE="${DISK_SIZE:-30GB}"
ADDRESS_NAME="${ADDRESS_NAME:-trustpay-ip}"
TAGS="http-server,https-server"

echo "→ project=$PROJECT_ID region=$REGION zone=$ZONE instance=$INSTANCE type=$MACHINE_TYPE"
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable compute.googleapis.com >/dev/null

# 1. Static external IP (needed so DNS survives reboots)
if ! gcloud compute addresses describe "$ADDRESS_NAME" --region="$REGION" >/dev/null 2>&1; then
  echo "→ reserving static IP $ADDRESS_NAME"
  gcloud compute addresses create "$ADDRESS_NAME" --region="$REGION" >/dev/null
fi
IP="$(gcloud compute addresses describe "$ADDRESS_NAME" --region="$REGION" --format='value(address)')"
echo "→ static IP: $IP"

# 2. Firewall for HTTP/HTTPS
if ! gcloud compute firewall-rules describe trustpay-web >/dev/null 2>&1; then
  echo "→ creating firewall rule trustpay-web (tcp:80,443)"
  gcloud compute firewall-rules create trustpay-web \
    --allow=tcp:80,tcp:443 --target-tags="$TAGS" >/dev/null
fi

# 3. VM with Docker + swap
STARTUP='#! /bin/bash
set -e
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-plugin git
systemctl enable --now docker
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi'

if ! gcloud compute instances describe "$INSTANCE" --zone="$ZONE" >/dev/null 2>&1; then
  echo "→ creating VM $INSTANCE"
  gcloud compute instances create "$INSTANCE" \
    --zone="$ZONE" --machine-type="$MACHINE_TYPE" \
    --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
    --boot-disk-size="$DISK_SIZE" --boot-disk-type=pd-standard \
    --address="$IP" --tags="$TAGS" \
    --metadata=startup-script="$STARTUP" >/dev/null
else
  echo "→ VM $INSTANCE already exists"
fi

cat <<EOF

✔ Provisioned.
  VM:   $INSTANCE  ($ZONE, $MACHINE_TYPE)
  IP:   $IP

Next:
  1. At your DNS provider, add:   A   $DOMAIN  ->  $IP
  2. Wait for the VM startup script (~60s), then:
       gcloud compute ssh $INSTANCE --zone=$ZONE
  3. Deploy the app (on the VM): see docs/13-gcp-deployment.md §4
EOF
