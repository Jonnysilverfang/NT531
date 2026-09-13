#!/usr/bin/env bash
# ==============================================================================
# Script: cleanup_resources.sh
# Mục tiêu: Dọn dẹp sạch toàn bộ tài nguyên lab trên AWS Sydney (ap-southeast-2)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"
REGION="ap-southeast-2"

echo "========================================================================"
echo " TIẾN HÀNH DỌN DẸP TÀI NGUYÊN LAB HIỆU NĂNG MẠNG TẠI SYDNEY (${REGION})"
echo "========================================================================"

if [ -d "${TERRAFORM_DIR}/.terraform" ]; then
    echo "Phát hiện hạ tầng được quản lý bởi Terraform. Đang chạy terraform destroy..."
    cd "${TERRAFORM_DIR}"
    terraform destroy -auto-approve
    echo "✅ Đã hủy toàn bộ tài nguyên qua Terraform thành công!"
else
    echo "Dọn dẹp thủ công qua AWS CLI tại Region ${REGION}..."

    echo "1. Tìm và xóa EC2 instances..."
    INSTANCE_IDS=$(aws ec2 describe-instances --region "${REGION}" \
        --filters "Name=tag:Project,Values=network-performance-capstone" "Name=instance-state-name,Values=running,pending,stopped" \
        --query "Reservations[].Instances[].InstanceId" --output text)
    if [ -n "${INSTANCE_IDS}" ] && [ "${INSTANCE_IDS}" != "None" ]; then
        aws ec2 terminate-instances --region "${REGION}" --instance-ids ${INSTANCE_IDS}
        echo "Đang chờ instances bị hủy..."
        aws ec2 wait instance-terminated --region "${REGION}" --instance-ids ${INSTANCE_IDS}
    fi

    echo "2. Tìm và xóa VPC Endpoints & Endpoint Services..."
    VPCE_IDS=$(aws ec2 describe-vpc-endpoints --region "${REGION}" \
        --filters "Name=tag:Project,Values=network-performance-capstone" \
        --query "VpcEndpoints[].VpcEndpointId" --output text)
    if [ -n "${VPCE_IDS}" ] && [ "${VPCE_IDS}" != "None" ]; then
        for id in ${VPCE_IDS}; do
            aws ec2 delete-vpc-endpoints --region "${REGION}" --vpc-endpoint-ids "${id}"
        done
    fi

    echo "3. Tìm và xóa Transit Gateway attachments & Transit Gateways..."
    TGW_ATTACH_IDS=$(aws ec2 describe-transit-gateway-attachments --region "${REGION}" \
        --filters "Name=tag:Project,Values=network-performance-capstone" "Name=state,Values=available,modifying" \
        --query "TransitGatewayAttachments[].TransitGatewayAttachmentId" --output text)
    if [ -n "${TGW_ATTACH_IDS}" ] && [ "${TGW_ATTACH_IDS}" != "None" ]; then
        for id in ${TGW_ATTACH_IDS}; do
            aws ec2 delete-transit-gateway-vpc-attachment --region "${REGION}" --transit-gateway-attachment-id "${id}"
        done
    fi

    echo "4. Tìm và xóa VPC Peering connections..."
    PEER_IDS=$(aws ec2 describe-vpc-peering-connections --region "${REGION}" \
        --filters "Name=tag:Project,Values=network-performance-capstone" "Name=status-code,Values=active,pending-acceptance" \
        --query "VpcPeeringConnections[].VpcPeeringConnectionId" --output text)
    if [ -n "${PEER_IDS}" ] && [ "${PEER_IDS}" != "None" ]; then
        for id in ${PEER_IDS}; do
            aws ec2 delete-vpc-peering-connection --region "${REGION}" --vpc-peering-connection-id "${id}"
        done
    fi

    echo "✅ Đã dọn dẹp hoàn tất! Không còn tài nguyên phát sinh chi phí."
fi
