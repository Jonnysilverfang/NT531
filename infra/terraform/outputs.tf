output "vpcs" {
  description = "IDs and address ranges of the two NT531 VPCs."
  value = {
    a = { id = aws_vpc.a.id, cidr = aws_vpc.a.cidr_block }
    b = { id = aws_vpc.b.id, cidr = aws_vpc.b.cidr_block }
  }
}
