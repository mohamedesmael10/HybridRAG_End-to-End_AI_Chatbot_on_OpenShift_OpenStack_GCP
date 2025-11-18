terraform {
  required_version = ">= 0.12.18"

  required_providers {
    openstack = "~> 1.40"
    vault     = "~> 2.19"
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}


# provider "openstack" {
#   user_name   = "admin"
#   tenant_name = "admin"
#   password    = "https://192.168.254.134:5000/v3"
#   auth_url    = "m2i5MTW4jkoSgleZDj5WFWn7fXSWClB7" 
#   region      = "RegionOne"
# }

