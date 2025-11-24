# output "cdn_bucket_sa_email" {
#   value = module.cdn_bucket_sa.service_account_email
# }

# output "user_cloud_run_sa_email" {
#   value = module.user_cloud_run_sa.service_account_email
# }

# output "admin_bucket_sa_email" {
#   value = module.admin_bucket_sa.service_account_email
# }

# output "admin_cloud_run_sa_email" {
#   value = module.admin_cloud_run_sa.service_account_email
# }

# output "chunk_cloud_run_endpoint" {
#   value = module.chunk_cloud_run.cloud_run_endpoint
# }

# output "user_url" {
#   value = module.user_cloud_run.cloud_run_endpoint
# }

# output "admin_url" {
#   value = module.admin_cloud_run.cloud_run_endpoint
# }

# output "user_frontend_url" {
#   value = module.user_frontend_cloud_run.cloud_run_endpoint
# }

# output "admin_frontend_url" {
#   value = module.admin_frontend_cloud_run.cloud_run_endpoint
# }

# output "index_endpoint_url" {
#   description = "The URL of the Vertex AI Endpoint for embeddings."
#   value       = google_vertex_ai_index_endpoint.rag_endpoint.id
# }

# output "redis_host" {
#   value = google_redis_instance.user_memory_store.host
# }

# output "redis_port" {
#   value = google_redis_instance.user_memory_store.port
# }

# output "index_endpoint" {
#   value = google_vertex_ai_index_endpoint.rag_endpoint.name
# }
# ---- corrected outputs ----

output "embedding_endpoint" {
  description = "Embedding API endpoint (Text embeddings predict)"
  value       = "https://${var.region}-aiplatform.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/publishers/google/models/text-embedding-004:predict"
}

output "chunk_url" {
  description = "URL of the chunk processing service (Cloud Run module output)"
  # use the module output (module must expose cloud_run_endpoint)
  value       = try(module.chunk_cloud_run.cloud_run_endpoint, "")
}

output "vector_db_endpoint_find_neighbors" {
  description = "Vertex AI MatchingEngine findNeighbors endpoint (public domain)"
  value       = "https://${google_vertex_ai_index_endpoint.rag_endpoint.public_endpoint_domain_name}/v1/projects/${var.project_id}/locations/${var.region}/indexEndpoints/${google_vertex_ai_index_endpoint.rag_endpoint.name}:findNeighbors"
}

output "vector_db_endpoint_upsert" {
  description = "Vertex AI MatchingEngine upsertDatapoints endpoint"
  value       = "https://${google_vertex_ai_index_endpoint.rag_endpoint.public_endpoint_domain_name}/v1/projects/${var.project_id}/locations/${var.region}/indexEndpoints/${google_vertex_ai_index_endpoint.rag_endpoint.name}:upsertDatapoints"
}

output "deployed_index_id" {
  description = "Deployed index ID"
  value       = google_vertex_ai_index_endpoint_deployed_index.rag_deployed.deployed_index_id
}

output "project_id" {
  description = "Project ID"
  value       = var.project_id
}

output "region" {
  description = "Region"
  value       = var.region
}

output "chunk_image_full" {
  value = "${var.artifact_registry_host}/${var.project_id}/${var.repo}/chunk-image:${var.chunk_image_tag}"
}

# Outputs for Pub/Sub topics
output "bucket_events_topic_name" {
  value = google_pubsub_topic.bucket_events_topic.name
}

output "bucket_events_topic_id" {
  value = google_pubsub_topic.bucket_events_topic.id
}

output "dlt_topic_name" {
  value = google_pubsub_topic.dlt_topic.name
}

output "dlt_topic_id" {
  value = google_pubsub_topic.dlt_topic.id
}

output "event_subscription_name" {
  value = google_pubsub_subscription.event_sub.name
}

output "event_subscription_path" {
  value = google_pubsub_subscription.event_sub.id
}

output "dlt_subscription_name" {
  value = google_pubsub_subscription.dlt_sub.name
}

output "dlt_subscription_path" {
  value = google_pubsub_subscription.dlt_sub.id
}
