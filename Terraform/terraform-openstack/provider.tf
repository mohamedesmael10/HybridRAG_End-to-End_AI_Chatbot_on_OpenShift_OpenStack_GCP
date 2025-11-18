# Provider configuration. You can either pass values via variables (terraform.tfvars) or set them
# as environment variables (recommended for passwords / CI).
#
# If you prefer environment variables, set:
# OS_AUTH_URL, OS_USERNAME, OS_PASSWORD, OS_PROJECT_NAME, OS_USER_DOMAIN_NAME, OS_PROJECT_DOMAIN_NAME, OS_REGION_NAME

#provider "openstack" {
#  # These variables are defined in variables.tf. They can be empty if you use env vars instead.
#  auth_url    = var.auth_url
#
#  username    = var.username
#  password    = var.password
#  tenant_name = var.project
#  domain_name = var.domain
#  region      = var.region
#  # Optional: cafile for TLS verification (useful for MicroStack with self-signed certs)
#  cacert = var.cacert != "" ? var.cacert : null
#}

# Vault provider — configure via variables or environment variables.
provider "vault" {
  address = var.vault_addr     # e.g. https://vault.example:8200 or http://127.0.0.1:8200
  token   = var.vault_token    # sensitive; prefer passing via env or CI variable
  # skip_tls_verify = true    # uncomment only for testing with self-signed certs
}


# Read the microstack secret stored under KV v2 at "secret/microstack"
# data "vault_kv_secret_v2" "microstack" {
#   mount = "secret"
#   name  = "microstack"
# }

# # OpenStack provider uses values read from Vault
# provider "openstack" {
#   auth_url    = data.vault_kv_secret_v2.microstack.data["OS_AUTH_URL"]
#   username    = data.vault_kv_secret_v2.microstack.data["OS_USERNAME"]
#   password    = data.vault_kv_secret_v2.microstack.data["OS_PASSWORD"]
#   tenant_name = data.vault_kv_secret_v2.microstack.data["OS_PROJECT_NAME"]
#   domain_name = data.vault_kv_secret_v2.microstack.data["OS_USER_DOMAIN_NAME"]
#   region      = var.region

#   # If you saved a CA path or PEM as OS_CACERT, pass it here (optional)
#   cacert = lookup(data.vault_kv_secret_v2.microstack.data, "OS_CACERT", null)
# }

# provider "openstack" {}

data "vault_generic_secret" "microstack" {
  path = "secret/microstack"
}

provider "openstack" {
  user_name        = data.vault_generic_secret.microstack.data["OS_USERNAME"]
  password         = data.vault_generic_secret.microstack.data["OS_PASSWORD"]
  tenant_name      = data.vault_generic_secret.microstack.data["OS_PROJECT_NAME"]
  user_domain_name = data.vault_generic_secret.microstack.data["OS_USER_DOMAIN_NAME"]
  auth_url         = data.vault_generic_secret.microstack.data["OS_AUTH_URL"]
  region           = var.region
  # cert = var.cacert
  insecure = true
}
