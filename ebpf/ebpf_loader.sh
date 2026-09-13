#!/usr/bin/env bash
# ==============================================================================
# ebpf_loader.sh - Tải và gỡ bỏ chương trình eBPF/XDP trên AWS ENA Driver
# Chuẩn hóa: Đường dẫn tuyệt đối, kiểm tra MTU tương thích ENA Native XDP
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERFACE="${2:-eth0}"
BPF_OBJ="${SCRIPT_DIR}/xdp_packet_filter.o"
BPF_PROG_SEC="xdp"

action="${1:-status}"

check_mtu() {
    local current_mtu
    current_mtu=$(ip link show dev "${INTERFACE}" | awk '/mtu/ {print $5}')
    if [ "${current_mtu}" -gt 1500 ]; then
        echo "[!] CẢNH BÁO: MTU hiện tại là ${current_mtu}."
        echo "    Driver AWS ENA Native XDP yêu cầu frame vừa vặn single page (MTU <= 1500) khi chạy single-buffer."
        echo "    Đang tạm thời điều chỉnh MTU về 1500 cho phiên kiểm thử XDP..."
        sudo ip link set dev "${INTERFACE}" mtu 1500
    fi
}

verify_native_hook() {
    local link_details net_details
    link_details=$(sudo ip -details link show dev "${INTERFACE}")
    if printf '%s\n' "${link_details}" | grep -Eqi 'xdpgeneric|mode[[:space:]]+generic'; then
        echo "[-] FAIL: ${INTERFACE} đang dùng generic/SKB XDP, không phải native driver hook." >&2
        return 1
    fi
    if ! printf '%s\n' "${link_details}" | grep -Eqi 'prog/xdp|xdpdrv|mode[[:space:]]+(native|driver)'; then
        echo "[-] FAIL: ip -details không xác nhận XDP native/driver hook trên ${INTERFACE}." >&2
        return 1
    fi

    command -v bpftool >/dev/null 2>&1 || {
        echo "[-] FAIL: bpftool là bắt buộc để kiểm chứng hook/map." >&2
        return 1
    }
    net_details=$(sudo bpftool net show dev "${INTERFACE}")
    printf '%s\n' "${net_details}" | grep -qi 'xdp' || {
        echo "[-] FAIL: bpftool net không xác nhận chương trình XDP trên ${INTERFACE}." >&2
        return 1
    }
    sudo bpftool map show | grep -q 'name xdp_config_map' || {
        echo "[-] FAIL: thiếu xdp_config_map sau khi load." >&2
        return 1
    }
    sudo bpftool map show | grep -q 'name xdp_stats_map' || {
        echo "[-] FAIL: thiếu xdp_stats_map sau khi load." >&2
        return 1
    }
}

case "$action" in
    load)
        echo "[+] Đang biên dịch mã nguồn eBPF (BTF Maps)..."
        make -C "${SCRIPT_DIR}"

        check_mtu

        echo "[+] Đang nạp eBPF/XDP bytecode (${BPF_OBJ}) vào ${INTERFACE}..."
        sudo ip link set dev "${INTERFACE}" xdp obj "${BPF_OBJ}" sec "${BPF_PROG_SEC}"
        if ! verify_native_hook; then
            echo "[-] Load verification thất bại; thử gỡ hook vừa nạp." >&2
            if ! sudo ip link set dev "${INTERFACE}" xdp off; then
                echo "[-] CẢNH BÁO: rollback XDP thất bại; cần kiểm tra thủ công ${INTERFACE}." >&2
            fi
            exit 1
        fi
        echo "[✓] Đã xác minh eBPF/XDP Native driver hook và hai BPF maps trên ${INTERFACE}."
        ;;

    unload)
        echo "[+] Đang gỡ bỏ chương trình eBPF/XDP khỏi ${INTERFACE}..."
        if ! sudo ip link set dev "${INTERFACE}" xdp off; then
            echo "[-] FAIL: không thể gỡ XDP khỏi ${INTERFACE}." >&2
            exit 1
        fi
        echo "[✓] Đã gỡ bỏ XDP hoàn toàn khỏi ${INTERFACE}."
        ;;

    status)
        echo "=== Trạng thái XDP trên ${INTERFACE} ==="
        sudo ip link show dev "${INTERFACE}" | grep -i --color=always xdp || echo "Không có chương trình XDP nào đang gắn vào ${INTERFACE}."
        echo ""
        echo "=== Danh sách BPF Maps ==="
        sudo bpftool map show 2>/dev/null || echo "bpftool không có sẵn hoặc chưa nạp map."
        ;;

    enable-drop)
        echo "[+] Kích hoạt chế độ XDP_DROP trên BPF Map..."
        MAP_ID=$(sudo bpftool map show | grep xdp_config_map | awk -F: '{print $1}' | head -n 1)
        if [ -n "$MAP_ID" ]; then
            sudo bpftool map update id "$MAP_ID" key 0 0 0 0 value 1 0 0 0
            echo "[✓] Chế độ XDP_DROP: BẬT (Drop UDP port 5201 tại driver ENA)"
        else
            echo "[-] Không tìm thấy map xdp_config_map. Vui lòng chạy './ebpf_loader.sh load' trước."
        fi
        ;;

    disable-drop)
        echo "[+] Tắt chế độ XDP_DROP trên BPF Map..."
        MAP_ID=$(sudo bpftool map show | grep xdp_config_map | awk -F: '{print $1}' | head -n 1)
        if [ -n "$MAP_ID" ]; then
            sudo bpftool map update id "$MAP_ID" key 0 0 0 0 value 0 0 0 0
            echo "[✓] Chế độ XDP_DROP: TẮT (Cho phép XDP_PASS)"
        else
            echo "[-] Không tìm thấy map xdp_config_map."
        fi
        ;;

    *)
        echo "Sử dụng: $0 {load|unload|status|enable-drop|disable-drop} [interface]"
        exit 1
        ;;
esac
