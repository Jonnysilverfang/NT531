#!/usr/bin/env bash
# ==============================================================================
# Script: dut_server_setup.sh
# Vai trò: Điều khiển và cấu hình thiết bị chịu tải (Device Under Test - DUT Receiver)
#          Chạy trực tiếp trên Target Server (10.2.1.10) hoặc gọi từ xa qua AWS SSM.
# Thiết kế chuẩn học thuật:
#  - Xác thực trạng thái nạp XDP Native/Driver mode fail-fast (kiểm tra ip -details và bpftool)
#  - Ngăn chặn triệt để xdpgeneric/SKB mode
#  - Kiểm tra sự tồn tại của BPF maps thực tế (xdp_config_map, xdp_stats_map)
#  - Đo đạc SoftIRQ trên toàn bộ vCPU và xuất snapshot JSON ra stdout phục vụ SSM transport
#  - Xử lý lỗi có cấu trúc, không nuốt lỗi cẩu thả bằng `|| true`
# ==============================================================================

set -euo pipefail

ACTION="${1:-status}"
INTERFACE="${2:-eth0}"
OUTFILE="${3:-/tmp/dut_counters.json}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Hàm hỗ trợ kiểm tra tiến trình
stop_daemon_process() {
    local pattern="$1"
    if pgrep -f "${pattern}" >/dev/null 2>&1; then
        if ! pkill -f "${pattern}"; then
            echo "[!] Lỗi: phát hiện nhưng không dừng được daemon '${pattern}'." >&2
            return 1
        fi
        sleep 1
    fi
}

