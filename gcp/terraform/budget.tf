# TrustPay SEA — billing guardrails (closes 06 NG-8).
#
# A brigading flood or a Gemini retry storm bills real money. This budget trips
# email + Pub/Sub alerts at 50/90% of the monthly cap and at 100% forecast.
# Wire a Cloud Function / Cloud Run subscriber later to auto-stop the VM or
# minScale→0 (Pub/Sub message carries alertThresholdExceeded/forecastThresholdExceeded).

variable "billing_account_id" {
  description = "Billing account ID (e.g. 000000-000000-000000). Empty = skip budget."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly cap in USD. Demo single-VM ≈ $22 — default $50 headroom."
  type        = string
  default     = "50"
}

variable "budget_alert_email" {
  description = "Email for budget alerts. Empty = billing-account default recipients."
  type        = string
  default     = ""
}

resource "google_pubsub_topic" "budget" {
  count   = var.billing_account_id == "" ? 0 : 1
  project = var.project_id
  name    = "${local.prefix}-budget-alerts"
}

resource "google_billing_budget" "demo" {
  count           = var.billing_account_id == "" ? 0 : 1
  billing_account = var.billing_account_id
  display_name    = "${local.prefix} monthly cap"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = var.monthly_budget_usd
    }
  }

  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    pubsub_topic = google_pubsub_topic.budget[0].id
  }
}

data "google_project" "current" {
  project_id = var.project_id
}
