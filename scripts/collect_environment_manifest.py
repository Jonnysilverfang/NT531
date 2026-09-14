#!/usr/bin/env python3
"""Collect a best-effort, machine-readable environment snapshot for Mode B."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def command(*args: str) -> dict[str, object]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return {
            "argv": list(args),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": list(args), "returncode": None, "stdout": "", "stderr": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--availability-zone", default="unknown")
    parser.add_argument("--instance-id", default="unknown")
    parser.add_argument("--instance-type", default="unknown")
    parser.add_argument("--ami-id", default="unknown")
    args = parser.parse_args()

    evidence = {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "region": args.region,
        "availability_zone": args.availability_zone,
        "instance_id": args.instance_id,
        "instance_type": args.instance_type,
        "ami_id": args.ami_id,
        "platform": platform.platform(),
        "cpu_count": __import__("os").cpu_count(),
        "commands": {
            "uname": command("uname", "-a"),
            "lscpu": command("lscpu"),
            "memory": command("free", "-b"),
            "interface": command("ip", "-details", "link", "show", "dev", args.interface),
            "ena_driver": command("ethtool", "-i", args.interface),
            "offloads": command("ethtool", "-k", args.interface),
            "congestion_control": command("sysctl", "net.ipv4.tcp_congestion_control"),
            "irq_affinity": command("sh", "-c", "grep -i eth /proc/interrupts || true"),
            "iperf3_version": command("iperf3", "--version"),
            "sockperf_version": command("sockperf", "--version"),
            "bpftool_version": command("bpftool", "version"),
            "clang_version": command("clang", "--version"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
