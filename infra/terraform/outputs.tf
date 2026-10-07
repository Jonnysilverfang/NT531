output "vpcs" {
  description = "IDs and address ranges of the four NT531 VPCs."
  value = merge({
    a = { id = aws_vpc.a.id, cidr = aws_vpc.a.cidr_block }
    b = { id = aws_vpc.b.id, cidr = aws_vpc.b.cidr_block }
  }, { for node, vpc in aws_vpc.extra : node => { id = vpc.id, cidr = vpc.cidr_block } })
}

output "instances" {
  description = "EC2 IDs and stable Elastic IPs for SSH after association; stopped instances remain unreachable."
  value = merge({
    a = {
      id                = aws_instance.a.id
      private_ip        = aws_instance.a.private_ip
      public_ip         = aws_eip.a.public_ip
      subnet_id         = aws_subnet.a.id
      security_group_id = aws_security_group.a.id
      key_name          = aws_instance.a.key_name
    }
    b = {
      id                = aws_instance.b.id
      private_ip        = aws_instance.b.private_ip
      public_ip         = aws_eip.b.public_ip
      subnet_id         = aws_subnet.b.id
      security_group_id = aws_security_group.b.id
      key_name          = aws_instance.b.key_name
    }
    }, { for node, instance in aws_instance.extra : node => {
      id                = instance.id
      private_ip        = instance.private_ip
      public_ip         = aws_eip.extra[node].public_ip
      subnet_id         = aws_subnet.extra[node].id
      security_group_id = aws_security_group.extra[node].id
      key_name          = instance.key_name
  } })
  depends_on = [aws_eip_association.a, aws_eip_association.b, aws_eip_association.extra]
}

output "routing" {
  description = "Route tables, all six Peering connections and selected experiment path."
  value = {
    route_table_a_id   = aws_route_table.a.id
    route_table_b_id   = aws_route_table.b.id
    peering_id         = aws_vpc_peering_connection.ab.id
    peering_cd_id      = aws_vpc_peering_connection.cd.id
    route_table_c_id   = aws_route_table.extra["c"].id
    route_table_d_id   = aws_route_table.extra["d"].id
    mode               = var.routing_mode
    transit_gateway_id = try(aws_ec2_transit_gateway.experiment[0].id, null)
    cross_peering_ids  = { for name, peer in aws_vpc_peering_connection.cross : name => peer.id }
  }
}
