# Network module
module "network" {
  source = "./modules/network"

  name            = var.network_name
  create          = var.create_network
  cidr            = var.cidr
  dns_nameservers = var.dns_nameservers
}

# Keypair module
module "keypair" {
  source          = "./modules/keypair"
  name            = var.key_name
  public_key      = ""                 
  public_key_path = var.public_key_path

  # Ensure keypair is created after network if needed
 
}

# Compute module
module "compute" {
  source = "./modules/compute"

  name           = var.instance_name
  image          = var.image_name
  flavor         = var.flavor_name
  network        = module.network.id
  key_name       = module.keypair.name
  instance_count = var.instance_count
  user_data      = file("cloud-init.yaml")

  # Ensure compute is created after network and keypair
  
}
# Vault secret for kubeconfig
data "vault_generic_secret" "k8s_config" {
  path = "kv/k8s-config"

  # Ensure Vault secret exists before reading
  depends_on = [module.compute]
}

# Write kubeconfig locally
resource "local_file" "kubeconfig" {
  content  = base64decode(data.vault_generic_secret.k8s_config.data["config"])
  filename = "kubeconfig"

  # Ensure file is written after Vault secret is read
  depends_on = [data.vault_generic_secret.k8s_config]
}
