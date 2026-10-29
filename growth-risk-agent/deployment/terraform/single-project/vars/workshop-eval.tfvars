# Optional evaluation copy of the orchestrator for the console's Agent
# Evaluation, which only reaches agents in europe-west1/europe-west4
# (docs/evaluation.md). Apply with -var-file=vars/workshop-eval.tfvars and
# separate state (TF_DATA_DIR=.terraform-workshop, backend prefix
# workshop-growth-risk-agent/europe-west1). Every other value comes from
# ../terraform.tfvars, which Terraform loads first.
project_name = "workshop-growth-risk-agent"
region       = "europe-west1"

# gemini-3.5-flash is offered in europe-west3 and global, not europe-west1/4.
model_location = "europe-west3"

telemetry_logs_filter = "labels.service_name=\"workshop-growth-risk-agent\" labels.type=\"agent_telemetry\""
