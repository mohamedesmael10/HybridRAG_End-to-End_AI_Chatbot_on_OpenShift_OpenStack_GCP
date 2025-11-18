resource "openstack_compute_keypair_v2" "key" {
name = var.name
public_key = var.public_key != "" ? var.public_key : file(var.public_key_path)
}