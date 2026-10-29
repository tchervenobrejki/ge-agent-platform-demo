# Agent Registry entry for this Compliance Agent as an A2A agent
# (F30 in docs/design-decisions.md).
#
# Cloud Run agents are not auto-registered (Agent Runtime agents are, as
# "CUSTOM"/Non-A2A). The spec content is the agent card the service itself
# serves; the registry derives interfaces and skills from it, so `interfaces`
# must stay empty. The card is private (run.invoker only), so it is checked in
# rather than fetched at plan time. Refresh it after changing the agent's
# name, description or tools:
#   TOK=$(gcloud auth print-identity-token \
#     --impersonate-service-account=growth-risk-mcp-caller@YOUR_PROJECT_ID.iam.gserviceaccount.com \
#     --audiences=https://compliance-agent-YOUR_PROJECT_NUMBER.YOUR_REGION.run.app --include-email)
#   curl -s -H "Authorization: Bearer $TOK" \
#     https://compliance-agent-YOUR_PROJECT_NUMBER.YOUR_REGION.run.app/a2a/app/.well-known/agent-card.json \
#     | python3 -m json.tool --sort-keys \
#     | sed "s#https://compliance-agent-[0-9]*\.[a-z0-9-]*\.run\.app#\${service_url}#g" \
#     > compliance_agent_card.json
# The checked-in card holds a ${service_url} placeholder, filled in below with
# this project's deterministic Cloud Run URL.

locals {
  # The served card carries both A2A shapes (the scaffold keeps a 0.3
  # compatibility layer for older clients); Agent Registry rejects that as
  # "ambiguous Agent Card", so register the 1.0 shape only: drop the 0.3
  # top-level fields, whose data supportedInterfaces already carries.
  # The compat layer also appends a protocolVersion "0.3" entry to
  # supportedInterfaces with the same URL, which the registry rejects as a
  # duplicate interface URL -- keep the 1.0 entries only.
  a2a_v03_only_fields = ["url", "protocolVersion", "preferredTransport", "additionalInterfaces"]
  compliance_agent_card_served = jsondecode(templatefile("${path.module}/compliance_agent_card.json", {
    service_url = "https://${var.project_name}-${data.google_project.project.number}.${var.region}.run.app"
  }))
  compliance_agent_card_v1 = merge(
    {
      for key, value in local.compliance_agent_card_served :
      key => value if !contains(local.a2a_v03_only_fields, key)
    },
    {
      supportedInterfaces = [
        for interface in local.compliance_agent_card_served.supportedInterfaces :
        interface if interface.protocolVersion != "0.3"
      ]
    },
  )
}

resource "google_agent_registry_service" "compliance_agent" {
  provider     = google-beta
  project      = var.project_id
  location     = var.region
  service_id   = var.project_name
  display_name = "Compliance Agent"
  description  = "Checks proposed growth/risk remediation actions against campaign policy (A2A, Cloud Run)."

  agent_spec {
    type    = "A2A_AGENT_CARD"
    content = jsonencode(local.compliance_agent_card_v1)
  }

  depends_on = [google_cloud_run_v2_service.app]
}
