# Artifact Registry Repository and Push Images
resource "google_artifact_registry_repository" "images_repo" {
  location      = var.region
  repository_id = "images-repo"
  description   = "Docker images for Cloud Run services"
  format        = "DOCKER"
}

# data "google_secret_manager_secret_version" "vault_token" {
#   project = var.project_id
#   secret  = "vault_secret"        
#   version = "latest"
# }

# provider "vault" {
#   address = "http://127.0.0.1:8200"
#   token   = data.google_secret_manager_secret_version.vault_token.secret_data
# }


# data "vault_kv_secret_v2" "git_credentials" {
#   mount = "secret"
#   name  = "git-credentials"
# }

data "google_secret_manager_secret_version" "GITLAB" {
  secret  = "GITLAB"
  project = var.project_id
}

# Vector DB / Matching Engine Index


data "google_project" "project" {
  project_id = var.project_id
}

resource "google_storage_bucket" "cloudbuild_logs" {
  name                        = "${var.project_id}-build-logs"
  location                    = "US"
  uniform_bucket_level_access = true
  force_destroy               = true 

  versioning { enabled = false }

  lifecycle_rule {
    action { type = "Delete" }
    condition { age = 30 }
  }

  labels = {
    environment = "build-logs"
    managed_by  = "terraform"
  }
}


resource "google_cloudbuild_trigger" "build_all_images" {
  name        = "build-rag-images"
  description = "Build and push Docker images on push to branch main"
  location    = "us-central1"
  project     = var.project_id

  repository_event_config {
    repository = "projects/rock-task-468906-n1/locations/us-central1/connections/mohamedesmael10/repositories/mohamedesmael10-HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP"

    push {
      branch = "main"
    }
  }

  filename        = "cloudbuild.yaml"
  service_account = google_service_account.cloudbuild_service_account.id

  substitutions = {
    _ARTIFACT_REG_HOST = "${var.region}-docker.pkg.dev"
    _REPO              = google_artifact_registry_repository.images_repo.repository_id
    _PROJECT_ID        = var.project_id
    _GITLAB_PROJ_ID    = var.gitlab_project_id
    _GITLAB_REF        = var.gitlab_ref
    _GITLAB_TRIGGER_TOKEN = data.google_secret_manager_secret_version.GITLAB.secret_data
  
  }
   depends_on = [
    google_artifact_registry_repository.images_repo,
    google_service_account.cloudbuild_service_account,
    google_storage_bucket.cloudbuild_logs
  ]
}

resource "null_resource" "run_cloudbuild_trigger_after_apply" {
  provisioner "local-exec" {
    command = <<EOT
set -e
echo "==> Triggering Cloud Build trigger id: ${google_cloudbuild_trigger.build_all_images.trigger_id}"
gcloud builds triggers run ${google_cloudbuild_trigger.build_all_images.trigger_id} \
  --branch="${var.pipeline_branch}" \
  --region="${var.cloudbuild_region}" \
  --project="${var.project_id}" \
  --substitutions=_REGION="${var.cloudbuild_region}"
echo "==> Cloud Build trigger requested."
EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [
    google_cloudbuild_trigger.build_all_images,
    google_artifact_registry_repository.images_repo,
    google_storage_bucket.cloudbuild_logs
  ]
}

resource "null_resource" "destroy_infra_when_bootstrap_destroyed" {
  triggers = {
    infra_dir = var.infra_dir
  }

  provisioner "local-exec" {
    when = destroy
    command = <<EOT
set -e
echo "==> bootstrap destroy detected — running 'terraform destroy' in ${self.triggers.infra_dir}"
cd ${self.triggers.infra_dir} || (echo "Infra dir ${self.triggers.infra_dir} not found" && exit 1)
terraform init -input=false
terraform destroy -auto-approve
echo "==> terraform-infra destroy finished."
EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [
    google_cloudbuild_trigger.build_all_images,
    google_storage_bucket.cloudbuild_logs
  ]
}
