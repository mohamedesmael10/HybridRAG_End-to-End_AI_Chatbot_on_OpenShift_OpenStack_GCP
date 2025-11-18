variable "name" {
type = string
description = "Keypair name"
}


variable "public_key" {
  type        = string
  description = "Public key contents"
  default     = ""
}


variable "public_key_path" {
type = string
description = "Path to public key file to upload (used if public_key is empty)"
default = "~/.ssh/id_rsa.pub"
}