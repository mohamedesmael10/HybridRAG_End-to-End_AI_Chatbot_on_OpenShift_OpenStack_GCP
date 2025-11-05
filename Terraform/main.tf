# Artifact Registry Repository and Push Images
resource "google_artifact_registry_repository" "images_repo" {
  location      = var.region
  repository_id = "images-repo"
  description   = "Docker images for Cloud Run services"
  format        = "DOCKER"
}

data "google_secret_manager_secret_version" "vault_token" {
  project = var.project_id
  secret  = "vault_secret"        
  version = "latest"
}

provider "vault" {
  address = "http://127.0.0.1:8200"
  token   = data.google_secret_manager_secret_version.vault_token.secret_data
}


data "vault_kv_secret_v2" "git_credentials" {
  mount = "secret"
  name  = "git-credentials"
}

data "google_secret_manager_secret_version" "GITLAB" {
  secret  = "GITLAB"
  project = var.project_id
}

# Vector DB / Matching Engine Index
resource "google_vertex_ai_index" "rag_index" {
  display_name        = "rag_index_01"
  region              = var.region
  index_update_method = "BATCH_UPDATE"
  metadata {
    config {
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count = 1000
          leaf_nodes_to_search_percent = 10
        }
      }
      dimensions                  = 1536
      approximate_neighbors_count = 100
      shard_size                  = "SHARD_SIZE_SMALL"
    }
  }
}

resource "google_vertex_ai_index_endpoint" "rag_endpoint" {
  display_name = "rag-index-endpoint"
  region       = var.region
  depends_on = [ google_vertex_ai_index.rag_index ]
}

