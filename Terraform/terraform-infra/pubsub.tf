resource "google_pubsub_topic" "bucket_events_topic" {
  name = "bucket-events-topic"
}


resource "google_pubsub_subscription" "event_sub" {
  name  = "event-subscription"
  topic = google_pubsub_topic.bucket_events_topic.name

  ack_deadline_seconds        = 60
  message_retention_duration = "604800s"

   retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "60s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlt_topic.id
    max_delivery_attempts = 5
  }

  depends_on = [
    google_pubsub_topic.bucket_events_topic,
    ]
}


resource "google_storage_notification" "bucket_uploads" {
  bucket         = google_storage_bucket.admin_files_bucket.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.bucket_events_topic.id

  event_types = [
    "OBJECT_FINALIZE"
  ]

  depends_on = [
    google_pubsub_topic.bucket_events_topic,
    google_storage_bucket.admin_files_bucket
    ]
}

resource "google_pubsub_topic" "dlt_topic" {
  name = "dlt-topic"
}

resource "google_pubsub_subscription" "dlt_sub" {
  name  = "dlt-subscription"
  topic = google_pubsub_topic.dlt_topic.name

  message_retention_duration = "604800s"

  ack_deadline_seconds = 180

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "60s"
  }
}