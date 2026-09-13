output "client_a1_public_ip" {
  description = "Public IP của EC2 Client A1 để kết nối"
  value       = aws_instance.ec2_client_a.public_ip
}

output "client_a1_private_ip" {
  description = "Private IP của EC2 Client A1"
  value       = aws_instance.ec2_client_a.private_ip
}

output "server_b1_peering_ip" {
  description = "Private IP của Server B1 (Cùng AZ-a, định tuyến qua VPC Peering: 10.2.1.0/24)"
  value       = aws_instance.ec2_server_b1.private_ip
}

output "server_b2_tgw_ip" {
  description = "Private IP của Server B2 (Định tuyến qua AWS Transit Gateway: 10.2.2.0/24)"
  value       = aws_instance.ec2_server_b2.private_ip
}

output "privatelink_endpoint_dns" {
  description = "DNS Name của Interface VPC Endpoint trong VPC A"
  value       = aws_vpc_endpoint.interface_endpoint_a.dns_entry[0].dns_name
}

data "aws_network_interface" "privatelink_eni" {
  id = tolist(aws_vpc_endpoint.interface_endpoint_a.network_interface_ids)[0]
}

output "privatelink_endpoint_ip" {
  description = "Địa chỉ Private IP thực tế của PrivateLink Interface Endpoint ENI"
  value       = data.aws_network_interface.privatelink_eni.private_ip
}

output "transit_gateway_id" {
  description = "ID của AWS Transit Gateway"
  value       = aws_ec2_transit_gateway.tgw.id
}

output "peering_connection_id" {
  description = "ID của VPC Peering Connection"
  value       = aws_vpc_peering_connection.peer_a_b.id
}
