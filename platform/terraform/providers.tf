# Shared platform infrastructure for the growth-risk demo: the Model Armor
# template and, optionally, the console-evaluation bucket. The two agents keep their own agents-cli stacks.
terraform {
  required_version = ">= 1.11.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.28.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.28.0"
    }
  }
  backend "gcs" {
    bucket = "YOUR_PROJECT_ID-terraform-state" # set by setup/05_write_config.py
    prefix = "platform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
