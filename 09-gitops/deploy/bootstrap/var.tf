variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "kube_context" {
  type    = string
  default = "minikube"
}

variable "argocd_chart_version" {
  type    = string
  default = "10.10.5"
}
