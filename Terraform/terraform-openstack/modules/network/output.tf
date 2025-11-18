output "name" {
value = var.create ? openstack_networking_network_v2.net[0].name : data.openstack_networking_network_v2.existing[0].name
}


output "id" {
value = var.create ? openstack_networking_network_v2.net[0].id : data.openstack_networking_network_v2.existing[0].id
}