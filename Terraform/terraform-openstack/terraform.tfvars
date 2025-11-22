# Replace the values below. Keep password secret or use environment / CI variables.

auth_url    = "https://192.168.254.134:5000/v3"
username    = "admin"
project     = "admin"
domain      = "default"
region      = "microstack"

# If your MicroStack uses a self-signed cert, specify the CA cert path:
# cacert = "/var/snap/microstack/common/etc/ssl/certs/cacert.pem"

network_name = "my-vpc-esmael"
create_network = true
cidr = "10.10.0.0/24"
dns_nameservers = ["8.8.8.8"]

key_name = "esmael"
public_key_path = "/home/openstack/hybridrag_end-to-end_ai_chatbot_on_openshift_openstack_gcp/Terraform/terraform-openstack/keys/esmael.pub"
# public_key_path = ""

image_name = "ubuntu-22.04-cloud-mini"
flavor_name = "m1.tiny"
instance_name = "esmael-vm"
instance_count = 1
cacert = "/var/snap/microstack/common/etc/ssl/certs/cacert.pem"

vault_addr = "https://2fcd81755e89.ngrok-free.app"