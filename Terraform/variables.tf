variable "project_id" {
       type = string
       description = "Google Cloud project ID"
       default = "end-to-end-rag-application"
    }

variable "region" {
       type = string
       description = "Current Region"
       default = "us-east1"
    }

variable "admin_bucket_name" {
       type = string
       description = "Current Region"
    }

variable "firestore_db_name" {
  description = "Firestore database name"
  type        = string
}

variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "region" {
  description = "The GCP region (e.g. us-central1)."
  type        = string
  default     = "us-central1"
}

variable "cloudbuild_branch" {
  description = "The Git branch that triggers Cloud Build."
  type        = string
  default     = "main"
}

variable "git_repo_owner" {
  description = "The GitHub owner or organization."
  type        = string
}

variable "git_repo_name" {
  description = "The GitHub repository name."
  type        = string
}

variable "gitlab_project_id" {
  description = "The GitLab project ID for CI/CD integration."
  type        = string
}

variable "gitlab_ref" {
  description = "The GitLab reference (branch or tag name)."
  type        = string
  default     = "main"
}

variable "vault_token" {
  description = "Vault token retrieved from GCP Secret Manager"
  type        = string
}

variable "vault_address" {
  description = "Vault address (e.g. http://127.0.0.1:8200 or https://vault.example.com)"
  type        = string
  default     = "http://127.0.0.1:8200"
}