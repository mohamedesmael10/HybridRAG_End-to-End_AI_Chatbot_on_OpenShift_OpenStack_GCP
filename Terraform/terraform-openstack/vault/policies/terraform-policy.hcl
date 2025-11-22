# terraform-policy.hcl
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
path "secret/data/*" {
  capabilities = ["read","list"]
}

