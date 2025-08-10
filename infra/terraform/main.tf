terraform {
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.8.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.11.0"
    }
  }
}

provider "kubernetes" {
  # assumes your kubeconfig is at the default location
  config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

variable "namespace" {
  type    = string
  default = "default"
  description = "Kubernetes namespace to deploy into"
}

variable "release_name" {
  type        = string
  default     = "market-data-api"
  description = "Helm release name"
}

variable "image_repo" {
  type    = string
  default = "market-data-api-python"
  description = "Container image repository"
}

variable "image_tag" {
  type    = string
  default = "local"
  description = "Container image tag"
}

resource "helm_release" "service" {
  name       = var.release_name
  namespace  = var.namespace

  # point this at your generated chart directory
  chart      = "${path.module}/../../chart"
  version    = "0.1.0"        # chart version, bump as needed
  create_namespace = true

  values = [
    yamlencode({
      image = {
        repository = var.image_repo
        tag        = var.image_tag
      }
      service = {
        port = 50051
      }
    })
  ]
}
