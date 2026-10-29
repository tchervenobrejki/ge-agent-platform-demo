# Template: setup/05_write_config.py copies this to ../terraform.tfvars and
# fills in every YOUR_* value. Terraform loads terraform.tfvars automatically.

# Project name used for resource naming
project_name = "growth-risk-agent"

# Your Google Cloud project id
project_id = "YOUR_PROJECT_ID"

# The Google Cloud region you will use to deploy the infrastructure
region = "europe-west3"

# Created in the setup steps (BigQuery dataset, RAG corpora, MCP server,
# caller service account, compliance agent).
policy_rag_corpus          = "projects/YOUR_PROJECT_NUMBER/locations/europe-west3/ragCorpora/YOUR_POLICY_CORPUS_ID"
support_rag_corpus         = "projects/YOUR_PROJECT_NUMBER/locations/europe-west3/ragCorpora/YOUR_SUPPORT_CORPUS_ID"
remediation_mcp_url        = "https://remediation-mcp-server-YOUR_PROJECT_NUMBER.europe-west3.run.app/mcp"
mcp_caller_service_account = "growth-risk-mcp-caller@YOUR_PROJECT_ID.iam.gserviceaccount.com"
compliance_agent_url       = "https://compliance-agent-YOUR_PROJECT_NUMBER.europe-west3.run.app/a2a/app"
