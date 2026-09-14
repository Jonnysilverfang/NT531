#!/usr/bin/env python3
"""
calculate_softirq_delta.py - Mô-đun tính toán và xác thực SoftIRQ Delta trên DUT
Mục tiêu:
 - Đọc hai tệp snapshot (before và after) thu thập từ DUT trong cùng một workload window
 - Xác minh tính toàn vẹn: cùng host/instance_id, monotonic duration > 0, total_jiffies > 0
 - Tính toán chính xác SoftIRQ % và tổng CPU busy %:
     Delta_SoftIRQ = SoftIRQ_after - SoftIRQ_before
     Delta_Total = Total_Jiffies_after - Total_Jiffies_before
     SoftIRQ% = 100.0 * (Delta_SoftIRQ / Delta_Total)
 - Tính toán Delta Net RX / Net TX packets/interrupts
"""

import sys
import os
import json
import argparse

def parse_snapshot(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file snapshot: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def compute_delta(before_path, after_path, condition="unknown", run_id=1):
    b = parse_snapshot(before_path)
    a = parse_snapshot(after_path)

    # 1. Xác thực riêng từng định danh để không che khuất instance mismatch
    for identity_key in ("host", "instance_id", "interface", "mac_address"):
        before_value = b.get(identity_key)
        after_value = a.get(identity_key)
        if not before_value or not after_value:
            raise ValueError(f"Snapshot thiếu định danh bắt buộc: {identity_key}")
        if before_value != after_value:
            raise ValueError(
                f"Bất nhất {identity_key}: Before={before_value}, After={after_value}"
            )

    # 2. Xác thực cửa sổ thời gian đo
    t_before_ns = b.get("timestamp_monotonic_ns", 0)
    t_after_ns = a.get("timestamp_monotonic_ns", 0)
    if not isinstance(t_before_ns, (int, float)) or not isinstance(t_after_ns, (int, float)):
        raise ValueError("timestamp_monotonic_ns phải là số")
    if t_before_ns <= 0 or t_after_ns <= t_before_ns:
        raise ValueError("Cửa sổ đo monotonic không hợp lệ: duration phải > 0")
    duration_sec = (t_after_ns - t_before_ns) / 1e9

    # 3. Trích xuất chỉ số CPU Jiffies từ /proc/stat
    stat_b = b.get("cpu_stat", {})
    stat_a = a.get("cpu_stat", {})
    total_b = stat_b.get("total_jiffies", 0)
    total_a = stat_a.get("total_jiffies", 0)
    softirq_b = stat_b.get("softirq", 0)
    softirq_a = stat_a.get("softirq", 0)
    idle_b = stat_b.get("idle", 0)
    idle_a = stat_a.get("idle", 0)
    iowait_b = stat_b.get("iowait", 0)
    iowait_a = stat_a.get("iowait", 0)

    delta_total = total_a - total_b
    delta_softirq = softirq_a - softirq_b
    delta_idle = idle_a - idle_b
    delta_iowait = iowait_a - iowait_b

    if delta_total <= 0:
        raise ValueError("delta_total_jiffies phải > 0")
    if delta_softirq < 0:
        raise ValueError("Bộ đếm softirq bị giảm giữa hai snapshot")
    if delta_idle < 0 or delta_iowait < 0:
        raise ValueError("Bộ đếm idle/iowait bị giảm giữa hai snapshot")
    delta_busy = delta_total - delta_idle - delta_iowait
    if delta_busy < 0 or delta_busy > delta_total:
        raise ValueError("Delta CPU busy nằm ngoài cửa sổ total jiffies")
    softirq_percent = 100.0 * float(delta_softirq) / float(delta_total)
    cpu_total_percent = 100.0 * float(delta_busy) / float(delta_total)

    # 4. Trích xuất chỉ số ngắt mạng từ /proc/softirqs
    si_b = b.get("softirqs", {})
    si_a = a.get("softirqs", {})
    delta_net_rx = si_a.get("net_rx", 0) - si_b.get("net_rx", 0)
    delta_net_tx = si_a.get("net_tx", 0) - si_b.get("net_tx", 0)
    if delta_net_rx < 0 or delta_net_tx < 0:
        raise ValueError("Bộ đếm NET_RX/NET_TX bị giảm giữa hai snapshot")

    result = {
        "condition": condition,
        "run_id": run_id,
        "host": a.get("host", "dut"),
        "instance_id": a.get("instance_id", "unknown"),
        "interface": a.get("interface", "eth0"),
        "duration_sec": round(duration_sec, 4),
        "timestamp_utc_before": b.get("timestamp_utc"),
        "timestamp_utc_after": a.get("timestamp_utc"),
        "metrics": {
            "delta_total_jiffies": delta_total,
            "delta_idle_jiffies": delta_idle,
            "delta_iowait_jiffies": delta_iowait,
            "delta_busy_jiffies": delta_busy,
            "delta_softirq_jiffies": delta_softirq,
            "softirq_percent": round(softirq_percent, 4),
            "cpu_total_percent": round(cpu_total_percent, 4),
            "delta_net_rx_interrupts": delta_net_rx,
            "delta_net_tx_interrupts": delta_net_tx,
            "net_rx_irq_per_sec": round(delta_net_rx / duration_sec, 2) if duration_sec > 0 else 0
        }
    }
    return result

def main():
    parser = argparse.ArgumentParser(description="Tính toán SoftIRQ Delta trên DUT giữa 2 snapshot Before và After")
    parser.add_argument("--before", required=True, help="Đường dẫn file snapshot trước khi phát tải")
    parser.add_argument("--after", required=True, help="Đường dẫn file snapshot sau khi phát tải")
    parser.add_argument("--condition", default="test", help="Điều kiện đo (iptables / xdp / mtu_1500 / mtu_9001)")
    parser.add_argument("--run-id", type=int, default=1, help="Mã phiên chạy (run_id)")
    parser.add_argument("--output-json", default=None, help="Đường dẫn xuất file JSON kết quả delta")

    args = parser.parse_args()

    try:
        res = compute_delta(args.before, args.after, args.condition, args.run_id)
        out_str = json.dumps(res, indent=2)
        if args.output_json:
            with open(args.output_json, "w", encoding="utf-8") as f:
                f.write(out_str)
            print(f"[✓] Đã xuất kết quả SoftIRQ delta ra: {args.output_json}")
        else:
            print(out_str)
    except Exception as e:
        sys.stderr.write(f"[!] Lỗi tính toán SoftIRQ delta: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
