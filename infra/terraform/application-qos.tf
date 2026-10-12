variable "enable_application_qos" {
  description = "Allow only A->B HTTP gateway and B->C/D worker traffic for the application experiment."
  type        = bool
  default     = false
}

locals {
  application_links = {
    a_b = { source = "a", target = "b", port = 8080 }
    b_c = { source = "b", target = "c", port = 8081 }
    b_d = { source = "b", target = "d", port = 8081 }
  }
}

resource "aws_vpc_security_group_ingress_rule" "application_http" {
  for_each          = var.enable_application_qos ? local.application_links : {}
  security_group_id = local.nodes[each.value.target].sg
  description       = "NT531 application ${each.value.source} to ${each.value.target}"
  cidr_ipv4         = "${local.nodes[each.value.source].ip}/32"
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
}
