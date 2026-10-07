#!/usr/bin/env bash
# Redeploy from your laptop (Git Bash / WSL / macOS / Linux):
#   bash deploy/deploy.sh
# ssh in → git pull → build images on the server → compose up -d → health check,
# then checks https://$DOMAIN/health from here (DNS + NSG + TLS from the outside).
# Push your commits to GitHub first — the server pulls from origin, not from this laptop.
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/azure_personacr}"
DOMAIN="${DOMAIN:-personacr.northcentralus.cloudapp.azure.com}"
SSH_HOST="${SSH_HOST:-azureuser@$DOMAIN}"
APP_DIR="${APP_DIR:-~/PersonaCR}"
BRANCH="${BRANCH:-main}"

echo "==> Deploying origin/${BRANCH} to ${SSH_HOST}"
# shellcheck disable=SC2029  # APP_DIR/BRANCH expand locally on purpose
ssh -i "$SSH_KEY" -o ServerAliveInterval=30 "$SSH_HOST" \
  "set -e; cd ${APP_DIR} && git fetch --quiet origin && git checkout --quiet ${BRANCH} && git pull --ff-only origin ${BRANCH} && bash deploy/server-deploy.sh"

echo "==> External health check"
for i in $(seq 1 12); do
  if curl -fsS --max-time 10 "https://${DOMAIN}/health"; then
    echo
    echo "==> Live: https://${DOMAIN}"
    exit 0
  fi
  sleep 5
done
echo "https://${DOMAIN}/health is not reachable from here. Check the Azure NSG allows 80/443." >&2
exit 1
