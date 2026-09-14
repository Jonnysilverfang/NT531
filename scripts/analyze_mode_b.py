#!/usr/bin/env python3
"""Mode B analyzer: run-tree schema, paired deltas, hierarchical bootstrap, saturation detection."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def verify_checksums(run_dir: Path) -> bool:
    """Verify SHA256 checksums for run artifacts."""
    checksum_file = run_dir / "checksums.sha256"
    if not checksum_file.exists():
        print(f"Missing checksums.sha256 in {run_dir}", file=sys.stderr)
        return False
    
    with open(checksum_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            expected_hash, filename = line.split(None, 1)
            filepath = run_dir / filename
            if not filepath.exists():
                print(f"Missing file: {filepath}", file=sys.stderr)
                return False
            actual_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                print(f"Checksum mismatch: {filepath}", file=sys.stderr)
                return False
    return True


def load_tc01_run(run_dir: Path) -> dict[str, Any] | None:
    """Load TC-01 peering vs TGW latency data from a single run."""
    tc01_dir = run_dir / "tc01"
    if not tc01_dir.exists():
        return None
    
    peering_file = tc01_dir / "peering" / "latency.txt"
    tgw_file = tc01_dir / "tgw" / "latency.txt"
    
    if not (peering_file.exists() and tgw_file.exists()):
        return None
    
    def parse_sockperf_p99(filepath: Path) -> float:
        """Extract P99 RTT from sockperf output."""
        with open(filepath) as f:
            for line in f:
                if "percentile 99.000" in line:
                    return float(line.split()[2])
        return 0.0
    
    peering_p99 = parse_sockperf_p99(peering_file)
    tgw_p99 = parse_sockperf_p99(tgw_file)
    
    return {
        "peering_p99_ms": peering_p99,
        "tgw_p99_ms": tgw_p99,
        "delta_p99_ms": tgw_p99 - peering_p99
    }


def load_tc04_saturation(run_dir: Path) -> list[dict[str, Any]]:
    """Load TC-04 saturation events."""
    sat_file = run_dir / "tc04" / "saturation_events.jsonl"
    if not sat_file.exists():
        return []
    
    events = []
    with open(sat_file) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def hierarchical_bootstrap(run_deltas: list[float], n_resamples: int = 10000, seed: int = 42) -> dict[str, float]:
    """Hierarchical bootstrap: resample runs, compute CI."""
    rng = np.random.default_rng(seed)
    deltas = np.array(run_deltas)
    bootstrap_means = []
    
    for _ in range(n_resamples):
        sample = rng.choice(deltas, size=len(deltas), replace=True)
        bootstrap_means.append(sample.mean())
    
    bootstrap_means = np.array(bootstrap_means)
    return {
        "mean": float(deltas.mean()),
        "ci_lower": float(np.percentile(bootstrap_means, 2.5)),
        "ci_upper": float(np.percentile(bootstrap_means, 97.5))
    }


def detect_saturation_point(events: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    """Find first saturation event for a given condition."""
    condition_events = [e for e in events if e.get("condition") == condition]
    saturated = [e for e in condition_events if e.get("saturation", {}).get("saturated")]
    
    if saturated:
        first = saturated[0]
        return {
            "saturated": True,
            "load_pps": first["load_target"],
            "reason": first["saturation"].get("reason", ""),
            "loss_pct": first["saturation"].get("loss_pct", 0),
            "p99_ms": first["saturation"].get("p99_ms", 0),
            "cpu_pct": first["saturation"].get("cpu_pct", 0)
        }
    
    return {"saturated": False}


def analyze_experiment(experiment_dir: Path, output_json: Path) -> None:
    """Analyze all runs in a Mode B experiment directory."""
    run_dirs = sorted([d for d in experiment_dir.iterdir() if d.is_dir() and d.name.startswith("run_")])
    
    if not run_dirs:
        print(f"No runs found in {experiment_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(run_dirs)} runs", file=sys.stderr)
    
    # Verify checksums
    for run_dir in run_dirs:
        if not verify_checksums(run_dir):
            print(f"Checksum verification failed for {run_dir}", file=sys.stderr)
            sys.exit(1)
    
    # TC-01: Paired deltas per run
    tc01_deltas = []
    for run_dir in run_dirs:
        tc01_data = load_tc01_run(run_dir)
        if tc01_data:
            tc01_deltas.append(tc01_data["delta_p99_ms"])
    
    tc01_result = {}
    if tc01_deltas:
        tc01_result = hierarchical_bootstrap(tc01_deltas)
        tc01_result["n_runs"] = len(tc01_deltas)
    
    # TC-04: Saturation detection
    all_saturation_events = []
    for run_dir in run_dirs:
        all_saturation_events.extend(load_tc04_saturation(run_dir))
    
    tc04_result = {
        "iptables": detect_saturation_point(all_saturation_events, "iptables"),
        "xdp": detect_saturation_point(all_saturation_events, "xdp")
    }
    
    summary = {
        "experiment_id": experiment_dir.name,
        "n_runs": len(run_dirs),
        "tc01_peering_vs_tgw": tc01_result,
        "tc04_saturation": tc04_result
    }
    
    output_json.write_text(json.dumps(summary, indent=2))
    print(f"Analysis complete: {output_json}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Mode B experiment runs")
    parser.add_argument("--experiment-dir", type=Path, required=True, help="Path to experiment directory")
    parser.add_argument("--output-json", type=Path, required=True, help="Output summary JSON")
    parser.add_argument("--bootstrap-resamples", type=int, default=10000)
    parser.add_argument("--random-seed", type=int, default=42)
    
    args = parser.parse_args()
    
    if not args.experiment_dir.exists():
        print(f"Experiment directory not found: {args.experiment_dir}", file=sys.stderr)
        sys.exit(1)
    
    analyze_experiment(args.experiment_dir, args.output_json)


if __name__ == "__main__":
    main()