case "${ACTION}" in
    start_daemons)
        echo "[*] DUT: Đang dọn dẹp các daemon cũ..."
        stop_daemon_process "iperf3 -s"
        stop_daemon_process "sockperf server"

        echo "[*] DUT: Khởi chạy daemons đo kiểm trên port 5201 và 5202..."
        # Port 5201: Cổng hứng bão UDP Flood (Attacker Target)
        iperf3 -s -p 5201 -D
        
        # Port 5202: Cổng phục vụ dịch vụ hợp lệ (Legitimate Probe Target)
        if command -v sockperf &>/dev/null; then
            sockperf server -i 0.0.0.0 --port 5202 --daemonize
        else
            iperf3 -s -p 5202 -D
        fi

        # Xác thực tiến trình đã chạy
        if pgrep -f "iperf3 -s -p 5201" >/dev/null && (pgrep -f "sockperf server" >/dev/null || pgrep -f "iperf3 -s -p 5202" >/dev/null); then
            echo "[✓] DUT: Daemons đã sẵn sàng và đang lắng nghe trên port 5201 (UDP Flood) và 5202 (Probe)."
        else
            echo "[!] LỖI: Không thể khởi chạy đầy đủ daemon trên DUT!" >&2
            exit 1
        fi
        ;;

    apply_iptables_drop)
        echo "[*] DUT: Áp dụng Linux iptables INPUT DROP trên UDP port 5201..."
        # Gỡ rule cũ nếu đã tồn tại trước đó để tránh trùng lặp
        if sudo iptables -C INPUT -p udp --dport 5201 -j DROP 2>/dev/null; then
            sudo iptables -D INPUT -p udp --dport 5201 -j DROP
        fi

        sudo iptables -I INPUT 1 -p udp --dport 5201 -j DROP

        # Xác thực rule đã gắn thành công (Fail-fast verification)
        if sudo iptables -C INPUT -p udp --dport 5201 -j DROP 2>/dev/null; then
            echo "[✓] DUT: iptables filter đã kích hoạt và xác thực thành công."
        else
            echo "[!] LỖI NGHIÊM TRỌNG: Không thể xác thực rule iptables trên DUT!" >&2
            exit 1
        fi
        ;;

    remove_iptables_drop)
        echo "[*] DUT: Gỡ bỏ Linux iptables rule trên UDP port 5201..."
        if sudo iptables -C INPUT -p udp --dport 5201 -j DROP 2>/dev/null; then
            sudo iptables -D INPUT -p udp --dport 5201 -j DROP
            echo "[✓] DUT: iptables filter đã gỡ."
        else
            echo "[*] DUT: Không có rule iptables nào cần gỡ."
        fi
        ;;

    apply_xdp_native)
        echo "[*] DUT: Chuẩn bị nạp chương trình C eBPF/XDP Native Hook vào interface ${INTERFACE}..."
        # Đảm bảo MTU 1500 cho ENA single-buffer XDP
        sudo ip link set dev "${INTERFACE}" mtu 1500
        
        # Nạp qua loader
        sudo "${PROJECT_ROOT}/ebpf/ebpf_loader.sh" load "${INTERFACE}"
        sudo "${PROJECT_ROOT}/ebpf/ebpf_loader.sh" enable-drop "${INTERFACE}"

        echo "[*] DUT: Tiến hành xác thực chuyên sâu XDP Native Mode..."
        local_details=$(ip -details link show dev "${INTERFACE}")
        echo "${local_details}" > /tmp/xdp_ip_link_details.txt

        # 1. Kiểm tra có chuỗi xdp
        if ! echo "${local_details}" | grep -qi "xdp"; then
            echo "[!] LỖI NGHIÊM TRỌNG: Không tìm thấy hook XDP nào trên interface ${INTERFACE}!" >&2
            exit 1
        fi

        # 2. Bắt buộc kiểm tra Native / Driver mode; từ chối Generic / SKB mode.
        # iproute2 thường biểu diễn native attach là "prog/xdp", còn generic là
        # "prog/xdpgeneric". Một số phiên bản mới in rõ mode native/driver.
        if echo "${local_details}" | grep -qiE "xdpgeneric|mode generic"; then
            echo "[!] LỖI BÁC BỎ HỌC THUẬT: XDP đang chạy ở Generic/SKB mode (không phải Native Driver Hook)!" >&2
            exit 1
        fi
        if ! echo "${local_details}" | grep -qiE "prog/xdp([[:space:]]|$)|xdpdrv|mode (native|driver)"; then
            echo "[!] LỖI BÁC BỎ HỌC THUẬT: Không có bằng chứng dương tính rằng XDP chạy ở Native/Driver mode!" >&2
            exit 1
        fi

        # 3. bpftool và bằng chứng attachment/map là điều kiện bắt buộc.
        command -v bpftool >/dev/null 2>&1 || {
            echo "[!] LỖI: bpftool là dependency bắt buộc để xác minh XDP." >&2
            exit 1
        }

        local bpftool_net
        if ! bpftool_net=$(sudo bpftool net show dev "${INTERFACE}" 2>/tmp/xdp_bpftool_net.stderr); then
            echo "[!] LỖI: bpftool net show thất bại; không thể chứng minh attachment." >&2
            exit 1
        fi
        echo "${bpftool_net}" > /tmp/xdp_bpftool_net.txt
        if ! echo "${bpftool_net}" | grep -qi "xdp"; then
            echo "[!] LỖI: bpftool net không xác nhận XDP program trên ${INTERFACE}." >&2
            exit 1
        fi
        echo "    -> bpftool net show: Xác nhận XDP program đang hook tại dev ${INTERFACE}."

        local map_list
        if ! map_list=$(sudo bpftool map show 2>/tmp/xdp_bpftool_map.stderr); then
            echo "[!] LỖI: Không truy vấn được danh sách BPF map." >&2
            exit 1
        fi
        for required_map in xdp_config_map xdp_stats_map; do
            if ! echo "${map_list}" | grep -qw "${required_map}"; then
                echo "[!] LỖI: Không tìm thấy BPF map bắt buộc ${required_map}." >&2
                exit 1
            fi
        done
        echo "    -> BPF Maps: Tìm thấy xdp_config_map và xdp_stats_map."

        echo "[✓] DUT: eBPF/XDP Native Hook đã gắn và XÁC THỰC THÀNH CÔNG trên ${INTERFACE} (Driver mode)."
        ;;

    remove_xdp_native)
        echo "[*] DUT: Gỡ bỏ chương trình eBPF/XDP Native Hook khỏi interface ${INTERFACE}..."
        if sudo "${PROJECT_ROOT}/ebpf/ebpf_loader.sh" unload "${INTERFACE}" 2>/dev/null; then
            echo "    -> Đã tháo XDP hook khỏi ${INTERFACE}."
        else
            echo "    [!] Cảnh báo: Loader thông báo không có hook XDP cần gỡ." >&2
        fi

        # Khôi phục MTU 9001
        if sudo ip link set dev "${INTERFACE}" mtu 9001 2>/dev/null; then
            echo "[✓] DUT: eBPF/XDP Native Hook đã gỡ, MTU 9001 đã khôi phục."
        else
            echo "[!] Cảnh báo có cấu trúc: XDP đã gỡ nhưng không thể khôi phục MTU 9001." >&2
            exit 1
        fi
        ;;

    snapshot_counters)
        # Snapshot SoftIRQ và CPU jiffies.
        # Xuất ra file $OUTFILE và ĐỒNG THỜI in ra stdout có kèm marker để SSM get-command-invocation đọc được.
        python3 - "${OUTFILE}" "${INTERFACE}" <<'EOF'
