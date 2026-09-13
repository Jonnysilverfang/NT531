#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS Network Performance Capstone - Scientific Statistical Analysis Engine
Tác giả: Capstone Research Team (Sydney ap-southeast-2)
Mục đích:
 - Tự động đối soát mã băm toàn vẹn (checksums.sha256) trước khi phân tích (Data Provenance).
 - Đọc trực tiếp và phân tích độc lập các observation-level records (KHÔNG HARD-CODE).
 - Giảm pseudoreplication bằng phân tích theo từng run độc lập (run-level paired analysis)
   và Hierarchical Bootstrap; N=3 vẫn được công khai là giới hạn lực thống kê.
 - Tránh lỗi numeric underflow p=0.0 (xuất chuẩn formatted_p_value: "< 1e-300").
"""

import os
import sys
import math
import json
import csv
import hashlib
import argparse
import random
from datetime import datetime

# Thiết lập UTF-8 cho stdout trên mọi nền tảng
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

class DataIntegrityError(Exception):
    """Ngoại lệ khi phát hiện sai lệch mã băm hoặc dữ liệu không toàn vẹn."""
    pass

def calculate_sha256(filepath):
    """Tính mã băm SHA256 của file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

REQUIRED_RAW_FILES = [
    "environment_manifest.json",
    "tc01_peering_tgw_samples.csv",
    "tc02_jumbo_frames_samples.json",
    "tc03_privatelink_samples.json",
    "tc04_xdp_iptables_samples.json"
]

