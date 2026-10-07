resource "aws_vpc_security_group_ingress_rule" "a_ssh" {
  security_group_id = aws_security_group.a.id
  cidr_ipv4         = var.ssh_admin_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "a_icmp_from_b" {
  security_group_id = aws_security_group.a.id
  description       = "Allow lab traffic to EC2 A"
  cidr_ipv4         = aws_subnet.b.cidr_block
  ip_protocol       = "icmp"
  from_port         = -1
  to_port           = -1
}

resource "aws_vpc_security_group_egress_rule" "a_all_ipv4" {
  security_group_id = aws_security_group.a.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "b_ssh" {
  security_group_id = aws_security_group.b.id
  cidr_ipv4         = var.ssh_admin_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "b_icmp_from_a" {
  security_group_id = aws_security_group.b.id
  cidr_ipv4         = aws_subnet.a.cidr_block
  ip_protocol       = "icmp"
  from_port         = -1
  to_port           = -1
}

resource "aws_vpc_security_group_ingress_rule" "b_iperf_from_a" {
  security_group_id = aws_security_group.b.id
  cidr_ipv4         = "10.10.10.212/32"
  ip_protocol       = "tcp"
  from_port         = 5201
  to_port           = 5201
}

resource "aws_vpc_security_group_egress_rule" "b_all_ipv4" {
  security_group_id = aws_security_group.b.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