import json, time, os, socket, sys
from datetime import datetime, timezone

outfile = sys.argv[1] if len(sys.argv) > 1 else "/tmp/dut_counters.json"
interface = sys.argv[2] if len(sys.argv) > 2 else "eth0"

def read_softirqs():
    rx, tx = 0, 0
    try:
        with open("/proc/softirqs") as f:
            for line in f:
                parts = line.split()
                if not parts: continue
                if parts[0] == "NET_RX:":
                    rx = sum(int(x) for x in parts[1:])
                elif parts[0] == "NET_TX:":
                    tx = sum(int(x) for x in parts[1:])
    except Exception as e:
        sys.stderr.write(f"Error reading softirqs: {e}\n")
    return {"net_rx": rx, "net_tx": tx}

def read_stat():
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu "):
                    parts = [int(x) for x in line.split()[1:]]
                    # Format /proc/stat: user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
                    total = sum(parts)
                    return {
                        "user": parts[0],
                        "system": parts[2],
                        "idle": parts[3],
                        "softirq": parts[6] if len(parts) > 6 else parts[5],
                        "total_jiffies": total
                    }
    except Exception as e:
        sys.stderr.write(f"Error reading /proc/stat: {e}\n")
    return {}

def get_instance_id():
    # Thử đọc AWS EC2 instance-id từ DMI hoặc IMDSv2
    try:
        with open("/sys/devices/virtual/dmi/id/product_uuid") as f:
            return f.read().strip()
    except Exception:
        return socket.gethostname()

def get_mac(iface):
    try:
        with open(f"/sys/class/net/{iface}/address") as f:
            return f.read().strip()
    except Exception:
        return "unknown"

data = {
    "host": socket.gethostname(),
    "instance_id": get_instance_id(),
    "interface": interface,
    "mac_address": get_mac(interface),
    "timestamp_monotonic_ns": time.monotonic_ns(),
    "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
    "softirqs": read_softirqs(),
    "cpu_stat": read_stat()
}

json_str = json.dumps(data, indent=2)

# Ghi ra file cục bộ trên DUT
try:
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(json_str)
except Exception as e:
    sys.stderr.write(f"Warning: could not write local outfile {outfile}: {e}\n")

# In ra stdout với sentinel marker rõ ràng để runner controller trích xuất qua SSM
print("___DUT_SNAPSHOT_JSON_BEGIN___")
print(json_str)
print("___DUT_SNAPSHOT_JSON_END___")
EOF
        echo "[✓] DUT: Đã thu thập snapshot SoftIRQ và CPU stat."
        ;;

    status)
        echo "=== TRẠNG THÁI DUT RECEIVER ==="
        echo "iptables rules port 5201:"
        sudo iptables -L INPUT -n -v | grep 5201 || echo "  (Không có rule port 5201)"
        echo "XDP status:"
        ip -details link show dev "${INTERFACE}" | grep -i xdp || echo "  (Chưa gắn XDP)"
        if command -v bpftool &>/dev/null; then
            echo "bpftool net status:"
            if ! sudo bpftool net show dev "${INTERFACE}" 2>/dev/null; then
                echo "  (Không truy vấn được trạng thái bpftool net)" >&2
            fi
        fi
        ;;

    *)
        echo "Sử dụng: $0 {start_daemons|apply_iptables_drop|remove_iptables_drop|apply_xdp_native|remove_xdp_native|snapshot_counters|status} [interface] [outfile]"
        exit 1
        ;;
esac
