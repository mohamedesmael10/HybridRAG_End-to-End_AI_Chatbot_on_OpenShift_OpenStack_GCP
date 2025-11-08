variable "project_id" {
  type        = string
  description = "Google Cloud project ID"
  default     = "end-to-end-rag-application"
}

variable "region" {
  type        = string
  description = "The GCP region (e.g. us-central1)"
  default     = "us-east1"
}

variable "admin_bucket_name" {
  type        = string
  description = "Admin backend bucket name"
}

variable "firestore_db_name" {
  type        = string
  description = "Firestore database name"
}

# variable "cloudbuild_branch" {
#   type        = string
#   description = "The Git branch that triggers Cloud Build"
#   default     = "main"
# }

# variable "git_repo_owner" {
#   type        = string
#   description = "The GitHub owner or organization"
# }

# variable "git_repo_name" {
#   type        = string
#   description = "The GitHub repository name"
# }

# variable "gitlab_project_id" {
#   type        = string
#   description = "The GitLab project ID for CI/CD integration"
# }

# variable "gitlab_ref" {
#   type        = string
#   description = "The GitLab reference (branch or tag name)"
#   default     = "main"
# }


variable "vault_address" {
  type        = string
  description = "Vault address (e.g. http://127.0.0.1:8200 or https://vault.example.com)"
  default     = "http://127.0.0.1:8200"
}

variable "artifact_registry_host" {
  description = "artifact registry host, e.g. us-central1-docker.pkg.dev"
  type = string
}

variable "repo" {
  description = "Artifact repository id (images-repo)"
  type = string
}

variable "chunk_image_tag" {
  description = "Image tag built by pipeline (SHORT_SHA)"
  type = string
}
