module "user_cloud_run_sa" {
    source = "./modules/service_account_module"
    account_id = "user-cloud-run-sa"
    display_name = "User Cloud Run Service Account"
    project_id = var.project_id
    rules = [
        "roles/run.invoker",
        "roles/redis.viewer",
        "roles/aiplatform.user",
        "roles/artifactregistry.reader",
        "roles/compute.networkUser"
    ]
}

module "admin_bucket_sa" {
    source = "./modules/service_account_module"
    account_id = "admin-bucket-sa"
    display_name = "Admin Bucket Service Account"
    project_id = var.project_id
    rules = [
        "roles/run.invoker",
        "roles/pubsub.publisher",
        "roles/storage.objectCreator",
    ]
}

module "admin_cloud_run_sa" {
    source = "./modules/service_account_module"
    account_id = "admin-cloud-run-sa"
    display_name = "Admin Cloud Run Service Account"
    project_id = var.project_id
    rules = [
        "roles/run.invoker",
        "roles/pubsub.subscriber",
        "roles/pubsub.viewer",
        "roles/aiplatform.user",
        "roles/datastore.user",
        "roles/storage.objectViewer",
        "roles/artifactregistry.reader"
    ]
}

module "chunk_cloud_run_sa" {
    source = "./modules/service_account_module"
    account_id = "chunk-cloud-run-sa"
    display_name = "Chunk Cloud Run Service Account"
    project_id = var.project_id
    rules = [
        "roles/artifactregistry.reader",
        "roles/run.invoker",
    ]
}

module "subscription_sa" {
    source = "./modules/service_account_module"
    account_id = "subscription-sa"
    display_name = "Subscription Service Account"
    project_id = var.project_id
    rules = [
        "roles/run.invoker",
    ]
}

module "admin_frontend_sa" {
    source = "./modules/service_account_module"
    account_id = "user-cdn-bucket-sa"
    display_name = "User Frontend Service Account"
    project_id = var.project_id
    rules = [
        "roles/run.invoker",
        "roles/storage.objectViewer"
    ]
}

resource "google_service_account" "cloudbuild_service_account" {
  account_id   = "cloudbuild-sa"
  display_name = "Cloud Build Service Account"
  description  = "Service Account used by Cloud Build Trigger"
}

# Grant required roles
resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_project_iam_member" "cloudbuild_sa_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_project_iam_member" "cloudbuild_sa_artifact" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_storage_bucket_iam_member" "sa_bucket_writer" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_service_account_iam_member" "allow_build_service_to_impersonate" {
  service_account_id = google_service_account.cloudbuild_service_account.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

resource "google_storage_bucket_iam_member" "cloudbuild_logs_writer" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}


resource "google_storage_bucket_iam_member" "cloudbuild_sa_storage_object_admin" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"

  depends_on = [google_storage_bucket.cloudbuild_logs]
}

resource "google_storage_bucket_iam_member" "cloudbuild_sa_storage_admin" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"

  depends_on = [google_storage_bucket.cloudbuild_logs]
}
