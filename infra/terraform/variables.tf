variable "enable_transit_gateway" {
  description = "Create the shared TGW and four attachments. Billed while provisioned, even if EC2 is stopped."
  type        = bool
  default     = false
}

variable "routing_mode" {
  description = "Path for all 12 directed inter-VPC routes. TGW mode requires enable_transit_gateway=true."
  type        = string
  default     = "peering"
  validation {
    condition     = contains(["peering", "tgw"], var.routing_mode)
    error_message = "routing_mode must be peering or tgw."
  }
}

variable "ssh_admin_cidr" {
  description = "SSH source: one public IPv4 /32, or 0.0.0.0/0 for the requested roaming demo access."
  type        = string
  nullable    = false

  validation {
    condition     = can(cidrnetmask(var.ssh_admin_cidr)) && (endswith(var.ssh_admin_cidr, "/32") || var.ssh_admin_cidr == "0.0.0.0/0")
    error_message = "ssh_admin_cidr must be a valid IPv4 /32 or 0.0.0.0/0."
  }
}
