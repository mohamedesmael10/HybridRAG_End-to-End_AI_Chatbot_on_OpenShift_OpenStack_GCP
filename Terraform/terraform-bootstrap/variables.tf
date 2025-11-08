variable "project_id" {
  type        = string
  description = "Google Cloud project ID"
  default     = "end-to-end-rag-application"
}

variable "region" {
  type        = string
  description = "The GCP region (e.g. us-central1)"
  default     = "us-central1"
}


variable "cloudbuild_branch" {
  type        = string
  description = "The Git branch that triggers Cloud Build"
  default     = "main"
}

variable "git_repo_owner" {
  type        = string
  description = "The GitHub owner or organization"
}

variable "git_repo_name" {
  type        = string
  description = "The GitHub repository name"
}

variable "gitlab_project_id" {
  type        = string
  description = "The GitLab project ID for CI/CD integration"
}

variable "gitlab_ref" {
  type        = string
  description = "The GitLab reference (branch or tag name)"
  default     = "main"
}


variable "vault_address" {
  type        = string
  description = "Vault address (e.g. http://127.0.0.1:8200 or https://vault.example.com)"
  default     = "http://127.0.0.1:8200"
}

variable "infra_dir" {
  type    = string
  default = "../terraform-infra" 
  description = "Relative path to the terraform-infra directory that will be destroyed on bootstrap destroy."
}

variable "pipeline_branch" {
  type    = string
  default = "main"
}

variable "cloudbuild_region" {
  type    = string
  default = "us-central1"
}
