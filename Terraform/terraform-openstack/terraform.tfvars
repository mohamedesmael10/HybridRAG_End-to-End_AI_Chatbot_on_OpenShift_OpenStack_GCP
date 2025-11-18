# Replace the values below. Keep password secret or use environment / CI variables.

auth_url    = "https://192.168.254.134:5000/v3"
username    = "admin"
password = "m2i5MTW4jkoSgleZDj5WFWn7fXSWClB7"   # <-- DO NOT commit. Prefer CI variables.
project     = "admin"
domain      = "default"
region      = "microstack"

# If your MicroStack uses a self-signed cert, specify the CA cert path:
# cacert = "/var/snap/microstack/common/etc/ssl/certs/cacert.pem"

network_name = "default"
create_network = true
cidr = "10.10.0.0/24"
dns_nameservers = ["8.8.8.8"]

key_name = "esmael"
public_key_path = "/home/openstack/Downloads/esmael.pub"

image_name = "ubuntu-22.04-iso"
flavor_name = "m1.tiny"
instance_name = "esmael-vm"
instance_count = 1
cacert = "/var/snap/microstack/common/etc/ssl/certs/cacert.pem"
