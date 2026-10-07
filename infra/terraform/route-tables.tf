resource "aws_route_table" "a" {
  vpc_id = aws_vpc.a.id

  tags = {
    Name = "nt531-rt-a"
  }
}

resource "aws_route_table" "b" {
  vpc_id = aws_vpc.b.id

  tags = {
    Name = "nt531-rt-b"
  }
}