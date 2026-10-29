# Who may call this Compliance Agent.
#
# The service is private (no allUsers invoker). The growth-risk-agent
# orchestrator reaches it over A2A with an ID token minted by impersonating
# this service account (growth-risk-agent/app/tools/gcp_auth.py).

variable "invoker_service_account" {
  description = "Service account allowed to invoke the Compliance Agent"
  type        = string
}

resource "google_cloud_run_v2_service_iam_member" "orchestrator_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.invoker_service_account}"
}
