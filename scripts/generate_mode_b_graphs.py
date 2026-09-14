#!/usr/bin/env python3
"""Generate the four registered Mode B figures from a validated final summary."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


GRAPH_NAMES = (
    "tc01_latency.png",
    "tc02_mtu_throughput.png",
    "tc02_softirq.png",
    "tc03_xdp_saturation.png",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_summary(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(data.get("data_mode") == "empirical_aws" and data.get("empirical") is True,
            "graphs require validated empirical AWS evidence")
    require(data.get("profile") == "final" and int(data.get("n_runs", 0)) >= 10,
            "final graphs require the final profile with at least 10 runs")
    require(all(name in data for name in ("tc01", "tc02", "tc03")),
            "summary must contain exactly the registered test groups")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        summary = load_summary(args.summary)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name in GRAPH_NAMES:
            require(not (args.output_dir / name).exists(), f"refusing to overwrite graph: {name}")

        colors = {"peering": "#2563eb", "tgw": "#dc2626", "iptables": "#d97706", "xdp": "#059669"}

        metrics = ["p50_ms", "p95_ms", "p99_ms"]
        x = np.arange(len(metrics))
        width = 0.36
        fig, ax = plt.subplots(figsize=(8, 5))
        for index, condition in enumerate(("peering", "tgw")):
            values = [summary["tc01"]["conditions"][condition][metric]["mean"] for metric in metrics]
            ax.bar(x + (index - 0.5) * width, values, width, label=condition.upper(), color=colors[condition])
        ax.set_xticks(x, [name.replace("_ms", "").upper() for name in metrics])
        ax.set_ylabel("RTT (ms)")
        ax.set_title("TC01: Peering vs Transit Gateway latency")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(args.output_dir / GRAPH_NAMES[0], dpi=180)
        plt.close(fig)

        streams = [1, 4, 8]
        fig, ax = plt.subplots(figsize=(8, 5))
        for mtu, marker in ((1500, "o"), (9001, "s")):
            values = [summary["tc02"]["cells"][f"mtu_{mtu}_p{p}"]["throughput_gbps"]["mean"] for p in streams]
            ax.plot(streams, values, marker=marker, linewidth=2, label=f"MTU {mtu}")
        ax.set_xlabel("Parallel iperf3 streams")
        ax.set_ylabel("Throughput (Gbps)")
        ax.set_title("TC02: MTU × streams throughput")
        ax.set_xticks(streams)
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(args.output_dir / GRAPH_NAMES[1], dpi=180)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5))
        for mtu, marker in ((1500, "o"), (9001, "s")):
            values = [summary["tc02"]["cells"][f"mtu_{mtu}_p{p}"]["softirq_percent"]["mean"] for p in streams]
            ax.plot(streams, values, marker=marker, linewidth=2, label=f"MTU {mtu}")
        ax.set_xlabel("Parallel iperf3 streams")
        ax.set_ylabel("DUT SoftIRQ CPU (%)")
        ax.set_title("TC02: SoftIRQ cost")
        ax.set_xticks(streams)
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(args.output_dir / GRAPH_NAMES[2], dpi=180)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5))
        for condition in ("iptables", "xdp"):
            by_load: dict[int, list[float]] = {}
            for events in summary["tc03"]["load_curves"][condition].values():
                for event in events:
                    by_load.setdefault(int(event["load_target_pps"]), []).append(
                        float(event["saturation"]["dut_ena_rx_pps"])
                    )
            loads = sorted(by_load)
            achieved = [statistics.fmean(by_load[load]) for load in loads]
            ax.plot(loads, achieved, marker="o", linewidth=2, label=condition.upper(), color=colors[condition])
        ax.plot([0, max(ax.get_xlim()[1], 1)], [0, max(ax.get_xlim()[1], 1)], linestyle="--", color="#6b7280", label="offered = received")
        ax.set_xlabel("Target offered load (PPS)")
        ax.set_ylabel("DUT ENA RX (PPS)")
        ax.set_title("TC03: iptables vs native XDP saturation")
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(args.output_dir / GRAPH_NAMES[3], dpi=180)
        plt.close(fig)

        metadata = {
            "schema_version": 1,
            "source_summary": str(args.summary),
            "experiment_id": summary["experiment_id"],
            "graphs": list(GRAPH_NAMES),
        }
        (args.output_dir / "graph_manifest.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (ImportError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"MODE_B_GRAPH_ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"MODE_B_GRAPHS=PASS output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
