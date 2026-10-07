# Deploying PersonaCR to one Azure VM

The whole stack runs with Docker Compose on one VM. Caddy terminates HTTPS with an automatic Let's Encrypt certificate.

| | |
|---|---|
| VM | Ubuntu 24.04 x64, Standard_B2als_v2 (2 vCPU, 4 GB RAM), 64 GB disk, North Central US |
| URL | https://personacr.northcentralus.cloudapp.azure.com |
| SSH | `ssh -i ~/.ssh/azure_personacr azureuser@personacr.northcentralus.cloudapp.azure.com` |
| Uptime | ~7 AM–5 PM Pacific (Azure auto-shutdown + auto-start); the stack starts by itself on boot |

```
Internet ──443/80──▶ caddy ─┬─ /api/* /health /mcp* /docs* /openapi.json ─▶ backend:8000 (FastAPI)
                            ├─ /metrics ─▶ 404 (internal only)
                            └─ everything else ─▶ frontend:80 (nginx, SPA)
backend ─┬─ redis:6379    (job queue, job status, rate-limit counters)  volume redis_data
worker ──┼─ chromadb:8000 (code embeddings)                             volume chroma_data
         └─ /models       (Jina + MiniLM downloads, fetched once)       volume model_cache
caddy: TLS certificates in volume caddy_data
External: Supabase (auth + Postgres), Anthropic (Claude Haiku 4.5), GitHub API
```

Only Caddy publishes ports. Redis, Chroma, the backend and the worker can only be reached on the compose network.

## Files

| File | Runs on | What it does |
|---|---|---|
| `docker-compose.prod.yml` | server | caddy, frontend, backend, worker, redis, chromadb; memory limits, named volumes, `restart: unless-stopped` |
| `Caddyfile` | server | domain → frontend; `/api`, `/health`, `/mcp`, `/docs`, `/openapi.json` → backend |
| `.env.prod.example` | — | template for `deploy/.env.prod` (secrets, filled on the server only, gitignored) |
| `setup-server.sh` | server, once | Docker (enabled at boot), 4 GB swap, ufw 22/80/443, clone the repo, keep-alive cron |
| `server-deploy.sh` | server | validate the Caddyfile, build images, `compose up -d`, wait for health |
| `deploy.ps1` / `deploy.sh` | your laptop | ssh → `git pull` → `server-deploy.sh` → external health check |
| `supabase-keepalive.sh` | server, cron | daily query to Supabase so a free-tier project isn't paused |

## Memory budget (4 GB RAM + 4 GB swap)

| Service | Limit (RAM / RAM+swap) | Measured |
|---|---|---|
| worker | 2.5 GB / 4 GB | review peak ~2.3 GiB (torch + MiniLM), analyze peak ~1.4 GiB |
| backend | 1.5 GB / 2.5 GB | idle ~200 MiB; chat adds the Jina model (~1 GiB) for code search |
| chromadb | 768 MB / 1.25 GB | |
| redis | 256 MB (maxmemory 200 MB, noeviction for RQ) | |
| caddy / frontend | 128 MB / 64 MB | |

The measurements come from `evals/results/ops_measurements.json` (minikube, single runs). The limits add up to more than 4 GB on purpose. A limit is a ceiling, not a reservation, and the heavy peaks don't overlap because the single RQ worker runs one job at a time. Swap covers the rest. `MAX_EMBED_TOKENS=1024` is set in the compose file.

## Abuse protection

The backend enforces per-user sliding 1-hour limits in Redis (`backend/src/core/rate_limit.py`):

| Action | Endpoints | Default per user | Default global per day |
|---|---|---|---|
| review | `POST /api/review`, `POST /api/reviews` | 5 / hour | 300 |
| chat | `POST /api/chat` | 30 / hour | 1000 |
| analyze | `POST /api/analyze-repo`, `POST /api/analyze-jobs` | 5 / hour | 100 |

- **Over the limit:** the API returns HTTP 429 with a `Retry-After` header. The UI shows the server's message, for example *"You've reached the demo limit of 5 reviews per hour. Try again in 12 minutes."*
- **Not counted:** invalid requests (400/404), and re-opening an analysis that is already running.
- **Global daily cap:** guests are Supabase anonymous sign-ins, so a determined caller can create new user ids. The global cap limits total spend no matter how many ids there are.
- **Configuration:** all limits are env vars in `.env.prod`. Put your own user id in `RATE_LIMIT_EXEMPT_USERS`.
- **If Redis is down:** requests are allowed and a warning is logged.

