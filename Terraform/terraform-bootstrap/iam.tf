

resource "google_service_account" "cloudbuild_service_account" {
  account_id   = "cloudbuild-sa"
  display_name = "Cloud Build Service Account"
  description  = "Service Account used by Cloud Build Trigger"
}

# Grant the Cloud Build service account the "Service Account User" role
resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

# Grant the Cloud Build service account access to Secret Manager
resource "google_project_iam_member" "secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
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


resource "google_storage_bucket_iam_member" "cloudbuild_service_agent_logs" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

  depends_on = [google_storage_bucket.cloudbuild_logs]
}

resource "google_storage_bucket_iam_member" "cloudbuild_service_agent_object_admin" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

  depends_on = [google_storage_bucket.cloudbuild_logs]
}


resource "google_storage_bucket_iam_member" "cloudbuild_sa_state_admin" {
  bucket = "terrraform-rag-app-state"   
  role   = "roles/storage.objectAdmin"  
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}


resource "google_storage_bucket_iam_member" "cloudbuild_sa_state_viewer" {
  bucket = "terrraform-rag-app-state"   
  role   = "roles/storage.objectViewer"  
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}



resource "google_storage_bucket_iam_member" "cloudbuild_sa_state_storage_admin" {
  bucket = "terrraform-rag-app-state"   
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"

  depends_on = [google_storage_bucket.cloudbuild_logs]
}


resource "google_storage_bucket_iam_member" "state_bucket_writer" {
  bucket = "terrraform-rag-app-state"   
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}
