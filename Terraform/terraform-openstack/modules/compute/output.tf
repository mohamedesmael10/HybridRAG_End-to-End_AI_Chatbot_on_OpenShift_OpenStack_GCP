output "ids" {
description = "IDs of the created instances"
value = [for i in openstack_compute_instance_v2.vm : i.id]
}


output "access_ips" {
description = "IPv4 access IPs (may be empty if none assigned)"
value = [for i in openstack_compute_instance_v2.vm : i.access_ip_v4]
}


output "full_instances" {
description = "Raw instance objects (for debugging)"
value = openstack_compute_instance_v2.vm
}