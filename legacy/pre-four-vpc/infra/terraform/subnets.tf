resource "aws_subnet" "a" {
  vpc_id                  = aws_vpc.a.id
  cidr_block              = "10.10.10.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false

  tags = {
    Name      = "nt531-subnet-a"
    ManagedBy = "Manual"
  }
}

resource "aws_subnet" "b" {
  vpc_id                  = aws_vpc.b.id
  cidr_block              = "10.20.10.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false

  tags = {
    Name      = "nt531-subnet-b"
    ManagedBy = "Manual"
  }
}