Also set a monthly **spend limit in the Anthropic Console** (Settings → Limits). That's the hard backstop.

---

## First-time setup

### 0. Before touching the server

1. **Commit and push** this `deploy/` folder and the code changes. The server clones from GitHub, not from your laptop:
   ```powershell
   git add .gitattributes .gitignore deploy backend tests frontend
   git commit -m "deploy: single-VM Azure stack (Caddy + compose), per-user rate limits"
   git push origin main
   ```
   If the repo is private, add a read-only deploy key on the VM, or clone with a token, before step 2.

2. **Azure NSG.** In the Portal, open the VM → Networking → Inbound port rules and allow **TCP 80** and **TCP 443** from Any, next to 22. Caddy needs both to get the certificate (HTTP-01 / TLS-ALPN challenge).

3. **DNS label.** The public IP's DNS name label must be `personacr` (VM → Overview → DNS name). With a dynamic IP, the address can change after each deallocate/start, but the `*.cloudapp.azure.com` name follows it automatically. If you want a fixed address, make the IP **Static** (Public IP → Configuration).

4. **Auto-start / auto-shutdown.** Auto-shutdown is under VM → Operations → Auto-shutdown. Auto-start needs Start/Stop VMs v2, an Automation runbook or a Logic App. Nothing in this repo depends on which one you use. Docker starts at boot and every container has `restart: unless-stopped`.

### 1. Supabase (Dashboard → your project)

| Where | Setting |
|---|---|
| **Authentication → URL Configuration → Site URL** | `https://personacr.northcentralus.cloudapp.azure.com` |
| **Authentication → URL Configuration → Redirect URLs** | add `https://personacr.northcentralus.cloudapp.azure.com/login` (keep `http://localhost:5173/login` for local dev) |
| Authentication → Sign In / Providers → GitHub | unchanged. The GitHub OAuth App's callback stays `https://<project>.supabase.co/auth/v1/callback`. You can also set the OAuth App's *Homepage URL* to the new domain. |
| Authentication → Sign In / Providers → **Allow anonymous sign-ins** | on (guest mode) |
| Authentication → Rate Limits → anonymous sign-ins | keep the per-IP limit low (e.g. 30/hour) so guests can't mint ids freely |
| Project Settings → API | copy **Project URL**, **anon public** key and **service_role** key for `.env.prod` |

The frontend sends users back to `${window.location.origin}/login` after GitHub login (`frontend/src/lib/supabase.ts`). That's why `/login` must be in the Redirect URLs.

### 2. Prepare the server (once)

```bash
ssh -i ~/.ssh/azure_personacr azureuser@personacr.northcentralus.cloudapp.azure.com

curl -fsSL https://raw.githubusercontent.com/vaishnavi1064/PersonaCR/main/deploy/setup-server.sh -o setup-server.sh
bash setup-server.sh
exit          # log out so the docker group applies
```

`setup-server.sh` is idempotent. It does the following:

- Installs Docker Engine and the compose plugin from Docker's apt repo, with `systemctl enable docker containerd` and container log rotation (10 MB × 3).
- Creates `/swapfile` (4 GB, in `/etc/fstab`) and sets `vm.swappiness=10` and `vm.overcommit_memory=1`.
- Configures ufw: deny incoming, allow 22, 80 and 443.
- Clones the repo to `~/PersonaCR`.
- Installs `/etc/cron.d/personacr-keepalive`. It runs daily at 18:00 UTC (11:00 PDT / 10:00 PST, inside the uptime window) and 5 minutes after every boot.

### 3. Secrets (on the server)

```bash
ssh -i ~/.ssh/azure_personacr azureuser@personacr.northcentralus.cloudapp.azure.com
cd ~/PersonaCR
cp deploy/.env.prod.example deploy/.env.prod
nano deploy/.env.prod       # SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
                            # ANTHROPIC_API_KEY, GITHUB_TOKEN, RATE_LIMIT_EXEMPT_USERS
chmod 600 deploy/.env.prod
```

`deploy/.env.prod` is gitignored and lives only on the server. Every variable is documented in `.env.prod.example`. `LLM_MODEL=claude-haiku-4-5-20251001` is the demo default, chosen to keep costs down.

**About `GITHUB_TOKEN`:** without it, every visitor shares GitHub's unauthenticated limit of 60 requests/hour for the VM's IP. A fine-grained token with *Public repositories (read-only)* is enough.

### 4. First deploy (on the server)

```bash
bash ~/PersonaCR/deploy/server-deploy.sh
```

