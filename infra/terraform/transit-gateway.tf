locals {
  tgw_nodes = {
    a = { vpc_id = aws_vpc.a.id, subnet_id = aws_subnet.a.id }
    b = { vpc_id = aws_vpc.b.id, subnet_id = aws_subnet.b.id }
    c = { vpc_id = aws_vpc.extra["c"].id, subnet_id = aws_subnet.extra["c"].id }
    d = { vpc_id = aws_vpc.extra["d"].id, subnet_id = aws_subnet.extra["d"].id }
  }
}

resource "aws_ec2_transit_gateway" "experiment" {
  count                           = var.enable_transit_gateway ? 1 : 0
  description                     = "NT531 shared transit gateway for four-VPC full-mesh experiments"
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  dns_support                     = "enable"
  tags                            = { Name = "nt531-tgw" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "experiment" {
  for_each                                        = var.enable_transit_gateway ? local.tgw_nodes : {}
  transit_gateway_id                              = aws_ec2_transit_gateway.experiment[0].id
  vpc_id                                          = each.value.vpc_id
  subnet_ids                                      = [each.value.subnet_id]
  transit_gateway_default_route_table_association = true
  transit_gateway_default_route_table_propagation = true
  tags                                            = { Name = "nt531-tgw-${each.key}" }
}
