# TrustPay SEA — GCP foundation (Terraform).
#
# Creates STATEFUL infra + IAM + secret shells. Cloud Run services themselves
# are deployed via gcp/cloudrun/*.yaml (see gcp/scripts/deploy.sh) to avoid
# the image chicken-and-egg on first apply.
#
# Layout mirrors docker-compose.yml:
#   postgres:16  -> Cloud SQL for PostgreSQL 16 (private IP)
#   redis:7      -> Memorystore for Redis 7 (Basic tier)
#   api:8000     -> Cloud Run (yaml) + api-runtime SA
#   web:3000     -> Cloud Run (yaml)
# Evidence uploads -> Cloud Storage bucket (uniform access + lifecycle).

locals {
  prefix = "trustpay-${var.environment}"
}

# ---------------------------------------------------------------- APIs ---
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",               # Cloud Run
    "sqladmin.googleapis.com",          # Cloud SQL
    "redis.googleapis.com",             # Memorystore
    "secretmanager.googleapis.com",     # Secret Manager
    "artifactregistry.googleapis.com",  # container images
    "cloudbuild.googleapis.com",        # CI builds
    "storage.googleapis.com",           # evidence bucket
    "vpcaccess.googleapis.com",         # Serverless VPC connector
    "compute.googleapis.com",           # VPC networking
    "servicenetworking.googleapis.com", # private services access (SQL)
    "monitoring.googleapis.com",        # Cloud Monitoring
    "logging.googleapis.com",           # Cloud Logging
    "cloudtasks.googleapis.com",        # async scoring tasks
    "cloudscheduler.googleapis.com",    # nightly recompute
    "pubsub.googleapis.com",            # report events
    "webrisk.googleapis.com",           # scam URL intel (commercial API)
    "recaptchaenterprise.googleapis.com", # Fraud Defense / App Check provider
    "translate.googleapis.com",         # ID/MS/TH/VI report normalization
    "vision.googleapis.com",            # evidence OCR / SafeSearch
    "bigquery.googleapis.com",          # fraud analytics dataset
  ])
  project = var.project_id
  service = each.value

  # Keep APIs enabled on destroy so re-apply is cheap.
  disable_on_destroy = false
}

# ------------------------------------------------------- Artifact Registry ---
resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "${local.prefix}-images"
  description   = "TrustPay SEA container images (api, web)"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------- Networking ---
resource "google_compute_network" "main" {
  project                 = var.project_id
  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = true
}

# Private services access for Cloud SQL private IP.
resource "google_compute_global_address" "sql_private" {
  project       = var.project_id
  name          = "${local.prefix}-sql-private-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "sql_private" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql_private.name]
}

# Serverless VPC connector: Cloud Run -> SQL/Redis over private IP.
resource "google_vpc_access_connector" "main" {
  project       = var.project_id
  name          = "${local.prefix}-conn"
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = var.vpc_connector_cidr

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------- Cloud SQL ---
resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "postgres" {
  project          = var.project_id
  name             = "${local.prefix}-pg16"
  region           = var.region
  database_version = "POSTGRES_16"

  settings {
    tier              = var.sql_tier
    edition           = "ENTERPRISE"
    disk_size         = var.sql_disk_size_gb
    disk_autoresize   = true
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"

    ip_configuration {
      ipv4_enabled    = false # private IP only (PDP:最小暴露)
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    insights_config {
      query_insights_enabled = true
    }
  }

  depends_on = [
    google_service_networking_connection.sql_private,
    google_project_service.apis,
  ]

  # Prod guard: never lose data on accidental tier change.
  deletion_protection = true
}

resource "google_sql_database" "app" {
  project  = var.project_id
  name     = "trustpay"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "app" {
  project  = var.project_id
  name     = "trustpay"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db.result
}

# ------------------------------------------------------------ Memorystore ---
resource "google_redis_instance" "cache" {
  project            = var.project_id
  name               = "${local.prefix}-redis"
  region             = var.region
  tier               = "BASIC"
  memory_size_gb     = var.redis_memory_gb
  redis_version      = "REDIS_7_0"
  authorized_network = google_compute_network.main.id
  transit_encryption_mode = "DISABLED" # enable SERVER_AUTHENTICATION in prod

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------- Evidence bucket ---
resource "google_storage_bucket" "evidence" {
  project                     = var.project_id
  name                        = "${var.project_id}-${local.prefix}-evidence"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = var.environment != "prod"

  versioning { enabled = true }

  # Cheap PII hygiene: auto-expire raw uploads; curated copies live in DB.
  lifecycle_rule {
    action    { type = "Delete" }
    condition { age = 90 }
  }

  cors {
    origin          = ["http://localhost:3000"]
    method          = ["GET", "PUT", "POST"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

# ------------------------------------------------------ Analytics dataset ---
resource "google_bigquery_dataset" "fraud" {
  project    = var.project_id
  dataset_id = replace("${local.prefix}_fraud", "-", "_")
  location   = var.region
  description = "TrustPay SEA fraud analytics (report events, score history)"
}

# --------------------------------------------------------- Service accounts ---
# Least-privilege runtime identity for the FastAPI Cloud Run service.
resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "${local.prefix}-api"
  display_name = "TrustPay SEA API runtime (${var.environment})"
}

resource "google_project_iam_member" "api_roles" {
  for_each = toset([
    "roles/cloudsql.client",        # Cloud SQL connect
    "roles/secretmanager.secretAccessor", # read secrets at boot
    "roles/storage.objectAdmin",    # evidence bucket R/W (scope to bucket below too)
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Tighten storage to just the evidence bucket (defense in depth).
resource "google_storage_bucket_iam_member" "api_evidence" {
  bucket = google_storage_bucket.evidence.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

# ---------------------------------------------------------- Secret shells ---
# Shells only — values are filled by gcp/scripts/bootstrap-secrets.sh
# (or CI) so no secret material ever lands in git / tfstate in cleartext.
resource "google_secret_manager_secret" "secrets" {
  for_each = toset([
    "database-url",     # postgresql+asyncpg://trustpay:PASS@PRIVATE_IP:5432/trustpay
    "redis-url",        # redis://REDIS_HOST:6379/0
    "jwt-private-pem",  # RS256 private key (prod: real key, never self-generated)
    "jwt-public-pem",   # RS256 public key
    "account-hmac-key", # KMS-keyed HMAC stand-in until Phase 7 KMS wiring
    "gemini-api-key",   # empty = mock-first (ADR-012)
    "factcheck-api-key",# empty = enrichment disabled
  ])
  project   = var.project_id
  secret_id = "${local.prefix}-${each.value}"

  replication { auto {} }
}

resource "google_secret_manager_secret_iam_member" "api_accessor" {
  for_each  = google_secret_manager_secret.secrets
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}
