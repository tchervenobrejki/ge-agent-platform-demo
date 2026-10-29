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


resource "google_cloud_run_v2_service" "app" {
  name                = var.project_name
  location            = var.region
  project             = var.project_id
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels = {
    "created-by" = "agents-cli"
  }

  template {
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      # `agents-cli deploy` sets AGENT_VERSION from pyproject.toml's version;
      # declared here so re-applying Terraform doesn't remove it (zero drift).
      # Keep in sync with pyproject.toml.
      env {
        name  = "AGENT_VERSION"
        value = "0.1.0"
      }

      env {
        name  = "APP_URL"
        value = "https://${var.project_name}-${data.google_project.project.number}.${var.region}.run.app"
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name = "GOOGLE_CLOUD_LOCATION"
        # Regional, not "global": structured-output calls (triage, Compliance
        # Agent) took ~60s on the global endpoint vs ~6s in-region (Phase 6).
        value = var.region
      }

      env {
        name = "GOOGLE_GENAI_USE_ENTERPRISE"
        # Lowercase, as `agents-cli deploy` copies it from .env (no drift).
        value = "true"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }

      env {
        name  = "LOGS_BUCKET_NAME"
        value = google_storage_bucket.logs_data_bucket.name
      }

      env {
        name  = "OTEL_SERVICE_NAME"
        value = "compliance-agent"
      }

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
        name  = "BQ_ANALYTICS_DATASET_ID"
        value = google_bigquery_dataset.telemetry_dataset.dataset_id
      }
      env {
        name  = "BQ_ANALYTICS_GCS_BUCKET"
        value = google_storage_bucket.logs_data_bucket.name
      }
      env {
        name = "BQ_ANALYTICS_CONNECTION_ID"
        # Format: {location}.{connection_id}
        value = "${var.region}.${google_bigquery_connection.genai_telemetry_connection.connection_id}"
      }
    }

    service_account                  = google_service_account.app_sa.email
    max_instance_request_concurrency = 4

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    session_affinity = true
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  # This lifecycle block prevents Terraform from overwriting the container image when it's
  # updated by Cloud Run deployments outside of Terraform (e.g., via CI/CD pipelines)
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      # Written by `agents-cli deploy` (gcloud run deploy --source) on every
      # deploy; build metadata, not configuration.
      client,
      client_version,
      build_config,
    ]
  }

  # Make dependencies conditional to avoid errors.
  depends_on = [
    resource.google_project_service.services,
  ]
}
