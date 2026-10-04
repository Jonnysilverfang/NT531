resource "aws_vpc_peering_connection" "ab" {
  vpc_id      = aws_vpc.a.id
  peer_vpc_id = aws_vpc.b.id
  auto_accept = true

  requester {
    allow_remote_vpc_dns_resolution = false
  }

  accepter {
    allow_remote_vpc_dns_resolution = false
  }

  tags = {
    Name      = "nt531-peer-ab"
    ManagedBy = "Manual"
  }
}