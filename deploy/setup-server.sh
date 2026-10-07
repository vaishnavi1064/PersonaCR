#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 VM for PersonaCR.
# Run ON THE SERVER as the login user (azureuser), not as root:
#   curl -fsSL https://raw.githubusercontent.com/vaishnavi1064/PersonaCR/main/deploy/setup-server.sh -o setup-server.sh
#   bash setup-server.sh
#
# Idempotent — safe to re-run. Does:
#   1. Docker Engine + compose plugin from Docker's apt repo, enabled at boot, log rotation
#   2. 4 GB swap file (persistent), low swappiness, vm.overcommit_memory=1 for Redis
#   3. ufw: allow 22, 80, 443 only
#   4. git clone the repo to ~/PersonaCR
#   5. Supabase keep-alive cron (/etc/cron.d/personacr-keepalive)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/vaishnavi1064/PersonaCR.git}"
APP_DIR="${APP_DIR:-$HOME/PersonaCR}"
SWAP_SIZE="${SWAP_SIZE:-4G}"
DEPLOY_USER="$(id -un)"

if [ "$(id -u)" -eq 0 ]; then
  echo "Run as your login user (it uses sudo), not root." >&2
  exit 1
fi

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ── 1. Docker ────────────────────────────────────────────────────────────────
log "Installing Docker Engine"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git ufw cron
if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# Rotate container logs so they can't fill the 64 GB disk.
if [ ! -f /etc/docker/daemon.json ]; then
  sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
  sudo systemctl restart docker
fi

# Start at boot — with restart: unless-stopped this brings the stack back after auto-start.
sudo systemctl enable --now docker.service containerd.service
sudo usermod -aG docker "$DEPLOY_USER"

# ── 2. Swap ──────────────────────────────────────────────────────────────────
log "Configuring ${SWAP_SIZE} swap"
if ! sudo swapon --show | grep -q '^/swapfile'; then
  if [ ! -f /swapfile ]; then
    sudo fallocate -l "$SWAP_SIZE" /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
  fi
  sudo swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
# Swap only under pressure; Redis wants overcommit for background saves.
sudo tee /etc/sysctl.d/99-personacr.conf >/dev/null <<'CONF'
vm.swappiness=10
vm.overcommit_memory=1
CONF
sudo sysctl --system >/dev/null

# ── 3. Firewall ──────────────────────────────────────────────────────────────
log "Configuring ufw (22, 80, 443)"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose

# ── 4. Repo ──────────────────────────────────────────────────────────────────
log "Cloning ${REPO_URL} → ${APP_DIR}"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

# ── 5. Supabase keep-alive ───────────────────────────────────────────────────
# Free-tier projects pause after a week without activity. Cron runs in UTC:
# 18:00 UTC is 11:00 PDT / 10:00 PST — inside the 7 AM–5 PM Pacific uptime window.
# Also once shortly after every boot. Output goes to the journal:
#   journalctl -t personacr-keepalive
log "Installing Supabase keep-alive cron"
sudo tee /etc/cron.d/personacr-keepalive >/dev/null <<CRON
SHELL=/bin/bash
0 18 * * * ${DEPLOY_USER} /bin/bash ${APP_DIR}/deploy/supabase-keepalive.sh 2>&1 | logger -t personacr-keepalive
@reboot ${DEPLOY_USER} sleep 300 && /bin/bash ${APP_DIR}/deploy/supabase-keepalive.sh 2>&1 | logger -t personacr-keepalive
CRON
sudo chmod 644 /etc/cron.d/personacr-keepalive
sudo systemctl enable --now cron

log "Done"
cat <<EOF

Next:
  1. Log out and back in (or run: newgrp docker) so 'docker' works without sudo.
  2. cp ${APP_DIR}/deploy/.env.prod.example ${APP_DIR}/deploy/.env.prod
     nano ${APP_DIR}/deploy/.env.prod      # fill in the secrets
     chmod 600 ${APP_DIR}/deploy/.env.prod
  3. bash ${APP_DIR}/deploy/server-deploy.sh   # first build + start (10–20 min)
EOF
