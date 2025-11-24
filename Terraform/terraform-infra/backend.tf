# terraform {
#   required_providers {
#     google = {
#       source  = "hashicorp/google"
#       version = "7.1.1"
#     }
#   }

#   backend "gcs" {
#     bucket      = "terrraform-rag-app-state"
#     prefix      = "dev"
#     credentials = "/home/esmael/Downloads/rock-task-468906-n1-7263e54c7ecd.json"  
#   }
  
# }

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
