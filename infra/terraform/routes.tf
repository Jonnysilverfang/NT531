resource "aws_route" "a_to_b" {
  route_table_id            = aws_route_table.a.id
  destination_cidr_block    = aws_vpc.b.cidr_block
  vpc_peering_connection_id = var.routing_mode == "peering" ? aws_vpc_peering_connection.ab.id : null
  transit_gateway_id        = var.routing_mode == "tgw" ? try(aws_ec2_transit_gateway.experiment[0].id, null) : null
  depends_on                = [aws_ec2_transit_gateway_vpc_attachment.experiment]
  lifecycle {
    precondition {
      condition     = var.routing_mode != "tgw" || var.enable_transit_gateway
      error_message = "Enable Transit Gateway before selecting tgw routing."
    }
  }
}

resource "aws_route" "b_to_a" {
  route_table_id            = aws_route_table.b.id
  destination_cidr_block    = aws_vpc.a.cidr_block
  vpc_peering_connection_id = var.routing_mode == "peering" ? aws_vpc_peering_connection.ab.id : null
  transit_gateway_id        = var.routing_mode == "tgw" ? try(aws_ec2_transit_gateway.experiment[0].id, null) : null
  depends_on                = [aws_ec2_transit_gateway_vpc_attachment.experiment]
  lifecycle {
    precondition {
      condition     = var.routing_mode != "tgw" || var.enable_transit_gateway
      error_message = "Enable Transit Gateway before selecting tgw routing."
    }
  }
}

resource "aws_route" "a_to_internet" {
  route_table_id         = aws_route_table.a.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.a.id
}

resource "aws_route" "b_to_internet" {
  route_table_id         = aws_route_table.b.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.b.id
}
