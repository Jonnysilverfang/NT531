#!/usr/bin/env python3
"""
ebpf_monitor.py - Giám sát hiệu năng xử lý gói tin tầng eBPF/XDP theo thời gian thực
Chuẩn hóa:
 - Loại bỏ shell=True để bảo mật (CWE-78)
 - Xử lý đa định dạng đầu ra bpftool (integer, hex string, byte array)
 - Xử lý ngoại lệ rõ ràng, không nuốt lỗi
"""

import sys
import time
import subprocess
import json

def parse_val(raw):
    """Chuyển đổi linh hoạt giá trị từ bpftool JSON (int, hex, list byte) sang uint64."""
    if isinstance(raw, int):
        return raw
    elif isinstance(raw, str):
        try:
            return int(raw, 16) if raw.startswith("0x") else int(raw)
        except ValueError:
            return 0
    elif isinstance(raw, list):
        # Mảng bytes little-endian
        val = 0
        for i, b in enumerate(raw[:8]):
            if isinstance(b, str):
                b = int(b, 16) if b.startswith("0x") else int(b)
            val |= (b << (8 * i))
        return val
    elif isinstance(raw, dict) and "value" in raw:
        return parse_val(raw["value"])
    return 0

def get_bpf_map_stats():
    """Trích xuất dữ liệu từ xdp_stats_map bằng bpftool an toàn (không dùng shell=True)."""
    try:
        cmd_find = ["sudo", "bpftool", "map", "show", "-j"]
        res = subprocess.run(cmd_find, capture_output=True, text=True, check=True)
        maps = json.loads(res.stdout)
        
        map_id = None
        for m in maps:
            if m.get("name") == "xdp_stats_map":
                map_id = m.get("id")
                break

        if map_id is None:
            return None

        cmd_dump = ["sudo", "bpftool", "map", "dump", "id", str(map_id), "-j"]
        res_dump = subprocess.run(cmd_dump, capture_output=True, text=True, check=True)
        data = json.loads(res_dump.stdout)

        pass_packets = 0
        drop_packets = 0
        total_bytes = 0

        for entry in data:
            key_raw = entry.get("key")
            key = parse_val(key_raw)
            values = entry.get("values", [])
            total_val = sum(parse_val(v) for v in values)

            if key == 0:
                pass_packets = total_val
            elif key == 1:
                drop_packets = total_val
            elif key == 2:
                total_bytes = total_val

        return {
            "pass_packets": pass_packets,
            "drop_packets": drop_packets,
            "total_bytes": total_bytes
        }
    except subprocess.CalledProcessError as cpe:
        sys.stderr.write(f"[!] Lỗi gọi lệnh bpftool: {cpe}\n")
        return None
    except json.JSONDecodeError as jde:
        sys.stderr.write(f"[!] Lỗi phân tích JSON từ bpftool: {jde}\n")
        return None
    except Exception as e:
        sys.stderr.write(f"[!] Lỗi không xác định: {e}\n")
        return None

def main():
    print("================================================================================")
    print("      AWS NITRO ENA - BỘ GIÁM SÁT HIỆU NĂNG eBPF / XDP THỜI GIAN THỰC         ")
    print("================================================================================")
    print("Đang đọc dữ liệu từ Kernel BPF Map Per-CPU Array... Nhấn Ctrl+C để dừng.\n")

    prev_stats = get_bpf_map_stats()
    if prev_stats is None:
        print("[-] Không tìm thấy xdp_stats_map. Vui lòng nạp eBPF bằng 'sudo ./ebpf_loader.sh load' trước.")
        sys.exit(1)

    prev_time = time.monotonic()
    print(f"{'Thời gian':<12} | {'XDP_PASS (PPS)':<16} | {'XDP_DROP (PPS)':<16} | {'Throughput (Mbps)':<18} | {'Tổng Packets':<15}")
    print("-" * 86)

    try:
        while True:
            time.sleep(1.0)
            curr_time = time.monotonic()
            curr_stats = get_bpf_map_stats()

            if curr_stats is None:
                continue

            dt = curr_time - prev_time
            if dt <= 0:
                continue

            deltas = {
                key: curr_stats[key] - prev_stats[key]
                for key in ("pass_packets", "drop_packets", "total_bytes")
            }
            if any(value < 0 for value in deltas.values()):
                sys.stderr.write("[!] BPF counter reset/map reload detected; resetting monitor baseline.\n")
                prev_stats, prev_time = curr_stats, curr_time
                continue

            d_pass = deltas["pass_packets"] / dt
            d_drop = deltas["drop_packets"] / dt
            d_bytes = deltas["total_bytes"] / dt
            mbps = (d_bytes * 8) / 1_000_000

            total_pkts = curr_stats["pass_packets"] + curr_stats["drop_packets"]
            time_str = time.strftime("%H:%M:%S")

            print(f"{time_str:<12} | {d_pass:>14,.0f} | {d_drop:>14,.0f} | {mbps:>16,.2f} | {total_pkts:>15,}")

            prev_stats = curr_stats
            prev_time = curr_time

    except KeyboardInterrupt:
        print("\n[✓] Đã dừng tiến trình giám sát eBPF.")

if __name__ == "__main__":
    main()
