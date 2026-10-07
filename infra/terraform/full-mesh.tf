# Preserve imported AB and existing CD addresses; add the four missing pairs.
locals {
  nodes = {
    a = { vpc_id = aws_vpc.a.id, cidr = aws_vpc.a.cidr_block, ip = aws_instance.a.private_ip, sg = aws_security_group.a.id, rt = aws_route_table.a.id }
    b = { vpc_id = aws_vpc.b.id, cidr = aws_vpc.b.cidr_block, ip = aws_instance.b.private_ip, sg = aws_security_group.b.id, rt = aws_route_table.b.id }
    c = { vpc_id = aws_vpc.extra["c"].id, cidr = local.extra_nodes.c.cidr, ip = local.extra_nodes.c.ip, sg = aws_security_group.extra["c"].id, rt = aws_route_table.extra["c"].id }
    d = { vpc_id = aws_vpc.extra["d"].id, cidr = local.extra_nodes.d.cidr, ip = local.extra_nodes.d.ip, sg = aws_security_group.extra["d"].id, rt = aws_route_table.extra["d"].id }
  }
  cross_pairs = { ac = ["a", "c"], ad = ["a", "d"], bc = ["b", "c"], bd = ["b", "d"] }
  cross_routes = merge([
    for pair, ends in local.cross_pairs : {
      "${ends[0]}_${ends[1]}" = { source = ends[0], target = ends[1], pair = pair }
      "${ends[1]}_${ends[0]}" = { source = ends[1], target = ends[0], pair = pair }
    }
  ]...)
  directed_pairs = merge([
    for source in keys(local.nodes) : {
      for target in keys(local.nodes) : "${source}_${target}" => { source = source, target = target } if source != target
    }
  ]...)
}

resource "aws_vpc_peering_connection" "cross" {
  for_each    = local.cross_pairs
  vpc_id      = local.nodes[each.value[0]].vpc_id
  peer_vpc_id = local.nodes[each.value[1]].vpc_id
  auto_accept = true
  requester { allow_remote_vpc_dns_resolution = false }
  accepter { allow_remote_vpc_dns_resolution = false }
  tags = { Name = "nt531-peer-${each.key}" }
}

resource "aws_route" "cross" {
  for_each                  = local.cross_routes
  route_table_id            = local.nodes[each.value.source].rt
  destination_cidr_block    = local.nodes[each.value.target].cidr
  vpc_peering_connection_id = var.routing_mode == "peering" ? aws_vpc_peering_connection.cross[each.value.pair].id : null
  transit_gateway_id        = var.routing_mode == "tgw" ? try(aws_ec2_transit_gateway.experiment[0].id, null) : null
  depends_on                = [aws_ec2_transit_gateway_vpc_attachment.experiment]
  lifecycle {
    precondition {
      condition     = var.routing_mode != "tgw" || var.enable_transit_gateway
      error_message = "Enable Transit Gateway before selecting tgw routing."
    }
  }
}

# ICMP for the eight new directions; AB/BA/CD/DC already have rules.
resource "aws_vpc_security_group_ingress_rule" "cross_icmp" {
  for_each          = local.cross_routes
  security_group_id = local.nodes[each.value.target].sg
  cidr_ipv4         = "${local.nodes[each.value.source].ip}/32"
  ip_protocol       = "icmp"
  from_port         = -1
  to_port           = -1
}

# One server process per port allows three independent senders to one receiver.
# Existing AB and CD rules already cover port 5201; extend those with 5202-5203.
resource "aws_vpc_security_group_ingress_rule" "mesh_tcp" {
  for_each          = local.directed_pairs
  security_group_id = local.nodes[each.value.target].sg
  cidr_ipv4         = "${local.nodes[each.value.source].ip}/32"
  ip_protocol       = "tcp"
  from_port         = contains(["a_b", "c_d"], each.key) ? 5202 : 5201
  to_port           = 5203
}
