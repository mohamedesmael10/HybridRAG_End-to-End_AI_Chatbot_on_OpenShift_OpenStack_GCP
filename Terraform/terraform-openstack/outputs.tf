output "instance_ids" {
  description = "IDs of created instances"
  value       = module.compute.ids
}

output "instance_ips" {
  description = "IPv4 access IPs (from compute module)"
  value       = module.compute.access_ips
}

output "keypair_name" {
  description = "Name of the keypair created/used"
  value       = module.keypair.name
}

output "kubeconfig" {
  value     = local_file.kubeconfig.filename
}