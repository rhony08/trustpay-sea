output "registry" {
  description = "Artifact Registry repo for api/web images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "sql_connection_name" {
  description = "Cloud SQL connection name (for Cloud Run --add-cloudsql-instances)"
  value       = google_sql_database_instance.postgres.connection_name
}

output "sql_private_ip" {
  description = "Cloud SQL private IP (used to build DATABASE_URL over VPC)"
  value       = google_sql_database_instance.postgres.private_ip_address
  sensitive   = true
}

output "redis_host" {
  description = "Memorystore Redis host (used to build REDIS_URL over VPC)"
  value       = google_redis_instance.cache.host
  sensitive   = true
}

output "evidence_bucket" {
  description = "GCS bucket for fraud-report evidence"
  value       = google_storage_bucket.evidence.name
}

output "api_service_account" {
  description = "Least-privilege runtime SA for the FastAPI Cloud Run service"
  value       = google_service_account.api.email
}

output "vpc_connector" {
  description = "Serverless VPC connector for Cloud Run private egress"
  value       = google_vpc_access_connector.main.id
}

output "secret_ids" {
  description = "Secret Manager secret IDs (fill via bootstrap-secrets.sh)"
  value       = [for s in google_secret_manager_secret.secrets : s.secret_id]
}
