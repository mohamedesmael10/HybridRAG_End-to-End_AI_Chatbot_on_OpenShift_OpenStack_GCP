# OpenStack auth (sensitive values should be supplied via environment or a protected terraform.tfvars)
variable "auth_url" {
  description = "OpenStack auth URL (Keystone), e.g. https://192.168.254.134:5000/v3"
  type        = string
  default     = ""
}

variable "username" {
  description = "OpenStack username (admin)"
  type        = string
  default     = ""
}

variable "password" {
  description = "OpenStack password (sensitive)"
  type        = string
  default     = ""
}

variable "project" {
  description = "OpenStack project/tenant (admin)"
  type        = string
  default     = "admin"
}

variable "domain" {
  description = "OpenStack domain"
  type        = string
  default     = "default"
}

variable "region" {
  description = "OpenStack region"
  type        = string
  default     = "RegionOne"
}

variable "cacert" {
  description = "Path to CA certificate file if using self-signed certs (optional)"
  type        = string
  default     = ""
}

# Infrastructure variables
variable "network_name" {
  description = "Network name to create or reference"
  type        = string
  default     = "default"
}

variable "create_network" {
  description = "If true the network module will create the network/subnet"
  type        = bool
  default     = false
}

variable "cidr" {
  description = "Subnet CIDR used when creating a network"
  type        = string
  default     = "10.10.0.0/24"
}

variable "dns_nameservers" {
  description = "DNS nameservers for the subnet"
  type        = list(string)
  default     = ["8.8.8.8"]
}

variable "key_name" {
  description = "Keypair name in OpenStack"
  type        = string
  default     = "esmael"
}

variable "public_key_path" {
  description = "Path to the public key file to upload if keypair does not exist"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "image_name" {
  description = "Image name to use for instances"
  type        = string
  default     = "ubuntu-22.04-iso"
}

variable "flavor_name" {
  description = "Flavor name to use"
  type        = string
  default     = "m1.tiny"
}

variable "instance_name" {
  description = "Base name for instances"
  type        = string
  default     = "ci-test-vm"
}

variable "instance_count" {
  description = "Number of instances to create"
  type        = number
  default     = 1
}

variable "vault_addr" {
  description = "Vault address (e.g. http://127.0.0.1:8200)"
  type        = string
  default     = "http://127.0.0.1:8200"
}

variable "vault_token" {
  description = "Vault root/token (sensitive) - prefer using env var or CI secret"
  type        = string
  default     = ""
}
