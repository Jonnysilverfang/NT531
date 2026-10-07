resource "aws_instance" "a" {
  iam_instance_profile   = aws_iam_instance_profile.ssm.name
  ami                    = "ami-0d27e0fb3bac4d724"
  instance_type          = "c6i.large"
  subnet_id              = aws_subnet.a.id
  private_ip             = "10.10.10.212"
  vpc_security_group_ids = [aws_security_group.a.id]
  key_name               = "nt531-key"
  monitoring             = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_protocol_ipv6          = "disabled"
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    iops                  = 3000
    throughput            = 125
    encrypted             = false
    delete_on_termination = true
  }

  tags = {
    Name      = "nt531-ec2-a"
    ManagedBy = "Manual"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_instance" "b" {
  iam_instance_profile   = aws_iam_instance_profile.ssm.name
  ami                    = "ami-0d27e0fb3bac4d724"
  instance_type          = "c6i.large"
  subnet_id              = aws_subnet.b.id
  private_ip             = "10.20.10.155"
  vpc_security_group_ids = [aws_security_group.b.id]
  key_name               = "nt531-key"
  monitoring             = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_protocol_ipv6          = "disabled"
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    iops                  = 3000
    throughput            = 125
    encrypted             = false
    delete_on_termination = true
  }

  tags = {
    Name      = "nt531-ec2-b"
    ManagedBy = "Manual"
  }

  lifecycle {
    prevent_destroy = true
  }
}
