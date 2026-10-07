# Offline plan tests (Terraform >= 1.7). No AWS calls or real resources.
mock_provider "aws" {}

variables {
  ssh_admin_cidr         = "203.0.113.10/32"
  enable_transit_gateway = false
  routing_mode           = "peering"
}

run "full_mesh_peering" {
  command = plan
  assert {
    condition     = length(aws_vpc_peering_connection.cross) == 4 && length(aws_route.cross) == 8 && length(local.directed_pairs) == 12
    error_message = "Full mesh needs four new peers, eight new routes and twelve directed endpoint pairs."
  }
  assert {
    condition     = alltrue([for r in aws_route.cross : r.transit_gateway_id == null])
    error_message = "Cross routes must use Peering in peering mode."
  }
  assert {
    condition     = length(aws_instance.extra) == 2 && length(aws_eip.extra) == 2
    error_message = "C/D must each have an EC2 and EIP."
  }
  assert {
    condition     = length(aws_ec2_transit_gateway.experiment) == 0 && length(aws_ec2_transit_gateway_vpc_attachment.experiment) == 0
    error_message = "Default mode must not allocate paid TGW attachments."
  }
  assert {
    condition     = aws_route.a_to_b.transit_gateway_id == null && aws_route.b_to_a.transit_gateway_id == null && alltrue([for r in aws_route.extra_to_peer : r.transit_gateway_id == null])
    error_message = "Peering mode must not use TGW routes."
  }
  assert {
    condition     = aws_route.extra_to_peer["c"].destination_cidr_block == "10.40.0.0/16" && aws_route.extra_to_peer["d"].destination_cidr_block == "10.30.0.0/16"
    error_message = "C/D must have correct reciprocal destinations."
  }
}

run "full_mesh_tgw" {
  command = plan
  assert {
    condition     = alltrue([for r in aws_route.cross : r.vpc_peering_connection_id == null])
    error_message = "All cross routes must stop using Peering in TGW mode."
  }
  variables {
    enable_transit_gateway = true
    routing_mode           = "tgw"
  }
  assert {
    condition     = length(aws_ec2_transit_gateway.experiment) == 1 && length(aws_ec2_transit_gateway_vpc_attachment.experiment) == 4
    error_message = "TGW mode needs one shared TGW and four attachments."
  }
  assert {
    condition     = aws_route.a_to_b.vpc_peering_connection_id == null && aws_route.b_to_a.vpc_peering_connection_id == null && alltrue([for r in aws_route.extra_to_peer : r.vpc_peering_connection_id == null])
    error_message = "TGW mode must remove all four Peering route targets."
  }
}

run "reject_tgw_without_attachments" {
  command = plan
  variables {
    routing_mode = "tgw"
  }
  expect_failures = [aws_route.a_to_b, aws_route.b_to_a, aws_route.extra_to_peer, aws_route.cross]
}
