module "argocd" {
  source = "../modules/argocd"

  chart         = "argo-cd"
  chart_version = var.argocd_chart_version
}