def verify_checksum_manifest(input_dir):
    """Đối soát toàn bộ 5 file bắt buộc trong thư mục với checksums.sha256 (Fail-fast verification)."""
    checksum_file = os.path.join(input_dir, "checksums.sha256")
    if not os.path.exists(checksum_file):
        raise DataIntegrityError(f"Không tìm thấy file checksums.sha256 tại {checksum_file}")
    
    expected_hashes = {}
    with open(checksum_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                expected_hashes[parts[1]] = parts[0].lower()

    # Kiểm tra danh sách file bắt buộc không bị xóa bớt khỏi manifest
    missing_from_manifest = [f for f in REQUIRED_RAW_FILES if f not in expected_hashes]
    if missing_from_manifest:
        raise DataIntegrityError(f"Manifest checksums.sha256 thiếu các tệp tin bắt buộc: {', '.join(missing_from_manifest)}")
                
    mismatches = []
    verified_files = 0
    for filename in REQUIRED_RAW_FILES:
        expected_hash = expected_hashes[filename]
        filepath = os.path.join(input_dir, filename)
        if not os.path.exists(filepath):
            mismatches.append(f"Missing file on disk: {filename}")
            continue
        actual_hash = calculate_sha256(filepath).lower()
        if actual_hash != expected_hash:
            mismatches.append(f"Mismatch: {filename} (expected {expected_hash[:8]}, got {actual_hash[:8]})")
        else:
            verified_files += 1
            
    if mismatches:
        raise DataIntegrityError(f"Phát hiện lỗi toàn vẹn dữ liệu: {'; '.join(mismatches)}")
        
    return {
        "manifest_found": True,
        "files_expected": len(REQUIRED_RAW_FILES),
        "files_verified": verified_files,
        "required_files": REQUIRED_RAW_FILES,
        "mismatches": mismatches,
        "status": "passed"
    }


def _require(condition, message):
    if not condition:
        raise DataIntegrityError(message)


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DataIntegrityError(f"JSON không hợp lệ: {path}: {exc}") from exc


def validate_raw_dataset(input_dir):
    """Kiểm tra schema và invariant ngữ nghĩa của bộ dữ liệu Chế độ A."""
    manifest = _load_json(os.path.join(input_dir, "environment_manifest.json"))
    _require(
        manifest.get("manifest_category") == "calibrated_synthetic_reference_model",
        "Manifest phải khai báo calibrated_synthetic_reference_model cho Chế độ A",
    )
    provenance = manifest.get("provenance", {})
    _require(provenance.get("generator") == "scripts/generate_reference_dataset.py", "Manifest thiếu generator provenance")
    _require(provenance.get("deterministic") is True, "Dataset Chế độ A phải deterministic")
    _require(provenance.get("empirical") is False, "Dataset Chế độ A không được tự nhận là empirical")
    _require(provenance.get("random_seeds") == {"tc01": 41001, "tc02": 41002, "tc03": 41003, "tc04": 41004}, "Seed provenance không khớp recipe")
    placement = manifest.get("model_parameters", {}).get("tc02a_placement_latency_us", {})
    _require(
        set(placement) == {"cluster_placement_group", "same_az_non_placement", "cross_az_reference"}
        and all(isinstance(value, (int, float)) and value > 0 for value in placement.values()),
        "Manifest thiếu tham số TC-02A placement hợp lệ",
    )
    timestamp = manifest.get("timestamp_utc", "")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DataIntegrityError("timestamp_utc trong manifest không phải ISO-8601") from exc

    tc01_groups = {}
    timestamps = set()
    csv_path = os.path.join(input_dir, "tc01_peering_tgw_samples.csv")
    with open(csv_path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_columns = ["timestamp_ns", "rtt_us", "run_id", "path", "sequence"]
        _require(reader.fieldnames == expected_columns, "TC-01 sai schema cột hoặc thứ tự cột")
        for line_number, row in enumerate(reader, start=2):
            try:
                ts = int(row["timestamp_ns"])
                rtt = float(row["rtt_us"])
                run_id = int(row["run_id"])
                sequence = int(row["sequence"])
            except (TypeError, ValueError) as exc:
                raise DataIntegrityError(f"TC-01 sai kiểu dữ liệu tại dòng {line_number}") from exc
            _require(ts > 0 and ts not in timestamps, f"TC-01 timestamp trùng/không dương tại dòng {line_number}")
            _require(rtt > 0, f"TC-01 RTT phải > 0 tại dòng {line_number}")
            _require(run_id in (1, 2, 3), f"TC-01 run_id ngoài 1..3 tại dòng {line_number}")
            _require(row["path"] in ("vpc_peering", "transit_gateway"), f"TC-01 path không hợp lệ tại dòng {line_number}")
            timestamps.add(ts)
            tc01_groups.setdefault((run_id, row["path"]), []).append(sequence)
    _require(len(timestamps) == 6000, "TC-01 phải có đúng 6.000 observations")
    for key in ((r, p) for r in (1, 2, 3) for p in ("vpc_peering", "transit_gateway")):
        _require(sorted(tc01_groups.get(key, [])) == list(range(1, 1001)), f"TC-01 sequence thiếu/trùng cho {key}")

    tc02 = _load_json(os.path.join(input_dir, "tc02_jumbo_frames_samples.json"))
    _require([r.get("run_id") for r in tc02.get("runs", [])] == [1, 2, 3], "TC-02 phải có run_id 1,2,3")
    for run in tc02["runs"]:
        for condition in ("mtu_1500_seconds", "mtu_9001_seconds"):
            series = run.get(condition, [])
            _require([x.get("second") for x in series] == list(range(1, 11)), f"TC-02 {condition} phải có second 1..10")
            for item in series:
                _require(item.get("throughput_gbps", 0) > 0, "TC-02 throughput phải > 0")
                _require(0 <= item.get("cpu_softirq_percent", -1) <= 100, "TC-02 SoftIRQ ngoài [0,100]")
                _require(item.get("packets_per_second", 0) > 0, "TC-02 PPS phải > 0")
                _require(item.get("retransmits", -1) >= 0, "TC-02 retransmits phải >= 0")

    tc03 = _load_json(os.path.join(input_dir, "tc03_privatelink_samples.json"))
    _require([r.get("run_id") for r in tc03.get("runs", [])] == [1, 2, 3], "TC-03 phải có run_id 1,2,3")
    for run in tc03["runs"]:
        for condition, expected_resolution in (("privatelink", True), ("peering_direct", False)):
            sample = run.get(condition, {})
            rtts = sample.get("rtt_us_samples", [])
            _require(len(rtts) == 500 and all(isinstance(x, (int, float)) and x > 0 for x in rtts), f"TC-03 {condition} cần 500 RTT dương")
            _require(sample.get("throughput_gbps", 0) > 0, f"TC-03 {condition} throughput phải > 0")
            _require(sample.get("nat_cidr_conflict_resolved") is expected_resolution, f"TC-03 {condition} sai invariant CIDR")

    tc04 = _load_json(os.path.join(input_dir, "tc04_xdp_iptables_samples.json"))
    _require([r.get("run_id") for r in tc04.get("runs", [])] == [1, 2, 3], "TC-04 phải có run_id 1,2,3")
    for run in tc04["runs"]:
        for condition in ("iptables_series", "xdp_series"):
            series = run.get(condition, [])
            _require([x.get("second") for x in series] == list(range(1, 31)), f"TC-04 {condition} phải có second 1..30")
            for item in series:
                p50, p99 = item.get("probe_tcp_p50_ms", -1), item.get("probe_tcp_p99_ms", -1)
                _require(0 <= item.get("softirq_percent", -1) <= 100, "TC-04 SoftIRQ ngoài [0,100]")
                _require(item.get("pps_dropped", 0) > 0, "TC-04 dropped PPS phải > 0")
                _require(p50 > 0 and p99 >= p50, "TC-04 yêu cầu P99 >= P50 > 0")

    return {
        "status": "passed",
        "data_mode": manifest["manifest_category"],
        "dataset_version": manifest["manifest_version"],
        "tc02a_placement_latency_us": placement,
        "tc01_observations": 6000,
        "tc02_intervals": 60,
        "tc03_rtt_observations": 3000,
        "tc04_intervals": 180,
        "independent_runs": 3,
    }

def calculate_percentile(data, p):
    """Tính phân vị p (0 <= p <= 100) bằng phương pháp nội suy tuyến tính chuẩn."""
    if not data:
        return 0.0
    sorted_d = sorted(data)
    n = len(sorted_d)
    k = (n - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_d[int(k)]
    return sorted_d[int(f)] * (c - k) + sorted_d[int(c)] * (k - f)

def calculate_stats(data):
    """Tính các đại lượng thống kê mô tả: Mean, Variance, StdDev, SEM, 95% CI, P50, P90, P95, P99."""
    n = len(data)
    if n == 0:
        return {"n": 0, "mean": 0.0, "variance": 0.0, "std_dev": 0.0, "sem": 0.0, "ci_95": [0.0, 0.0]}
    
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / (n - 1) if n > 1 else 0.0
    std_dev = math.sqrt(variance)
    sem = std_dev / math.sqrt(n)
    
    t_crit = 1.96 if n >= 30 else (4.303 if n == 3 else 2.571)
    ci_lower = mean - t_crit * sem
    ci_upper = mean + t_crit * sem
    
    return {
        "n": n,
        "mean": mean,
        "variance": variance,
        "std_dev": std_dev,
        "sem": sem,
        "ci_95": [ci_lower, ci_upper],
        "p50": calculate_percentile(data, 50),
        "p90": calculate_percentile(data, 90),
        "p95": calculate_percentile(data, 95),
        "p99": calculate_percentile(data, 99)
    }

def bootstrap_percentile_ci(data, p=99, num_resamples=10000, alpha=0.05):
    """Tính khoảng tin cậy Bootstrap cho phân vị P99 (10,000 resamples)."""
    n = len(data)
    if n < 10:
        val = calculate_percentile(data, p)
        return [val, val]
    
    boot_stats = []
    for _ in range(num_resamples):
        sample = [random.choice(data) for _ in range(n)]
        boot_stats.append(calculate_percentile(sample, p))
    boot_stats.sort()
    
    low_idx = int((alpha / 2.0) * num_resamples)
    high_idx = int((1.0 - alpha / 2.0) * num_resamples)
    return [boot_stats[low_idx], boot_stats[high_idx]]

def hierarchical_bootstrap_paired_effect(
    run_dict_a,
    run_dict_b,
    statistic="mean",
    num_resamples=10000,
    alpha=0.05,
    effect_name="condition_b_minus_condition_a",
    unit="",
):
    """
    Thuật toán Hierarchical Bootstrap ghép cặp (2 cấp):
    - Cấp 1: Lấy mẫu lại các Run độc lập có hoàn lại (sampling runs with replacement)
    - Cấp 2: Lấy mẫu lại các observation lồng trong từng run được chọn
    - Tính chênh lệch B-A của mean hoặc P99 trong từng run, rồi lấy trung bình run.
    """
    run_ids = sorted(run_dict_a)
    if run_ids != sorted(run_dict_b) or not run_ids:
        raise ValueError("Hai điều kiện phải có cùng tập run_id và không được rỗng")
    if statistic not in ("mean", "p99"):
        raise ValueError("statistic chỉ chấp nhận 'mean' hoặc 'p99'")
    k_runs = len(run_ids)

    def summarize(values):
        return sum(values) / len(values) if statistic == "mean" else calculate_percentile(values, 99)

    run_level_results = []
    for run_id in run_ids:
        value_a = summarize(run_dict_a[run_id])
        value_b = summarize(run_dict_b[run_id])
        run_level_results.append({
            "run_id": run_id,
            "condition_a": value_a,
            "condition_b": value_b,
            "delta_b_minus_a": value_b - value_a,
        })
    
    boot_deltas = []
    for _ in range(num_resamples):
        sampled_runs = [random.choice(run_ids) for _ in range(k_runs)]
        run_deltas = []
        for r_id in sampled_runs:
            obs_a = run_dict_a[r_id]
            obs_b = run_dict_b[r_id]
            sample_a = [random.choice(obs_a) for _ in range(len(obs_a))]
            sample_b = [random.choice(obs_b) for _ in range(len(obs_b))]
            run_deltas.append(summarize(sample_b) - summarize(sample_a))
        boot_deltas.append(sum(run_deltas) / len(run_deltas))
        
    boot_deltas.sort()
    low_idx = int((alpha / 2.0) * num_resamples)
    high_idx = min(num_resamples - 1, int((1.0 - alpha / 2.0) * num_resamples))
    mean_estimate = sum(boot_deltas) / len(boot_deltas)
    
    return {
        "effect_name": effect_name,
        "statistic": statistic,
        "unit": unit,
        "estimate": mean_estimate,
        "ci_95": [boot_deltas[low_idx], boot_deltas[high_idx]],
        "method": "hierarchical_bootstrap",
        "resamples": num_resamples,
        "statistical_unit": "independent_run",
        "independent_runs": k_runs,
        "run_level_results": run_level_results,
    }


def hierarchical_bootstrap_p99_delta(run_dict_a, run_dict_b, num_resamples=10000, alpha=0.05):
    """Compatibility wrapper for TC-01's historical JSON field names."""
    result = hierarchical_bootstrap_paired_effect(
        run_dict_a, run_dict_b, statistic="p99", num_resamples=num_resamples,
        alpha=alpha, effect_name="tgw_minus_peering_p99", unit="ms"
    )
    result["estimate_delta_ms"] = result["estimate"]
    result["ci_95_ms"] = result["ci_95"]
    return result

def _betacf(a, b, x):
    """Phân số liên tục cho hàm incomplete beta (Lentz's method)."""
    MAXIT = 200
    EPS = 3.0e-12
    FPMIN = 1.0e-30

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        del_h = d * c
        h *= del_h
        if abs(del_h - 1.0) <= EPS: break
    return h

def betai(a, b, x):
    """Regularized incomplete beta function."""
    if x < 0.0 or x > 1.0: raise ValueError("x phải nằm trong [0, 1]")
    if x == 0.0: return 0.0
    if x == 1.0: return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    bt = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    else:
        return 1.0 - bt * _betacf(b, a, 1.0 - x) / b

def student_t_two_sided_p_value(t_val, df):
    """Tính exact two-sided p-value của phân phối Student-t với format tránh underflow."""
    if df <= 0: return {"p_value": 1.0, "formatted": "1.000", "numeric_underflow": False}
    x = df / (df + t_val * t_val)
    raw_p = betai(0.5 * df, 0.5, x)
    if raw_p <= 1e-300:
        return {"p_value": None, "formatted": "< 1e-300", "numeric_underflow": True}
    return {"p_value": raw_p, "formatted": f"{raw_p:.8e}", "numeric_underflow": False}

def welch_t_test(sample1, sample2):
    """Thực hiện kiểm định Welch's t-test với định dạng p-value chuẩn học thuật."""
    n1, n2 = len(sample1), len(sample2)
    m1, m2 = sum(sample1) / n1, sum(sample2) / n2
    v1 = sum((x - m1) ** 2 for x in sample1) / (n1 - 1)
    v2 = sum((x - m2) ** 2 for x in sample2) / (n2 - 1)
    
    se_diff = math.sqrt(v1 / n1 + v2 / n2)
    if se_diff == 0:
        return {"t_stat": 0.0, "df": n1 + n2 - 2, "p_value_info": {"formatted": "1.0"}, "cohens_d": 0.0, "diff": 0.0, "interpretation": "exploratory_only_pooled_observations"}
    
    t_stat = (m1 - m2) / se_diff
    df_num = (v1 / n1 + v2 / n2) ** 2
    df_den = ((v1 / n1) ** 2) / (n1 - 1) + ((v2 / n2) ** 2) / (n2 - 1)
    df = df_num / df_den if df_den > 0 else (n1 + n2 - 2)
    
    p_info = student_t_two_sided_p_value(t_stat, df)
    s_pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    cohens_d = (m1 - m2) / s_pooled if s_pooled > 0 else 0.0
    
    return {
        "t_stat": t_stat,
        "df": df,
        "p_value_info": p_info,
        "cohens_d": cohens_d,
        "diff": m1 - m2,
        "interpretation": "exploratory_only_pooled_observations"
    }

def main():
    parser = argparse.ArgumentParser(description="Pipeline phân tích thống kê chuẩn hóa (Scientific Engine)")
    parser.add_argument("--input-dir", type=str, default="", help="Thư mục chứa raw observations")
    parser.add_argument("--output-json", type=str, default="", help="File xuất summary_statistics.json")
    parser.add_argument("--bootstrap-resamples", type=int, default=10000, help="Số lần lấy mẫu Bootstrap (mặc định 10,000)")
    parser.add_argument("--random-seed", type=int, default=42, help="Seed ngẫu nhiên cố định")
    args = parser.parse_args()

    random.seed(args.random_seed)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    input_dir = args.input_dir if args.input_dir else os.path.join(project_root, "results", "raw")
    output_json = args.output_json if args.output_json else os.path.join(project_root, "results", "summary_statistics.json")

    print("================================================================================")
    print("      AWS NETWORK PERFORMANCE - PIPELINE PHÂN TÍCH THỐNG KÊ KHOA HỌC          ")
    print("================================================================================")
    print(f"[*] Thư mục dữ liệu:        {input_dir}")
    print(f"[*] File kết quả xuất:      {output_json}")
    print(f"[*] Bootstrap resamples:    {args.bootstrap_resamples:,}")
    print(f"[*] Random Seed:            {args.random_seed}")

    # 1. Đối soát mã băm toàn vẹn (Checksum Manifest Verification)
    print("\n[*] Đang xác thực toàn vẹn dữ liệu nguồn (SHA256 Manifest Verification)...")
    integrity_result = verify_checksum_manifest(input_dir)
    print(f"[✓] XÁC THỰC THÀNH CÔNG: {integrity_result['files_verified']}/{integrity_result['files_expected']} tệp tin khớp mã băm tuyệt đối.")
    semantic_validation = validate_raw_dataset(input_dir)
    print("[✓] SCHEMA/SEMANTIC VALIDATION: Raw dataset đáp ứng toàn bộ invariant Chế độ A.")

    # --------------------------------------------------------------------------
    # 2. Xử lý TC-01: Phân tích theo từng Run độc lập & Hierarchical Bootstrap
    # --------------------------------------------------------------------------
    tc01_csv = os.path.join(input_dir, "tc01_peering_tgw_samples.csv")
    peering_by_run = {1: [], 2: [], 3: []}
    tgw_by_run = {1: [], 2: [], 3: []}
    peering_all = []
    tgw_all = []

    with open(tc01_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rtt_ms = float(row["rtt_us"]) / 1000.0
            r_id = int(row["run_id"])
            if row["path"] == "vpc_peering":
                peering_by_run[r_id].append(rtt_ms)
                peering_all.append(rtt_ms)
            elif row["path"] == "transit_gateway":
                tgw_by_run[r_id].append(rtt_ms)
                tgw_all.append(rtt_ms)

    # Phân tích theo từng run độc lập (Run-level paired metrics)
    run_level_tc01 = []
    for r in [1, 2, 3]:
        p99_peer = calculate_percentile(peering_by_run[r], 99)
        p99_tgw = calculate_percentile(tgw_by_run[r], 99)
        run_level_tc01.append({
            "run_id": r,
            "peering_p99_ms": p99_peer,
            "tgw_p99_ms": p99_tgw,
            "delta_p99_ms": p99_tgw - p99_peer
        })

    stats_peering = calculate_stats(peering_all)
    stats_tgw = calculate_stats(tgw_all)
    test_tc01 = welch_t_test(peering_all, tgw_all)
    
    # Chạy Hierarchical Bootstrap 10,000 resamples trên 2 cấp
    hierarchical_tc01 = hierarchical_bootstrap_p99_delta(
        peering_by_run, tgw_by_run, num_resamples=args.bootstrap_resamples
    )

    # --------------------------------------------------------------------------
    # 3. Xử lý TC-02: Phân tích MTU 1500 vs MTU 9001 từ JSON time-series
    # --------------------------------------------------------------------------
    tc02_json = os.path.join(input_dir, "tc02_jumbo_frames_samples.json")
    with open(tc02_json, "r", encoding="utf-8") as f:
        tc02_raw = json.load(f)

    mtu1500_softirqs = []
    mtu9001_softirqs = []
    mtu1500_thruputs = []
    mtu9001_thruputs = []
    mtu1500_pps = []
    mtu9001_pps = []
    tc02_by_run = {metric: ({}, {}) for metric in ("softirq", "throughput", "pps")}

    for run in tc02_raw["runs"]:
        run_id = run["run_id"]
        tc02_by_run["softirq"][0][run_id] = []
        tc02_by_run["softirq"][1][run_id] = []
        tc02_by_run["throughput"][0][run_id] = []
        tc02_by_run["throughput"][1][run_id] = []
        tc02_by_run["pps"][0][run_id] = []
        tc02_by_run["pps"][1][run_id] = []
        for sec in run["mtu_1500_seconds"]:
            mtu1500_softirqs.append(sec["cpu_softirq_percent"])
            mtu1500_thruputs.append(sec["throughput_gbps"])
            mtu1500_pps.append(sec["packets_per_second"])
            tc02_by_run["softirq"][0][run_id].append(sec["cpu_softirq_percent"])
            tc02_by_run["throughput"][0][run_id].append(sec["throughput_gbps"])
            tc02_by_run["pps"][0][run_id].append(sec["packets_per_second"])
        for sec in run["mtu_9001_seconds"]:
            mtu9001_softirqs.append(sec["cpu_softirq_percent"])
            mtu9001_thruputs.append(sec["throughput_gbps"])
            mtu9001_pps.append(sec["packets_per_second"])
            tc02_by_run["softirq"][1][run_id].append(sec["cpu_softirq_percent"])
            tc02_by_run["throughput"][1][run_id].append(sec["throughput_gbps"])
            tc02_by_run["pps"][1][run_id].append(sec["packets_per_second"])

    stats_mtu1500_irq = calculate_stats(mtu1500_softirqs)
    stats_mtu9001_irq = calculate_stats(mtu9001_softirqs)
    stats_mtu1500_thru = calculate_stats(mtu1500_thruputs)
    stats_mtu9001_thru = calculate_stats(mtu9001_thruputs)
    stats_mtu1500_pps = calculate_stats(mtu1500_pps)
    stats_mtu9001_pps = calculate_stats(mtu9001_pps)
    test_tc02_irq = welch_t_test(mtu1500_softirqs, mtu9001_softirqs)
    hierarchical_tc02_irq = hierarchical_bootstrap_paired_effect(
        *tc02_by_run["softirq"], statistic="mean", num_resamples=args.bootstrap_resamples,
        effect_name="mtu9001_minus_mtu1500_softirq", unit="percentage_points")
    hierarchical_tc02_throughput = hierarchical_bootstrap_paired_effect(
        *tc02_by_run["throughput"], statistic="mean", num_resamples=args.bootstrap_resamples,
        effect_name="mtu9001_minus_mtu1500_throughput", unit="Gbps")

    # --------------------------------------------------------------------------
    # 4. Xử lý TC-03: Phân tích PrivateLink vs Peering
    # --------------------------------------------------------------------------
    tc03_json = os.path.join(input_dir, "tc03_privatelink_samples.json")
    with open(tc03_json, "r", encoding="utf-8") as f:
        tc03_raw = json.load(f)

    pl_rtts_ms = []
    peer3_rtts_ms = []
    pl_by_run = {}
    peer3_by_run = {}
    for run in tc03_raw["runs"]:
        run_id = run["run_id"]
        pl_by_run[run_id] = [r / 1000.0 for r in run["privatelink"]["rtt_us_samples"]]
        peer3_by_run[run_id] = [r / 1000.0 for r in run["peering_direct"]["rtt_us_samples"]]
        for r in run["privatelink"]["rtt_us_samples"]:
            pl_rtts_ms.append(r / 1000.0)
        for r in run["peering_direct"]["rtt_us_samples"]:
            peer3_rtts_ms.append(r / 1000.0)

    stats_pl_rtt = calculate_stats(pl_rtts_ms)
    stats_peer3_rtt = calculate_stats(peer3_rtts_ms)
    test_tc03 = welch_t_test(pl_rtts_ms, peer3_rtts_ms)
    hierarchical_tc03 = hierarchical_bootstrap_paired_effect(
        peer3_by_run, pl_by_run, statistic="p99", num_resamples=args.bootstrap_resamples,
        effect_name="privatelink_minus_peering_p99", unit="ms")

    # --------------------------------------------------------------------------
    # 5. Xử lý TC-04: Phân tích iptables vs XDP dưới bão UDP Flood
    # --------------------------------------------------------------------------
    tc04_json = os.path.join(input_dir, "tc04_xdp_iptables_samples.json")
    with open(tc04_json, "r", encoding="utf-8") as f:
        tc04_raw = json.load(f)

    iptables_irqs = []
    xdp_irqs = []
    iptables_pps_dropped = []
    xdp_pps_dropped = []
    iptables_probe_p99 = []
    xdp_probe_p99 = []
    tc04_by_run = {metric: ({}, {}) for metric in ("softirq", "pps_drop", "probe_p99")}

    for run in tc04_raw["runs"]:
        run_id = run["run_id"]
        for condition_index in (0, 1):
            for metric in tc04_by_run:
                tc04_by_run[metric][condition_index][run_id] = []
        for sec in run["iptables_series"]:
            iptables_irqs.append(sec["softirq_percent"])
            iptables_pps_dropped.append(sec["pps_dropped"])
            iptables_probe_p99.append(sec["probe_tcp_p99_ms"])
            tc04_by_run["softirq"][0][run_id].append(sec["softirq_percent"])
            tc04_by_run["pps_drop"][0][run_id].append(sec["pps_dropped"])
            tc04_by_run["probe_p99"][0][run_id].append(sec["probe_tcp_p99_ms"])
        for sec in run["xdp_series"]:
            xdp_irqs.append(sec["softirq_percent"])
            xdp_pps_dropped.append(sec["pps_dropped"])
            xdp_probe_p99.append(sec["probe_tcp_p99_ms"])
            tc04_by_run["softirq"][1][run_id].append(sec["softirq_percent"])
            tc04_by_run["pps_drop"][1][run_id].append(sec["pps_dropped"])
            tc04_by_run["probe_p99"][1][run_id].append(sec["probe_tcp_p99_ms"])

    stats_iptables_irq = calculate_stats(iptables_irqs)
    stats_xdp_irq = calculate_stats(xdp_irqs)
    stats_iptables_drop = calculate_stats(iptables_pps_dropped)
    stats_xdp_drop = calculate_stats(xdp_pps_dropped)
    stats_iptables_probe = calculate_stats(iptables_probe_p99)
    stats_xdp_probe = calculate_stats(xdp_probe_p99)
    test_tc04_irq = welch_t_test(iptables_irqs, xdp_irqs)
    test_tc04_probe = welch_t_test(iptables_probe_p99, xdp_probe_p99)
    hierarchical_tc04_irq = hierarchical_bootstrap_paired_effect(
        *tc04_by_run["softirq"], statistic="mean", num_resamples=args.bootstrap_resamples,
        effect_name="xdp_minus_iptables_softirq", unit="percentage_points")
    hierarchical_tc04_pps = hierarchical_bootstrap_paired_effect(
        *tc04_by_run["pps_drop"], statistic="mean", num_resamples=args.bootstrap_resamples,
        effect_name="xdp_minus_iptables_drop_rate", unit="packets_per_second")
    hierarchical_tc04_probe = hierarchical_bootstrap_paired_effect(
        *tc04_by_run["probe_p99"], statistic="mean", num_resamples=args.bootstrap_resamples,
        effect_name="xdp_minus_iptables_interval_p99", unit="ms")

    # --------------------------------------------------------------------------
    # Xuất báo cáo màn hình
    # --------------------------------------------------------------------------
    print("\n[+] TC-01 (VPC Peering vs Transit Gateway - Hierarchical Analysis):")
    print(f"  - Peering P99: {stats_peering['p99']:.4f} ms | TGW P99: {stats_tgw['p99']:.4f} ms")
    print(f"  - Run-level Deltas (TGW - Peering):")
    for r in run_level_tc01:
        print(f"    * Run {r['run_id']}: Peering P99 = {r['peering_p99_ms']:.4f} ms | TGW P99 = {r['tgw_p99_ms']:.4f} ms | Delta = +{r['delta_p99_ms']:.4f} ms")
    print(f"  - Hierarchical Bootstrap Effect Size (10,000 resamples):")
    print(f"    * Estimate Delta: +{hierarchical_tc01['estimate_delta_ms']:.4f} ms")
    print(f"    * 95% CI of Delta: [{hierarchical_tc01['ci_95_ms'][0]:.4f}, {hierarchical_tc01['ci_95_ms'][1]:.4f}] ms")
    print(f"  - Welch t-statistic: {test_tc01['t_stat']:.4f} | Two-sided p-value: {test_tc01['p_value_info']['formatted']}")

    print("\n[+] TC-02 (Jumbo Frames MTU 1500 vs MTU 9001):")
    print(f"  - MTU 1500 SoftIRQ: {stats_mtu1500_irq['mean']:.2f}% | Throughput: {stats_mtu1500_thru['mean']:.2f} Gbps | PPS: {stats_mtu1500_pps['mean']:,.0f}")
    print(f"  - MTU 9001 SoftIRQ: {stats_mtu9001_irq['mean']:.2f}% | Throughput: {stats_mtu9001_thru['mean']:.2f} Gbps | PPS: {stats_mtu9001_pps['mean']:,.0f}")
    print(f"  - Giảm SoftIRQ: {abs(test_tc02_irq['diff']):.2f}% | p-value: {test_tc02_irq['p_value_info']['formatted']}")

    print("\n[+] TC-03 (AWS PrivateLink vs VPC Peering):")
    print(f"  - PrivateLink Mean RTT: {stats_pl_rtt['mean']:.4f} ms | P99: {stats_pl_rtt['p99']:.4f} ms")
    print(f"  - VPC Peering Mean RTT: {stats_peer3_rtt['mean']:.4f} ms | P99: {stats_peer3_rtt['p99']:.4f} ms")
    print(f"  - Chênh lệch NLB Proxy: +{test_tc03['diff']:.4f} ms | p-value: {test_tc03['p_value_info']['formatted']}")

    print("\n[+] TC-04 (Kernel-Bypass eBPF/XDP vs iptables under UDP Flood):")
    print(f"  - iptables SoftIRQ: {stats_iptables_irq['mean']:.2f}% | Drop PPS: {stats_iptables_drop['mean']:,.0f} | Legitimate Probe P99: {stats_iptables_probe['mean']:.3f} ms")
    print(f"  - eBPF/XDP SoftIRQ: {stats_xdp_irq['mean']:.2f}% | Drop PPS: {stats_xdp_drop['mean']:,.0f} | Legitimate Probe P99: {stats_xdp_probe['mean']:.3f} ms")
    print(f"  - SoftIRQ Giảm: {stats_iptables_irq['mean'] - stats_xdp_irq['mean']:.2f}% | p-value: {test_tc04_irq['p_value_info']['formatted']}")

    # --------------------------------------------------------------------------
    # 6. Tạo file kết quả cấu trúc JSON duy nhất (Single Source of Truth)
    # --------------------------------------------------------------------------
    summary_data = {
        "metadata": {
            "generator": "analyze_results.py (Scientific Hierarchical Engine)",
            "data_mode": "CALIBRATED_SYNTHETIC_REFERENCE_BENCHMARK",
            "dataset_version": semantic_validation["dataset_version"],
            "statistical_unit": "independent_run",
            "integrity_verification": integrity_result,
            "semantic_validation": semantic_validation,
            "bootstrap_parameters": {
                "method": "hierarchical_percentile",
                "resamples": args.bootstrap_resamples,
                "confidence_level": 0.95,
                "random_seed": args.random_seed
            },
            "softirq_measurement": {
                "formula": "100.0 * (softirq_after - softirq_before) / (total_jiffies_after - total_jiffies_before)",
                "telemetry_sources": [
                    "/proc/stat (cpu softirq column 7 and total jiffies sum)",
                    "/proc/softirqs (NET_RX + NET_TX)"
                ],
                "sampling_window": "Synchronized strictly with load generator window on DUT (T1 to T6)"
            },
            "statistical_framework": {
                "primary_effects": "run_aware_paired_hierarchical_bootstrap for TC01-TC04 (independent_run N=3)",
                "exploratory_tests": "pooled_welch_t_test",
                "pseudoreplication_mitigation": "Run-level paired analysis and two-level hierarchical resampling"
            }
        },
        "tc01_peering_tgw": {
            "statistical_unit": "independent_run (N=3)",
            "observation_count": len(peering_all) + len(tgw_all),
            "run_level_results": run_level_tc01,
            "hierarchical_p99_effect": hierarchical_tc01,
            "peering": stats_peering,
            "transit_gateway": stats_tgw,
            "welch_t_test": test_tc01
        },
        "tc02a_placement_reference": {
            "data_mode": "synthetic_static_reference",
            "latency_us": semantic_validation["tc02a_placement_latency_us"],
            "empirical": False
        },
        "tc02_jumbo_frames": {
            "statistical_unit": "independent_run (N=3)",
            "mtu_1500": {
                "softirq": stats_mtu1500_irq,
                "throughput_gbps": stats_mtu1500_thru,
                "pps": stats_mtu1500_pps
            },
            "mtu_9001": {
                "softirq": stats_mtu9001_irq,
                "throughput_gbps": stats_mtu9001_thru,
                "pps": stats_mtu9001_pps
            },
            "welch_softirq": test_tc02_irq,
            "hierarchical_softirq_effect": hierarchical_tc02_irq,
            "hierarchical_throughput_effect": hierarchical_tc02_throughput
        },
        "tc03_privatelink": {
            "statistical_unit": "independent_run (N=3)",
            "privatelink": { "rtt": stats_pl_rtt },
            "peering": { "rtt": stats_peer3_rtt },
            "welch_rtt": test_tc03,
            "hierarchical_p99_effect": hierarchical_tc03,
            "cidr_conflict_resolved": True
        },
        "tc04_ebpf_xdp": {
            "statistical_unit": "independent_run (N=3)",
            "iptables": {
                "softirq": stats_iptables_irq,
                "pps_drop": stats_iptables_drop,
                "interval_p99_latency_ms": stats_iptables_probe
            },
            "xdp_native": {
                "softirq": stats_xdp_irq,
                "pps_drop": stats_xdp_drop,
                "interval_p99_latency_ms": stats_xdp_probe
            },
            "welch_softirq": test_tc04_irq,
            "welch_probe_latency": test_tc04_probe,
            "hierarchical_softirq_effect": hierarchical_tc04_irq,
            "hierarchical_drop_rate_effect": hierarchical_tc04_pps,
            "hierarchical_probe_latency_effect": hierarchical_tc04_probe
        }
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print(f"\n[✔] ĐÃ XUẤT THÀNH CÔNG BÁO CÁO THỐNG KÊ TỔNG HỢP: {output_json}")
    print("[✔] ALL PRIMARY EFFECTS USE RUN-AWARE PAIRED HIERARCHICAL BOOTSTRAP (INDEPENDENT RUNS N=3). ALL POOLED WELCH RESULTS ARE EXPLORATORY ONLY.")

if __name__ == "__main__":
    main()
