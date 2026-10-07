#!/usr/bin/env bash
# Daily Supabase ping so a free-tier project isn't paused for inactivity.
# Installed as /etc/cron.d/personacr-keepalive by setup-server.sh; logs go to
#   journalctl -t personacr-keepalive
# Runs a real (tiny) Postgres query through PostgREST with the service role key
# from deploy/.env.prod — the key never leaves this machine.
set -euo pipefail

ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env.prod"
if [ ! -f "$ENV_FILE" ]; then
  echo "skip: $ENV_FILE not found"
  exit 0
fi

# Read KEY=value without sourcing the file (values may contain shell characters).
env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }

SUPABASE_URL="$(env_value SUPABASE_URL)"
KEY="$(env_value SUPABASE_SERVICE_ROLE_KEY)"
if [ -z "$SUPABASE_URL" ] || [ -z "$KEY" ]; then
  echo "skip: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in $ENV_FILE"
  exit 0
fi

status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 --retry 3 --retry-delay 10 \
  "${SUPABASE_URL%/}/rest/v1/fingerprints?select=id&limit=1" \
  -H "apikey: ${KEY}" -H "Authorization: Bearer ${KEY}")"

if [ "$status" = "200" ]; then
  echo "ok: Supabase responded 200 at $(date -u +%FT%TZ)"
else
  echo "FAILED: Supabase responded HTTP ${status} at $(date -u +%FT%TZ)"
  exit 1
fi
