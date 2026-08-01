# PersonaCR on local minikube

**Local/dev demonstration of container orchestration — not a production, HA, or multi-node deployment.**

The app already runs fine via Docker Compose (Redis + Prometheus + Grafana) and local uvicorn/Vite. This folder shows the same services (plus backend/frontend images and a ChromaDB StatefulSet) orchestrated on a **local minikube** cluster (docker driver). Treat it as a portfolio / skill demo, not an SRE claim.

## What this deploys

| Workload | Kind | Notes |
|----------|------|--------|
| `backend` | Deployment + ClusterIP + PVC | FastAPI `:8000`, probes on `/health`, PVC at `backend/.chroma` |
| `frontend` | Deployment + **NodePort 30080** | nginx serves SPA + proxies `/api` → backend |
| `chromadb` | StatefulSet + PVC | Official image; **not wired into app code** (see below) |
| `redis` | Deployment + ClusterIP | Mirrors compose `redis:7-alpine` |
| `prometheus` | Deployment + ClusterIP | Scrapes `backend:8000/metrics` |
| `grafana` | Deployment + **NodePort 30301** | Local admin/admin + anonymous Viewer |

### Honesty notes

- **Compose vs this stack:** Root `docker-compose.yml` currently defines **Redis, Prometheus, Grafana only** (not backend/frontend/Chroma as compose services). Backend/frontend here are new images; Redis/Prom/Grafana images/ports mirror compose.
- **ChromaDB:** The app uses an **in-process** `chromadb.PersistentClient` under `backend/.chroma`. The backend PVC preserves those vectors across pod restarts. The `chromadb` StatefulSet demonstrates StatefulSet + PVC orchestration and is reserved for a possible future `HttpClient` wiring — **no app source was changed**.
- **Secrets:** Never commit `secret.yaml`. Copy the example template and fill locally.
- **Scale:** 1 replica each, small requests/limits, emptyDir for Redis/Prometheus TSDB. Not HA.

## Prerequisites

- minikube running (`minikube status`) with docker driver
- `kubectl` context = `minikube`
- Docker CLI available
- Real API keys for Groq + Supabase (for a useful backend)

## 1. Point Docker at minikube

Images must be visible inside the cluster. On **PowerShell**:

```powershell
minikube docker-env | Invoke-Expression
```

(Unix/macOS: `eval $(minikube docker-env)`)

Confirm: `docker info` should show the minikube VM/docker context.

## 2. Build images into minikube's Docker

From the **repository root**:

```powershell
docker build -t personacr-backend:latest ./backend

# Optional: bake Supabase client env into the Vite bundle
docker build -t personacr-frontend:latest ./frontend `
  --build-arg VITE_SUPABASE_URL="https://YOUR_PROJECT.supabase.co" `
  --build-arg VITE_SUPABASE_ANON_KEY="YOUR_ANON_KEY"
```

`VITE_API_URL` defaults to `.` (same-origin) so the frontend nginx proxy can reach the backend Service without CORS pain.

Alternative: `minikube image build -t personacr-backend:latest -f backend/Dockerfile backend`

## 3. Create the Secret (required before apply)

```powershell
cp k8s/secret.example.yaml k8s/secret.yaml
# Edit k8s/secret.yaml — set GROQ_API_KEY, SUPABASE_*, etc.
```

`k8s/secret.yaml` is gitignored. Do not commit it.

## 4. Apply manifests

Apply the Secret first (not in kustomize, so the repo stays secret-free), then the rest:

```powershell
kubectl apply -f k8s/secret.yaml
kubectl apply -k k8s/
```

Or apply in order without kustomize:

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/prometheus-configmap.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/chromadb.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml
```

## 5. Verify

```powershell
kubectl -n personacr get pods
kubectl -n personacr get svc
kubectl -n personacr logs deploy/backend --tail=50
```

Open the frontend (NodePort):

```powershell
minikube service frontend -n personacr
```

Or:

```powershell
minikube service list -n personacr
# Frontend NodePort 30080 → http://$(minikube ip):30080
```

Grafana (optional):

```powershell
minikube service grafana -n personacr
# NodePort 30301 — admin/admin (local demo only)
```

Backend health via port-forward:

```powershell
kubectl -n personacr port-forward svc/backend 8000:8000
# then: curl http://localhost:8000/health
```

## 6. Optional: Terraform (namespace + ConfigMap)

See [`../terraform/README.md`](../terraform/README.md). Terraform targets the **local minikube** kubeconfig context — not EKS/GKE/AKS.

Typical flow: `terraform apply` for namespace/ConfigMap, then `kubectl apply -k k8s/` for workloads (or expand Terraform later).

## Tear down

```powershell
kubectl delete -k k8s/
# or: kubectl delete namespace personacr
```

PVCs may linger depending on storage class reclaim policy:

```powershell
kubectl -n personacr get pvc
# after namespace delete, check: kubectl get pvc -A
```

Reset Docker env to the host daemon when done:

```powershell
minikube docker-env -u | Invoke-Expression
```

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `ImagePullBackOff` for `personacr-*` | Rebuild with `minikube docker-env` active; `imagePullPolicy: IfNotPresent` |
| Backend CrashLoop / OOM | Raise memory limit (models are heavy); check `kubectl describe pod` |
| Frontend loads but API fails | Confirm nginx → `backend:8000`; check backend Ready; rebuild frontend with Supabase build-args if auth needed |
| `secret.yaml` missing on apply | Copy from `secret.example.yaml` first |

## Out of scope / follow-ups

- Multi-node / production / HA / TLS ingress
- Wiring app code to Chroma `HttpClient` against the StatefulSet
- Cloud providers (EKS etc.)
- Committing real secrets
