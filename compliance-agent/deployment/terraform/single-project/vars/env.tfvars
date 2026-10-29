# Template: setup/05_write_config.py copies this to ../terraform.tfvars and
# fills in every YOUR_* value. Terraform loads terraform.tfvars automatically.

# Project name used for resource naming
project_name = "compliance-agent"

# Your Google Cloud project id
project_id = "YOUR_PROJECT_ID"

# The Google Cloud region you will use to deploy the infrastructure
region = "europe-west3"

# Service account the growth-risk-agent impersonates to call this service
invoker_service_account = "growth-risk-mcp-caller@YOUR_PROJECT_ID.iam.gserviceaccount.com"
