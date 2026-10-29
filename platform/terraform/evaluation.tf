# Output bucket for Agent Evaluation experiments run in the console.
#
# Console evaluation runs only in europe-west1/europe-west4 and only reaches
# agents in its own region, so it evaluates a copy of the orchestrator in
# europe-west1 (docs/evaluation.md) and the bucket lives there too.

data "google_project" "this" {}

# Off by default: enable_console_eval = true in terraform.tfvars.

resource "google_storage_bucket" "eval" {
  count                       = var.enable_console_eval ? 1 : 0
  name                        = "${var.project_id}-eval"
  location                    = "europe-west1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# The evaluation service writes generated scenarios and per-item results here.
resource "google_storage_bucket_iam_member" "eval_service_agent" {
  count  = var.enable_console_eval ? 1 : 0
  bucket = google_storage_bucket.eval[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-vertex-eval.iam.gserviceaccount.com"
}

output "eval_bucket" {
  value = var.enable_console_eval ? google_storage_bucket.eval[0].url : null
}
