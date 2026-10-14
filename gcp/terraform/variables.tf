# TrustPay SEA — GCP inputs.
# PDP note (UU 27/2022 + PP 33/2026): keep primary data in Jakarta
# (asia-southeast2). Use Singapore only as failover for MY/SG/TH traffic.

variable "project_id" {
  description = "GCP project ID (e.g. trustpay-sea-dev)"
  type        = string
}

variable "region" {
  description = "Primary region. Default Jakarta for PDP data residency."
  type        = string
  default     = "asia-southeast2"
}

variable "environment" {
  description = "dev | staging | prod"
  type        = string
  default     = "dev"
}

# --- Cloud SQL ---
variable "sql_tier" {
  description = "Cloud SQL machine tier. db-g1-small for dev, db-custom-2-4096+ for prod."
  type        = string
  default     = "db-g1-small"
}

variable "sql_disk_size_gb" {
  description = "Postgres data disk size in GB."
  type        = number
  default     = 20
}

# --- Memorystore Redis ---
variable "redis_memory_gb" {
  description = "Memorystore Redis size in GB (Basic tier, Redis 7)."
  type        = number
  default     = 1
}

# --- Networking ---
variable "vpc_connector_cidr" {
  description = "CIDR for the Serverless VPC connector (must be /28, unused)."
  type        = string
  default     = "10.8.0.0/28"
}

# --- App images (filled by CI after first docker push) ---
variable "api_image" {
  description = "Full API image ref, e.g. REGION-docker.pkg.dev/PROJECT/repo/api:TAG"
  type        = string
  default     = ""
}

variable "web_image" {
  description = "Full web image ref, e.g. REGION-docker.pkg.dev/PROJECT/repo/web:TAG"
  type        = string
  default     = ""
}
