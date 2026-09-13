#!/usr/bin/env bash
# ==============================================================================
# Script: collect_ena_metrics.sh
# Mục tiêu: Đọc và xuất các thanh ghi phần cứng AWS Nitro ENA Driver
# ==============================================================================

set -euo pipefail

INTERFACE="eth0"
OUTPUT_FILE="${1:-/tmp/ena_metrics_$(date +%s).txt}"

echo "=================================================================="
echo " AWS NITRO ENA DRIVER HARDWARE METRICS"
echo " Time: $(date)"
echo " Interface: ${INTERFACE}"
echo "=================================================================="

if ! command -v ethtool &> /dev/null; then
    echo "LỖI: ethtool chưa được cài đặt. Đang cài đặt..."
    sudo dnf install -y ethtool || sudo apt-get install -y ethtool
fi

echo "--- THÔNG TIN DRIVER ENA ---"
ethtool -i "${INTERFACE}"

echo -e "\n--- BỘ ĐẾM HẠN MỨC MẠNG (ALLOWANCE COUNTERS) ---"
ethtool -S "${INTERFACE}" | grep -E "allowance_exceeded|drops|overruns" | tee "${OUTPUT_FILE}"

echo -e "\n--- ĐÁNH GIÁ TÌNH TRẠNG NGHẼN MẠNG NITRO ---"
BW_EXCEEDED=$(ethtool -S "${INTERFACE}" | grep "bw_in_allowance_exceeded" | awk '{print $2}' || echo "0")
PPS_EXCEEDED=$(ethtool -S "${INTERFACE}" | grep "pps_allowance_exceeded" | awk '{print $2}' || echo "0")
CONN_EXCEEDED=$(ethtool -S "${INTERFACE}" | grep "conntrack_allowance_exceeded" | awk '{print $2}' || echo "0")

if [ "${BW_EXCEEDED}" -gt 0 ]; then
    echo "⚠️ CẢNH BÁO: Phát hiện ${BW_EXCEEDED} lần bão hòa băng thông (bw_in_allowance_exceeded)!"
else
    echo "✅ Băng thông (Bandwidth): Bình thường, không bị bóp nghẽn."
fi

if [ "${PPS_EXCEEDED}" -gt 0 ]; then
    echo "⚠️ CẢNH BÁO: Phát hiện ${PPS_EXCEEDED} lần vượt hạn mức số gói tin/giây (pps_allowance_exceeded)!"
else
    echo "✅ Số gói tin/giây (PPS): Bình thường."
fi

if [ "${CONN_EXCEEDED}" -gt 0 ]; then
    echo "⚠️ CẢNH BÁO: Phát hiện ${CONN_EXCEEDED} lần vượt hạn mức theo dõi kết nối Security Group (conntrack_allowance_exceeded)!"
else
    echo "✅ Kết nối (Conntrack): Không bị tràn bảng trạng thái."
fi

echo -e "\nKết quả đã lưu vào: ${OUTPUT_FILE}"
