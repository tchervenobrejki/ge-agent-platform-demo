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

locals {
  dummy_source_b64 = trimspace(file("${path.module}/../shared/dummy_source.b64"))
}

resource "google_vertex_ai_reasoning_engine" "app" {
  display_name = var.project_name
  description  = "Agent deployed via Terraform"
  region       = var.region
  project      = var.project_id

  spec {
    agent_framework = var.agent_framework
    service_account = ""
    identity_type   = "AGENT_IDENTITY"

    deployment_spec {
      min_instances         = 0
      max_instances         = 3
      container_concurrency = 4

      resource_limits = {
        cpu    = "2"
        memory = "4Gi"
      }

      env {
        name  = "LOGS_BUCKET_NAME"
        value = google_storage_bucket.logs_data_bucket.name
      }

      # GOOGLE_CLOUD_PROJECT is reserved by Agent Runtime (the platform injects
      # it) and rejected in deployment_spec.env; GOOGLE_CLOUD_LOCATION is allowed.
      env {
        name = "GOOGLE_CLOUD_LOCATION"
        # Regional, not "global": structured-output calls (triage, Compliance
        # Agent) took ~60s on the global endpoint vs ~6s in-region (Phase 6).
        # model_location covers engines in regions without gemini-3.5-flash.
        value = coalesce(var.model_location, var.region)
      }

      env {
        name  = "GOOGLE_GENAI_USE_ENTERPRISE"
        value = "True"
      }

      env {
        name  = "OTEL_SERVICE_NAME"
        value = var.project_name
      }

      # Prompt/response content capture, off by default. Go: set "true" to log
      # content to OTLP log events for the completions view. Python: content goes to
      # GCS via the completion hook, so NO_CONTENT.
      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
        value = "NO_CONTENT"
      }

      env {
        name  = "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"
        value = "false"
      }

      env {
        name  = "OTEL_SEMCONV_STABILITY_OPT_IN"
        value = "gen_ai_latest_experimental"
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT"
        value = "jsonl"
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK"
        value = "upload"
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH"
        value = "gs://${google_storage_bucket.logs_data_bucket.name}/completions"
      }

      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }

      # Resources created by setup/ and the services this agent calls. See variables.tf for the values.
      env {
        name  = "BQ_DATASET"
        value = var.bq_dataset
      }
      env {
        name  = "POLICY_RAG_CORPUS"
        value = var.policy_rag_corpus
      }
      env {
        name  = "SUPPORT_RAG_CORPUS"
        value = var.support_rag_corpus
      }
      env {
        name  = "REMEDIATION_MCP_URL"
        value = var.remediation_mcp_url
      }
      env {
        name  = "MCP_CALLER_SERVICE_ACCOUNT"
        value = var.mcp_caller_service_account
      }
      env {
        name  = "COMPLIANCE_AGENT_URL"
        value = var.compliance_agent_url
      }
      env {
        name  = "BQ_ANALYTICS_DATASET_ID"
        value = google_bigquery_dataset.telemetry_dataset.dataset_id
      }
      env {
        name  = "BQ_ANALYTICS_GCS_BUCKET"
        value = google_storage_bucket.logs_data_bucket.name
      }
      env {
        # The telemetry dataset's region, which differs from
        # GOOGLE_CLOUD_LOCATION when model_location is set.
        name  = "BQ_ANALYTICS_LOCATION"
        value = var.region
      }
      env {
        name = "BQ_ANALYTICS_CONNECTION_ID"
        # Format: {location}.{connection_id}
        value = "${var.region}.${google_bigquery_connection.genai_telemetry_connection.connection_id}"
      }
    }

    source_code_spec {
      inline_source {
        source_archive = local.dummy_source_b64
      }
      image_spec {}
    }
  }

  # Terraform creates the resource with a placeholder source build; CI/CD
  # overwrites the same source_code_spec with the real code. The deploy writes
  # source_code_spec, so the placeholder must use it too — a container_spec
  # placeholder would be left alongside it and Agent Runtime rejects the update.
  # Ignore the spec and deployment_spec so Terraform never reverts the deployed agent.
  # class_methods too: `agents-cli deploy` writes the method contract
  # (stream_query, async_stream_query, sessions...) that the console playground
  # and :streamQuery rely on; without this, re-applying Terraform deletes it.
  lifecycle {
    ignore_changes = [
      spec[0].container_spec,
      spec[0].source_code_spec,
      spec[0].deployment_spec,
      spec[0].class_methods,
    ]
  }

  # Make dependencies conditional to avoid errors.
  depends_on = [google_project_service.services]
}
