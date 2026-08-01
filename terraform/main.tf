# IaC for PersonaCR local minikube demo.
# Manages namespace + ConfigMap. Workloads live in k8s/ YAML (kubectl apply -k)
# so this stays a small, honest local artifact — not a cloud platform module.

resource "kubernetes_namespace_v1" "personacr" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of" = "personacr"
      environment                 = "local-dev"
    }
  }
}

resource "kubernetes_config_map_v1" "personacr_config" {
  metadata {
    name      = "personacr-config"
    namespace = kubernetes_namespace_v1.personacr.metadata[0].name
    labels = {
      "app.kubernetes.io/part-of" = "personacr"
    }
  }

  data = {
    REDIS_URL                 = var.redis_url
    PERSONACR_METRICS_ENABLED = var.metrics_enabled
    BACKEND_URL               = "http://backend:8000"
    CHROMADB_URL              = "http://chromadb:8000"
    REDIS_HOST                = "redis"
    REDIS_PORT                = "6379"
  }
}

output "namespace" {
  value       = kubernetes_namespace_v1.personacr.metadata[0].name
  description = "Namespace managed by Terraform (local minikube)"
}

output "config_map_name" {
  value       = kubernetes_config_map_v1.personacr_config.metadata[0].name
  description = "ConfigMap managed by Terraform"
}
