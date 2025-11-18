variable "name" {
type = string
description = "Base name for the instance(s)"
}


variable "image" {
type = string
description = "Image name to use"
}


variable "flavor" {
type = string
description = "Flavor name to use"
}


variable "network" {
type = string
description = "Network name to attach the instance to"
}


variable "key_name" {
type = string
description = "Keypair name existing in OpenStack"
}


variable "instance_count" {
  type    = number
  default = 1
  description = "Number of instances to create"
}


variable "user_data" {
type = string
default = ""
}


variable "metadata" {
type = map(string)
default = {}
}