The first run takes 10–20 minutes, mostly building the backend image (CPU-only torch, ~2 GB). The script stops with logs if the backend isn't healthy after 5 minutes or HTTPS doesn't answer after 2.

The first analyze and the first review then download the embedding models (~0.7 GB) into the `model_cache` volume, so expect them to be slower. Later runs reuse the cache.

### 5. Verify

From your laptop:

```powershell
curl.exe -fsS https://personacr.northcentralus.cloudapp.azure.com/health
# {"status":"ok","service":"personacr-backend","version":"2.0.0"}
```

In the browser:

1. Open https://personacr.northcentralus.cloudapp.azure.com.
2. Sign in with GitHub. You should land back on `/login` and then the app.
3. Try guest mode.
4. Import a repo and run a review.
5. Run 6 reviews within an hour as a non-exempt user. The 6th shows the limit message.

### 6. Check that it survives a reboot (once)

```bash
ssh -i ~/.ssh/azure_personacr azureuser@personacr.northcentralus.cloudapp.azure.com 'sudo reboot'
# wait ~2 minutes
ssh -i ~/.ssh/azure_personacr azureuser@personacr.northcentralus.cloudapp.azure.com \
  'cd ~/PersonaCR && docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod ps'
```

After a boot, all containers start at the same time. Compose's `depends_on` order isn't applied on a daemon restart, so a container like the worker or nginx may restart once or twice until Redis and the backend are up. That's expected.

---

## Redeploy after new commits

1. Push to `main`.
2. From the repo root on your Windows laptop:

```powershell
.\deploy\deploy.ps1
```

or from Git Bash:

```bash
bash deploy/deploy.sh
```

Both do the same thing:

1. ssh in.
2. `git pull --ff-only origin main`.
3. Run `deploy/server-deploy.sh`: validate the Caddyfile → build images → `up -d` → restart Caddy if the Caddyfile changed → wait for backend health → check HTTPS → prune old images.
4. Check `https://<domain>/health` from your laptop.

Options: `.\deploy\deploy.ps1 -Branch my-branch`, or `BRANCH=my-branch bash deploy/deploy.sh`.

If you changed only `.env.prod` (on the server), no rebuild is needed:

```bash
cd ~/PersonaCR && docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d
```

**Exception:** `SUPABASE_URL` and `SUPABASE_ANON_KEY` are baked into the frontend bundle at build time. After changing them, run `bash deploy/server-deploy.sh`.

**Rollback:** on the server, `cd ~/PersonaCR && git checkout <good-sha> && bash deploy/server-deploy.sh`. Then `git checkout main` before the next normal deploy.

---

## Operations (on the server)

```bash
cd ~/PersonaCR
alias dc='docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod'

dc ps                          # status + health
dc logs -f --tail=100 backend  # or worker / caddy / frontend / redis / chromadb
docker stats --no-stream       # memory per container
free -h; df -h /               # RAM/swap, disk
dc restart worker              # restart one service
journalctl -t personacr-keepalive --since -3d   # keep-alive results
bash deploy/supabase-keepalive.sh               # run the keep-alive by hand
sudo ufw status
```

To check whether a container was OOM-killed: `docker inspect -f '{{.State.OOMKilled}}' $(dc ps -q worker)`. A job killed mid-run reads as failed after `JOB_STALE_SECONDS`, and the user can retry it.

Data lives in named volumes (`personacr_redis_data`, `personacr_chroma_data`, `personacr_caddy_data`, `personacr_model_cache`) and survives restarts, reboots and redeploys. `dc down` keeps them. Only `dc down -v` deletes them, and that throws away the TLS certificate, the embeddings and the job history.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `server-deploy.sh` stops at "https://…/health not reachable", Caddy logs show ACME errors | NSG doesn't allow 80/443, or the DNS label doesn't point at this VM. Run `nslookup personacr.northcentralus.cloudapp.azure.com`. |
| Too many failed certificate attempts | Let's Encrypt rate limit. Don't delete `caddy_data`; wait an hour. |
| 502 right after a deploy or boot | backend still starting (up to ~60 s). Check `dc ps`. |
| Login redirects to localhost or errors with "redirect URL not allowed" | Supabase Site URL / Redirect URLs (step 1) |
| UI says "Could not reach the PersonaCR server" | backend down: `dc logs backend` |
| "Sign-in can't be verified right now" (503) | backend can't reach the Supabase JWKS. Check `SUPABASE_URL`. |
| Analyses fail with GitHub 403 rate limit | set `GITHUB_TOKEN` |
| Reviews say the queue is offline (503) | `dc logs worker redis` |
