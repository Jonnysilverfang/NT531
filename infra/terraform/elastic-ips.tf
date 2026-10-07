# Stable management addresses. Benchmark traffic still uses private IPs.
# Allocated public IPv4 addresses are billed even while EC2 is stopped.
resource "aws_eip" "a" {
  domain = "vpc"
  tags   = { Name = "nt531-eip-a" }
}

resource "aws_eip" "b" {
  domain = "vpc"
  tags   = { Name = "nt531-eip-b" }
}

resource "aws_eip_association" "a" {
  allocation_id       = aws_eip.a.id
  instance_id         = aws_instance.a.id
  private_ip_address  = aws_instance.a.private_ip
  allow_reassociation = false
  depends_on          = [aws_internet_gateway.a]
}

resource "aws_eip_association" "b" {
  allocation_id       = aws_eip.b.id
  instance_id         = aws_instance.b.id
  private_ip_address  = aws_instance.b.private_ip
  allow_reassociation = false
  depends_on          = [aws_internet_gateway.b]
}
