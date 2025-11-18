# Call the modules we prepared: network, keypair, compute.
# Adjust module input names if your module variables are different.

module "network" {
  source = "./modules/network"

  name            = var.network_name
  create          = var.create_network
  cidr            = var.cidr
  dns_nameservers = var.dns_nameservers
}

module "keypair" {
  source       = "./modules/keypair"
  name         = var.key_name
  public_key   = ""                 
  public_key_path = var.public_key_path
}

module "compute" {
  source = "./modules/compute"

  name       = var.instance_name
  image      = var.image_name
  flavor     = var.flavor_name
  network    = module.network.name
  key_name   = module.keypair.name
  instance_count = var.instance_count
}