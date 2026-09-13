#!/usr/bin/env python3
"""Generate the deterministic Mode-A dataset. Never contacts AWS or loads XDP."""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path


DATASET_VERSION = "3.0.0"
CREATED_UTC = "2026-09-07T04:15:00Z"
SEEDS = {"tc01": 41001, "tc02": 41002, "tc03": 41003, "tc04": 41004}
RAW_FILES = (
    "environment_manifest.json", "tc01_peering_tgw_samples.csv",
    "tc02_jumbo_frames_samples.json", "tc03_privatelink_samples.json",
    "tc04_xdp_iptables_samples.json",
)


def rounded_gauss(rng, mean, stddev, digits, minimum=0.001):
    return round(max(minimum, rng.gauss(mean, stddev)), digits)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def manifest():
    return {
        "manifest_version": DATASET_VERSION,
        "project": "aws-network-performance-capstone",
        "manifest_category": "calibrated_synthetic_reference_model",
        "timestamp_utc": CREATED_UTC,
        "provenance": {
            "generator": "scripts/generate_reference_dataset.py",
            "generator_version": DATASET_VERSION,
            "deterministic": True,
            "random_seeds": SEEDS,
            "calibration_scope": "Declared illustrative targets for pipeline verification; not fitted to AWS telemetry",
            "empirical": False,
        },
        "region": "ap-southeast-2",
        "region_name": "Asia Pacific (Sydney) reference topology",
        "data_integrity_notice": "Deterministic synthetic observations for offline methodology verification; not AWS measurements.",
        "assumed_reference_environment": {
            "instance_type": "c6i.large", "vcpu_count": 2, "memory_gib": 4,
            "hypervisor": "AWS Nitro System", "nic": "AWS Elastic Network Adapter (ENA)",
            "ena_driver_expected": "amzn_ena_2.10.0g", "maximum_network_allowance_gbps": 12.5,
        },
        "model_parameters": {
            "distribution": "independent truncated Gaussian within each run; run offsets explicitly encoded in generator",
            "tc01_rtt_us": {"peering_mean": 173, "peering_sd": 14, "tgw_mean": 809, "tgw_sd": 72},
            "tc02": {"mtu1500_gbps": 3.20, "mtu9001_gbps": 4.85, "softirq_percent": [68.0, 22.1]},
            "tc02a_placement_latency_us": {
                "cluster_placement_group": 92.4,
                "same_az_non_placement": 173.4,
                "cross_az_reference": 985.0,
            },
            "tc03_rtt_us": {"peering_mean": 174, "privatelink_mean": 510},
            "tc04": {"iptables_softirq": 84.6, "xdp_softirq": 4.22, "offered_load_pps": 5_000_000},
        },
        "hardware_verification_commands": [
            "ethtool -i eth0", "ethtool -S eth0", "uname -r",
            "ip -details link show dev eth0", "bpftool net show dev eth0",
        ],
    }


def generate_tc01(path):
    rng = random.Random(SEEDS["tc01"])
    base_timestamp = 1788752400000000000
    serial = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["timestamp_ns", "rtt_us", "run_id", "path", "sequence"])
        for run_id in (1, 2, 3):
            for path_name, mean, sd in (
                ("vpc_peering", 173 + (run_id - 2) * 1.5, 14),
                ("transit_gateway", 809 + (run_id - 2) * 8, 72),
            ):
                for sequence in range(1, 1001):
                    serial += 1
                    writer.writerow([base_timestamp + serial * 1_000_000,
                                     rounded_gauss(rng, mean, sd, 2), run_id, path_name, sequence])


def generate_tc02(path):
    rng = random.Random(SEEDS["tc02"])
    result = {"test_case": "TC-02", "data_source": "deterministic_synthetic_reference",
              "name": "Jumbo Frames MTU 1500 vs MTU 9001", "runs": []}
    for run_id in (1, 2, 3):
        run = {"run_id": run_id, "mtu_1500_seconds": [], "mtu_9001_seconds": []}
        offset = (run_id - 2) * 0.015
        for second in range(1, 11):
            run["mtu_1500_seconds"].append({
                "second": second, "throughput_gbps": rounded_gauss(rng, 3.20 + offset, .055, 3),
                "cpu_softirq_percent": rounded_gauss(rng, 68.0 + offset * 5, .95, 2),
                "packets_per_second": int(round(rng.gauss(261_600, 3_000))),
                "retransmits": rng.randrange(0, 5),
            })
            run["mtu_9001_seconds"].append({
                "second": second, "throughput_gbps": rounded_gauss(rng, 4.85 + offset, .05, 3),
                "cpu_softirq_percent": rounded_gauss(rng, 22.1 + offset * 3, .58, 2),
                "packets_per_second": int(round(rng.gauss(67_250, 820))),
                "retransmits": rng.randrange(0, 2),
            })
        result["runs"].append(run)
    write_json(path, result)


