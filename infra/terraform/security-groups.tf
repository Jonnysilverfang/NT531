resource "aws_security_group" "a" {
  name        = "nt531-sg-a"
  description = "Allow lab traffic to EC2 A"
  vpc_id      = aws_vpc.a.id

  tags = {
    Name      = "nt531-sg-a"
    ManagedBy = "Manual"
  }
}

resource "aws_security_group" "b" {
  name        = "nt531-sg-b"
  description = "nt531-vpc-b"
  vpc_id      = aws_vpc.b.id

  tags = {
    Name = "nt531-sg-b"
  }
}