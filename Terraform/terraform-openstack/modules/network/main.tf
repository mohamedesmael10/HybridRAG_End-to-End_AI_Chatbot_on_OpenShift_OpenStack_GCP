resource "openstack_networking_network_v2" "net" {
count = var.create ? 1 : 0
name = var.name
}


resource "openstack_networking_subnet_v2" "subnet" {
count = var.create ? 1 : 0
name = "${var.name}-subnet"
network_id = openstack_networking_network_v2.net[0].id
cidr = var.cidr
ip_version = 4
dns_nameservers = var.dns_nameservers
}


# If not creating, look up an existing network by name
data "openstack_networking_network_v2" "existing" {
count = var.create ? 0 : 1
name = var.name
}