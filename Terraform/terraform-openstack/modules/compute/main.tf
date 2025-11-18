resource "openstack_compute_instance_v2" "vm" {
  count = var.instance_count

  name       = var.instance_count > 1 ? "${var.name}-${count.index + 1}" : var.name
  image_name = var.image
  flavor_name = var.flavor
  key_pair   = var.key_name

  network {
    name = var.network
  }

  user_data = var.user_data
  metadata  = var.metadata

  lifecycle {
    create_before_destroy = true
  }
}