resource "google_vertex_ai_index_endpoint_deployed_index" "rag_deployed" {
  deployed_index_id = "rag_index_01"
  index_endpoint = google_vertex_ai_index_endpoint.rag_endpoint.id
  index          = google_vertex_ai_index.rag_index.id
  dedicated_resources {
  machine_spec {
    machine_type = "e2-standard-2"
  }
  min_replica_count = 1
  max_replica_count = 1
 }
}
#      sed -i 's|CHUNK_URL_PLACEHOLDER|${module.chunk_cloud_run.cloud_run_endpoint}|g' ./helm/user-backend/values.yaml
/* 
resource "null_resource" "update_user_backend_values" {
  provisioner "local-exec" {
    command = <<EOT
      sed -i 's|VECTOR_DB_ENDPOINT_PLACEHOLDER|https://${google_vertex_ai_index_endpoint.rag_endpoint.public_endpoint_domain_name}/v1/projects/${var.project_id}/locations/${var.region}/indexEndpoints/${google_vertex_ai_index_endpoint.rag_endpoint.name}:findNeighbors|g' ./helm/user-backend/values.yaml
      sed -i 's|DEPLOYED_INDEX_ID_PLACEHOLDER|${google_vertex_ai_index_endpoint_deployed_index.rag_deployed.deployed_index_id}|g' ./helm/user-backend/values.yaml
      sed -i 's|MEMORY_STORE_HOST_PLACEHOLDER|${google_redis_instance.user_memory_store.host}|g' ./helm/user-backend/values.yaml
      sed -i 's|MEMORY_STORE_PORT_PLACEHOLDER|${google_redis_instance.user_memory_store.port}|g' ./helm/user-backend/values.yaml
      sed -i 's|EMBEDDING_ENDPOINT_PLACEHOLDER|https://${var.region}-aiplatform.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/publishers/google/models/text-embedding-004:predict|g' ./helm/user-backend/values.yaml
      sed -i 's|PROJECT_ID_PLACEHOLDER|${var.project_id}|g' ./helm/user-backend/values.yaml
      sed -i 's|REGION_PLACEHOLDER|${var.region}|g' ./helm/user-backend/values.yaml
    EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [
  google_vertex_ai_index_endpoint_deployed_index.rag_deployed,
  google_redis_instance.user_memory_store
]

}

#       sed -i 's|CHUNK_URL_PLACEHOLDER|${module.chunk_cloud_run.cloud_run_endpoint}|g' ./helm/admin-backend/values.yaml

resource "null_resource" "update_admin_backend_values" {
  provisioner "local-exec" {
    command = <<EOT
      sed -i 's|VECTOR_DB_ENDPOINT_PLACEHOLDER|https://${google_vertex_ai_index_endpoint.rag_endpoint.public_endpoint_domain_name}/v1/projects/${var.project_id}/locations/${var.region}/indexEndpoints/${google_vertex_ai_index_endpoint.rag_endpoint.name}:upsertDatapoints|g' ./helm/admin-backend/values.yaml
      sed -i 's|DEPLOYED_INDEX_ID_PLACEHOLDER|${google_vertex_ai_index_endpoint_deployed_index.rag_deployed.deployed_index_id}|g' ./helm/admin-backend/values.yaml
      sed -i 's|MEMORY_STORE_HOST_PLACEHOLDER|${google_redis_instance.user_memory_store.host}|g' ./helm/admin-backend/values.yaml
      sed -i 's|MEMORY_STORE_PORT_PLACEHOLDER|${google_redis_instance.user_memory_store.port}|g' ./helm/admin-backend/values.yaml
      sed -i 's|EMBEDDING_ENDPOINT_PLACEHOLDER|https://${var.region}-aiplatform.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/publishers/google/models/text-embedding-004:predict|g' ./helm/admin-backend/values.yaml
      sed -i 's|PROJECT_ID_PLACEHOLDER|${var.project_id}|g' ./helm/admin-backend/values.yaml
      sed -i 's|REGION_PLACEHOLDER|${var.region}|g' ./helm/admin-backend/values.yaml
    EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [
  google_vertex_ai_index_endpoint_deployed_index.rag_deployed,
  google_redis_instance.user_memory_store
]

} */
/* 
resource "null_resource" "helm_deploy_user_backend" {
  provisioner "local-exec" {
    command = <<EOT
      helm upgrade --install user-backend ./helm/user-backend \
        --set image.repository="${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images_repo.repository_id}/user-backend" \
        --set image.tag="v1" \
        --namespace user --create-namespace
    EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [null_resource.update_user_backend_values]
}

resource "null_resource" "helm_deploy_admin_backend" {
  provisioner "local-exec" {
    command = <<EOT
      helm upgrade --install admin-backend ./helm/admin-backend \
        --set image.repository="${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images_repo.repository_id}/admin-backend" \
        --set image.tag="v1" \
        --namespace admin --create-namespace
    EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [null_resource.update_admin_backend_values]
}
 */

# resource "null_resource" "push_helm_updates_to_github" {
#   provisioner "local-exec" {
#     command = <<EOT
# set -euo pipefail
# echo "=== Committing and pushing Helm updates to GitHub ==="

# # Configure Git identity
# git config user.email "mohamed.2714104@gmail.com"
# git config user.name "${data.vault_kv_secret_v2.git_credentials.data["username"]}"

# # Commit Helm changes (if any)
# git add ../helm/ || true
# git commit -m "Auto-update Helm values.yaml via Terraform" || echo "No changes to commit"

# # Push using Vault GitHub token (in memory only)
# echo "Pushing changes securely via HTTPS..."
# git push "https://${data.vault_kv_secret_v2.git_credentials.data["username"]}:${data.vault_kv_secret_v2.git_credentials.data["token"]}@github.com/${var.git_repo_owner}/${var.git_repo_name}.git" main || echo "No changes to push"

# echo "=== Push completed ==="
# EOT
#     interpreter = ["bash", "-c"]
#   }

#   depends_on = [
#     null_resource.update_user_backend_values,
#     null_resource.update_admin_backend_values
#   ]
# }
data "google_project" "project" {
  project_id = var.project_id
}

resource "google_storage_bucket" "cloudbuild_logs" {
  name                        = "${var.project_id}-build-logs"
  location                    = "US"
  uniform_bucket_level_access = true

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
