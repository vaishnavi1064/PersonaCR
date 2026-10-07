#!/usr/bin/env bash
# Build and (re)start the stack ON THE SERVER, then wait for the backend to be healthy.
# deploy.sh / deploy.ps1 run this over ssh right after `git pull`; you can also
# run it by hand on the server:  bash ~/PersonaCR/deploy/server-deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root
ENV_FILE=deploy/.env.prod
COMPOSE=(docker compose -f deploy/docker-compose.prod.yml --env-file "$ENV_FILE")

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — cp deploy/.env.prod.example $ENV_FILE and fill it in." >&2
  exit 1
fi
chmod 600 "$ENV_FILE"

domain="$(grep -E '^DOMAIN=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
echo "==> $(git log -1 --format='%h %s')"

# A broken Caddyfile would take the whole site down on restart — check it first.
echo "==> Validating the Caddyfile"
docker run --rm -e DOMAIN="$domain" -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile --validate >/dev/null

echo "==> Building images on the server"
"${COMPOSE[@]}" build

echo "==> Starting containers"
"${COMPOSE[@]}" up -d --remove-orphans

# git pull replaces the Caddyfile (new inode); a single-file bind mount keeps
# showing the old one until the container restarts. Restart only if it changed.
if [ "$("${COMPOSE[@]}" exec -T caddy cat /etc/caddy/Caddyfile | sha256sum)" != "$(sha256sum < deploy/Caddyfile)" ]; then
  echo "==> Caddyfile changed — restarting caddy"
  "${COMPOSE[@]}" restart caddy
fi

echo "==> Waiting for the backend to be healthy"
for i in $(seq 1 60); do
  state="$(docker inspect -f '{{.State.Health.Status}}' "$("${COMPOSE[@]}" ps -q backend)" 2>/dev/null || echo starting)"
  if [ "$state" = "healthy" ]; then
    echo "backend healthy after ~$((i * 5)) s"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "backend not healthy after 5 minutes (state=$state). Recent logs:" >&2
    "${COMPOSE[@]}" logs --tail=80 backend >&2
    exit 1
  fi
  sleep 5
done

echo "==> Health through Caddy + TLS (https://${domain}/health, resolved locally)"
# First start: Caddy needs a few seconds to get the certificate.
for i in $(seq 1 24); do
  if curl -fsS --max-time 10 --resolve "${domain}:443:127.0.0.1" "https://${domain}/health"; then
    echo
    break
  fi
  if [ "$i" -eq 24 ]; then
    echo "https://${domain}/health not reachable after 2 minutes. Caddy logs:" >&2
    "${COMPOSE[@]}" logs --tail=60 caddy >&2
    exit 1
  fi
  sleep 5
done

"${COMPOSE[@]}" ps

# Old image layers from previous builds pile up on the 64 GB disk.
docker image prune -f >/dev/null
echo "==> Deployed"
