provider "google" {
    #  credentials = file("/home/esmael/Downloads/rock-task-468906-n1-7263e54c7ecd.json") 
      project = var.project_id
      region = var.region
    }