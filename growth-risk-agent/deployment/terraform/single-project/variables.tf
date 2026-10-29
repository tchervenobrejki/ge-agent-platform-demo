# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_name" {
  type        = string
  description = "Project name used as a base for resource naming"
  default     = "growth-risk-agent"
}

variable "project_id" {
  type        = string
  description = "Google Cloud Project ID for resource deployment."
}

variable "region" {
  type        = string
  description = "Google Cloud region for resource deployment."
  default     = "europe-west3"
}

variable "model_location" {
  type        = string
  description = "Region for Gemini calls when it differs from the engine's region (gemini-3.5-flash is not offered in every region). Defaults to var.region."
  default     = null
}

variable "telemetry_logs_filter" {
  type        = string
  description = "Log Sink filter for capturing telemetry data. Captures logs with the `traceloop.association.properties.log_type` attribute set to `tracing`."
  default     = "labels.service_name=\"growth-risk-agent\" labels.type=\"agent_telemetry\""
}

variable "app_sa_roles" {
  description = "List of roles to assign to the application service account"
  type        = list(string)
  default = [

    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/bigquery.dataOwner",
    "roles/bigquery.jobUser",
  ]
}

variable "agent_framework" {
  description = "Framework label on the Agent Runtime deployment. The Google Cloud console reads it to pick a playground; override it when the container is not an ADK app."
  type        = string
  default     = "google-adk"
}

variable "agent_identity_roles" {
  description = "List of roles to assign to the agent's Agent Identity principal. Keep the first six in sync with AGENT_IDENTITY_ROLES in agents-cli, which `agents-cli deploy` grants."
  type        = list(string)
  default = [
    "roles/aiplatform.user",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/browser",
    "roles/cloudapiregistry.viewer",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
    "roles/bigquery.dataOwner",
    "roles/bigquery.jobUser",
  ]
}

# --- Resources created by setup/ and the services this agent calls ---

variable "bq_dataset" {
  description = "Existing BigQuery dataset holding campaign_daily, funnel_daily and support_tickets"
  type        = string
  default     = "demo_growth"
}

variable "policy_rag_corpus" {
  description = "Existing RAG Engine corpus with the policy documents"
  type        = string
}

variable "support_rag_corpus" {
  description = "Existing RAG Engine corpus with the support tickets and runbooks"
  type        = string
}

variable "remediation_mcp_url" {
  description = "MCP endpoint of the existing remediation-mcp-server Cloud Run service"
  type        = string
}

variable "mcp_caller_service_account" {
  description = "Service account the agent impersonates to mint Cloud Run ID tokens for the MCP server and the Compliance Agent"
  type        = string
}

variable "compliance_agent_url" {
  description = "A2A base URL of the compliance-agent Cloud Run service"
  type        = string
}
