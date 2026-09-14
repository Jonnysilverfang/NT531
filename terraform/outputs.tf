output "inventory" {
  description = "Authoritative inventory consumed by preflight and the SSM controller"
  value = {
    account_id        = data.aws_caller_identity.current.account_id
    region            = var.aws_region
    availability_zone = var.availability_zone
    ami_id            = nonsensitive(local.benchmark_ami_id)
    instance_type     = var.instance_type
    artifact_bucket   = aws_s3_bucket.artifacts.id
    kms_key_arn       = aws_kms_key.experiment.arn
    client = {
      instance_id = aws_instance.client.id
      private_ip  = aws_instance.client.private_ip
    }
    server_b1 = {
      instance_id = aws_instance.server_b1.id
      private_ip  = aws_instance.server_b1.private_ip
      path        = "peering"
    }
    server_b2 = {
      instance_id = aws_instance.server_b2.id
      private_ip  = aws_instance.server_b2.private_ip
      path        = "tgw"
    }
    vpc_a_id                 = aws_vpc.a.id
    vpc_b_id                 = aws_vpc.b.id
    peering_connection_id    = aws_vpc_peering_connection.a_b.id
    transit_gateway_id       = aws_ec2_transit_gateway.experiment.id
    transit_gateway_rt_id    = aws_ec2_transit_gateway_route_table.experiment.id
    client_route_table_id    = aws_route_table.a_client.id
    peering_route_table_id   = aws_route_table.b_peering.id
    tgw_route_table_id       = aws_route_table.b_tgw.id
    server_security_group_id = aws_security_group.servers.id
    flow_log_group           = aws_cloudwatch_log_group.flow_logs.name
  }
}

output "estimated_billable_components" {
  description = "Cost review list; prices are intentionally not hard-coded"
  value = [
    "3 x c6i.large EC2",
    "3 x public IPv4 address",
    "1 x Transit Gateway plus 2 VPC attachments and data processing",
    "3 x 20 GiB gp3 EBS",
    "CloudWatch detailed monitoring and encrypted flow-log ingestion/storage",
    "S3 artifact storage and KMS API usage"
  ]
}
