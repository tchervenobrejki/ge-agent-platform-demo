# Model Armor template used by notebooks/08_model_armor.ipynb
# (sanitizeUserPrompt / sanitizeModelResponse). It can also be attached inline
# to Agent Gateway. Regional: data-plane calls go to
# modelarmor.<region>.rep.googleapis.com.
resource "google_model_armor_template" "growth_risk_guard" {
  location    = var.region
  template_id = "growth-risk-guard"

  depends_on = [google_project_service.modelarmor]

  filter_config {
    # Prompt injection / jailbreak attempts ("ignore all previous instructions").
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "MEDIUM_AND_ABOVE"
    }

    # Known-malicious URLs in prompts or responses.
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }

    # Sensitive data (credit card numbers, SSNs, ...), basic SDP inspection.
    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }

    # Responsible-AI categories.
    rai_settings {
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "HARASSMENT"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "SEXUALLY_EXPLICIT"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "DANGEROUS"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
    }
  }

  template_metadata {
    # Write each sanitize verdict to Cloud Logging.
    log_sanitize_operations = true
    log_template_operations = true
  }
}

output "model_armor_template" {
  value = google_model_armor_template.growth_risk_guard.id
}
