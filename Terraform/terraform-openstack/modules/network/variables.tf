variable "name" {
type = string
description = "Network name to create or reference"
}


variable "create" {
type = bool
description = "If true, the module will create the network and subnet"
default = false
}


variable "cidr" {
type = string
description = "CIDR for the subnet when creating"
default = "10.10.0.0/24"
}


variable "dns_nameservers" {
type = list(string)
description = "DNS nameservers for the subnet"
default = ["8.8.8.8"]
}