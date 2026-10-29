# Grants on resources created by setup/ -- bindings only, the resources
# themselves stay outside this Terraform.

# The engine's Agent Identity impersonates the MCP caller SA to mint Cloud Run
# ID tokens for the remediation MCP server and the Compliance Agent
# (app/tools/gcp_auth.py). The caller SA already holds roles/run.invoker on
# remediation-mcp-server; compliance-agent's Terraform grants it there.
resource "google_service_account_iam_member" "agent_identity_mcp_caller_token_creator" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.mcp_caller_service_account}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "principal://${google_vertex_ai_reasoning_engine.app.spec[0].effective_identity}"
}

# BigQuery (demo_growth) and the RAG corpora need no extra grants: the
# scaffold's agent_identity_roles already give the identity project-wide
# roles/bigquery.dataOwner + jobUser and roles/aiplatform.user.
