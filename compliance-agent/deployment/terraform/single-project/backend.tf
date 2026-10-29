# Remote state: a versioned, private GCS bucket created by
# setup/01_project.sh -- Terraform can't create its own backend. Each project
# keeps its own prefix.
terraform {
  backend "gcs" {
    bucket = "YOUR_PROJECT_ID-terraform-state" # set by setup/05_write_config.py
    prefix = "compliance-agent/single-project"
  }
}
