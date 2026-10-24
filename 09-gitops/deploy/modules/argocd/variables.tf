variable "chart" {
  type = string
}

variable "chart_version" {
  type = string
}

variable "namespace" {
  type    = string
  default = "argocd"
}

variable "name" {
  type    = string
  default = "argocd"
}

variable "repository" {
  type    = string
  default = "https://argoproj.github.io/argo-helm"
}
