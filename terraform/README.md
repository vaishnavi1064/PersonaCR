# Terraform — PersonaCR on local minikube

**Targets the local minikube kubeconfig context only. Not EKS, GKE, AKS, or any cloud provider.**

This is a small IaC sample: **namespace + ConfigMap**. Workloads live in `k8s/` YAML applied with kubectl/kustomize. Local/dev demo — not production IaC.

## Prerequisites

- Terraform >= 1.5
- minikube running; `kubectl config current-context` → `minikube`
- kubeconfig at `~/.kube/config` (Windows: `$HOME\.kube\config`)

## Usage

```powershell
cd terraform
terraform init
terraform plan
terraform apply
```

Then apply workloads (after building images and creating `k8s/secret.yaml`):

```powershell
kubectl apply -f ../k8s/secret.yaml
kubectl apply -k ../k8s/
```

`kubectl apply -k` will also create the namespace/ConfigMap from YAML — that is fine for a local demo (same desired state). Use Terraform when you want an apply/plan audit trail for those two objects; use kubectl alone if you skip Terraform.

## Destroy

```powershell
terraform destroy
# and/or: kubectl delete namespace personacr
```

## Variables

| Name | Default | Purpose |
|------|---------|---------|
| `kubeconfig_path` | `~/.kube/config` | Local kubeconfig |
| `kubeconfig_context` | `minikube` | Must stay on minikube |
| `namespace` | `personacr` | Demo namespace |
| `redis_url` | `redis://redis:6379/0` | Backend Redis URL |
| `metrics_enabled` | `1` | Metrics toggle |

No cloud credentials. No real secrets in Terraform state by design — Secrets stay in gitignored `k8s/secret.yaml`.