def generate_tc03(path):
    rng = random.Random(SEEDS["tc03"])
    result = {"test_case": "TC-03", "data_source": "deterministic_synthetic_reference",
              "name": "Overlapping CIDR reference: PrivateLink vs Peering", "runs": []}
    for run_id in (1, 2, 3):
        offset = (run_id - 2) * 4
        result["runs"].append({
            "run_id": run_id,
            "privatelink": {
                "rtt_us_samples": [rounded_gauss(rng, 510 + offset, 42, 2) for _ in range(500)],
                "throughput_gbps": rounded_gauss(rng, 4.35, .05, 3),
                "nat_cidr_conflict_resolved": True,
            },
            "peering_direct": {
                "rtt_us_samples": [rounded_gauss(rng, 174 + offset / 4, 14, 2) for _ in range(500)],
                "throughput_gbps": rounded_gauss(rng, 4.8, .05, 3),
                "nat_cidr_conflict_resolved": False,
            },
        })
    write_json(path, result)


def generate_tc04(path):
    rng = random.Random(SEEDS["tc04"])
    result = {"test_case": "TC-04", "data_source": "deterministic_synthetic_reference",
              "name": "XDP native-hook methodology model vs iptables under UDP load",
              "roles": {"dut_receiver": "synthetic DUT ingress UDP:5201 and TCP probe:5202",
                        "load_generator": "synthetic 5 Mpps offered load"}, "runs": []}
    for run_id in (1, 2, 3):
        run = {"run_id": run_id, "iptables_series": [], "xdp_series": []}
        offset = (run_id - 2) * .12
        for second in range(1, 31):
            ipt_p50 = rounded_gauss(rng, 1.85, .18, 3)
            xdp_p50 = rounded_gauss(rng, .19, .012, 3)
            run["iptables_series"].append({
                "second": second, "softirq_percent": rounded_gauss(rng, 84.6 + offset, 1.1, 2),
                "pps_dropped": int(round(rng.gauss(1_150_000, 32_000))),
                "probe_tcp_p50_ms": ipt_p50,
                "probe_tcp_p99_ms": max(ipt_p50, rounded_gauss(rng, 14.71 + offset, 1.25, 3)),
            })
            run["xdp_series"].append({
                "second": second, "softirq_percent": rounded_gauss(rng, 4.22 + offset / 10, .30, 2),
                "pps_dropped": int(round(rng.gauss(4_950_000, 24_000))),
                "probe_tcp_p50_ms": xdp_p50,
                "probe_tcp_p99_ms": max(xdp_p50, rounded_gauss(rng, .347, .03, 3)),
            })
        result["runs"].append(run)
    write_json(path, result)


def generate(output_dir, overwrite=False):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    occupied = [name for name in (*RAW_FILES, "checksums.sha256") if (output_dir / name).exists()]
    if occupied and not overwrite:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(occupied))
    write_json(output_dir / "environment_manifest.json", manifest())
    generate_tc01(output_dir / "tc01_peering_tgw_samples.csv")
    generate_tc02(output_dir / "tc02_jumbo_frames_samples.json")
    generate_tc03(output_dir / "tc03_privatelink_samples.json")
    generate_tc04(output_dir / "tc04_xdp_iptables_samples.json")
    lines = []
    for name in RAW_FILES:
        digest = hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (output_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {name: lines[index].split()[0] for index, name in enumerate(RAW_FILES)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    generated = generate(args.output_dir, args.overwrite)
    print(json.dumps({"data_mode": "synthetic_reference", "empirical": False,
                      "files": generated}, indent=2))


if __name__ == "__main__":
    main()
