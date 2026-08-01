variable "kubeconfig_path" {
  description = "Path to kubeconfig (local minikube). Default: ~/.kube/config"
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "kubectl context name — must be the local minikube context, not a cloud cluster"
  type        = string
  default     = "minikube"
}

variable "namespace" {
  description = "Kubernetes namespace for PersonaCR local demo"
  type        = string
  default     = "personacr"
}

variable "redis_url" {
  description = "In-cluster Redis URL for the backend"
  type        = string
  default     = "redis://redis:6379/0"
}

variable "metrics_enabled" {
  description = "PERSONACR_METRICS_ENABLED value"
  type        = string
  default     = "1"
}
