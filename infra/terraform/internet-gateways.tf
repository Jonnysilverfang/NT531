resource "aws_internet_gateway" "a" {
  vpc_id = aws_vpc.a.id

  tags = {
    Name      = "nt531-igw-a"
    ManagedBy = "Manual"
  }
}

resource "aws_internet_gateway" "b" {
  vpc_id = aws_vpc.b.id

  tags = {
    Name      = "nt531-igw-b"
    ManagedBy = "Manual"
  }
}