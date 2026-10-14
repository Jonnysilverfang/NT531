#!/usr/bin/env python3
"""Build the primary report figures directly from the confirmation raw data."""

import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "img" / "chapter3" / "primary"
OUT.mkdir(parents=True, exist_ok=True)

BLUE = "#146C94"
ORANGE = "#D97706"
GREEN = "#15803D"
RED = "#B91C1C"
INK = "#172033"
GRID = "#D8DEE9"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "axes.edgecolor": "#667085",
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "figure.facecolor": "white",
        "axes.facecolor": "#FBFCFE",
    }
)


def save(fig, name):
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def style(ax):
    ax.grid(True, axis="y", color=GRID, linewidth=0.7, alpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)


def ping_values(capture):
    values = []
    for run in capture["runs"]:
        values.extend(float(x) for x in re.findall(r"time=([0-9.]+) ms", run["stdout"]))
    return values


def rtt_figure():
    analysis = json.loads((ROOT / "results/confirmation-rtt-v1/analysis.json").read_text(encoding="utf-8"))
    rows = analysis["rows"]
    raw = {"peering": [], "tgw": []}
    for mode in raw:
        for path in sorted((ROOT / "results/confirmation-rtt-v1").glob(f"block-*/*/{mode}/capture.json")):
            raw[mode].extend(ping_values(json.loads(path.read_text(encoding="utf-8"))))
    assert len(rows) == 5
    assert len(raw["peering"]) == len(raw["tgw"]) == 1500

    blocks = [row["block"] for row in rows]
    peering = [row["peering_ms"] for row in rows]
    tgw = [row["tgw_ms"] for row in rows]
    delta = [row["difference_ms"] for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.8), gridspec_kw={"width_ratios": [1.2, 1.15, 1]})
    fig.suptitle("RTT xác nhận cùng cohort: 5 block, 3.000/3.000 phản hồi", fontsize=14, fontweight="bold", y=1.04)

    ax = axes[0]
    ax.plot(blocks, peering, "o-", color=BLUE, linewidth=2.2, label="Peering")
    ax.plot(blocks, tgw, "o-", color=ORANGE, linewidth=2.2, label="TGW")
    for x, a, b in zip(blocks, peering, tgw):
        ax.vlines(x, a, b, color="#98A2B3", linewidth=1, alpha=0.7)
    ax.set(title="Trung bình theo block", xlabel="Block", ylabel="RTT (ms)", xticks=blocks)
    ax.legend(frameon=False, loc="upper left")
    style(ax)

    ax = axes[1]
    for mode, color, label in [("peering", BLUE, "Peering"), ("tgw", ORANGE, "TGW")]:
        x = np.sort(raw[mode])
        y = np.arange(1, len(x) + 1) / len(x)
        ax.step(x, y, where="post", color=color, linewidth=2.1, label=f"{label} (n={len(x)})")
    ax.set(title="Phân phối 1.500 RTT mỗi mode", xlabel="RTT từng probe (ms)", ylabel="ECDF", ylim=(0, 1.02))
    ax.legend(frameon=False, loc="lower right")
    style(ax)

    ax = axes[2]
    bars = ax.bar(blocks, delta, color=[BLUE if d < np.mean(delta) else ORANGE for d in delta], width=0.65)
    ax.axhline(np.mean(delta), color=RED, linestyle="--", linewidth=1.7, label=f"Mean = {np.mean(delta):.4f} ms")
    ax.bar_label(bars, labels=[f"{d:.3f}" for d in delta], padding=3, fontsize=8)
    ax.set(title="Hiệu ứng ghép cặp TGW - Peering", xlabel="Block", ylabel="Chênh lệch RTT (ms)", xticks=blocks, ylim=(0, max(delta) * 1.25))
    ax.legend(frameon=False, loc="upper left")
    style(ax)
    fig.tight_layout()
    save(fig, "rtt-confirmation-dashboard.png")


def slots_data():
    analysis = json.loads((ROOT / "results/application-slots-confirmation-v1/analysis.json").read_text(encoding="utf-8"))
    rows = []
    for block in analysis["rows"]:
        for row in block["rows"]:
            workers = row["workers"]
            rows.append(
                {
                    "block": block["block"],
                    "mode": row["mode"],
                    "slots": row["slots"],
                    "rate": row["rate_rps"],
                    "deadline": 100 * row["deadline_success_fraction"],
                    "p95": row["successful_completion_p95_ms"],
                    "queue_p95": np.mean([worker["queue_wait_p95_ms"] for worker in workers]),
                    "service_p95": np.mean([worker["service_p95_ms"] for worker in workers]),
                }
            )
    assert len(rows) == 24
    assert sum(row["scheduled"] for block in analysis["rows"] for row in block["rows"]) == 252_000
    return rows


def aggregate(rows, field):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["mode"], row["slots"], row["rate"])].append(row[field])
    return {key: (np.mean(values), np.min(values), np.max(values)) for key, values in grouped.items()}


def deadline_figure(rows):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.1), gridspec_kw={"width_ratios": [1.1, 1.4]})
    fig.suptitle("Deadline 50 ms: hiệu ứng số slots lớn hơn hiệu ứng đường mạng", fontsize=14, fontweight="bold", y=1.03)

    ax = axes[0]
    labels = ["Peering\n8 slots", "TGW\n8 slots", "Peering\n16 slots", "TGW\n16 slots"]
    keys = [("peering", 8), ("tgw", 8), ("peering", 16), ("tgw", 16)]
    agg = aggregate(rows, "deadline")
    x = np.arange(len(labels))
    width = 0.34
    for offset, rate, color in [(-width / 2, 600, GREEN), (width / 2, 800, RED)]:
        vals = [agg[(mode, slots, rate)][0] for mode, slots in keys]
        bars = ax.bar(x + offset, vals, width, color=color, label=f"{rate} request/s")
        ax.bar_label(bars, labels=[f"{v:.1f}%" for v in vals], padding=3, fontsize=8)
    ax.axhline(100, color="#98A2B3", linewidth=0.8)
    ax.set(title="Tỷ lệ request đúng hạn", ylabel="Đúng hạn (%)", xticks=x, xticklabels=labels, ylim=(0, 112))
    ax.legend(frameon=False, loc="lower right")
    style(ax)

    ax = axes[1]
    blocks = [1, 2, 3]
    series = [
        ("peering", 8, BLUE, "o", "Peering, 8 slots"),
        ("tgw", 8, ORANGE, "o", "TGW, 8 slots"),
        ("peering", 16, GREEN, "s", "Peering, 16 slots"),
        ("tgw", 16, RED, "s", "TGW, 16 slots"),
    ]
    for mode, slots, color, marker, label in series:
        vals = [next(r["deadline"] for r in rows if r["block"] == b and r["mode"] == mode and r["slots"] == slots and r["rate"] == 800) for b in blocks]
        ax.plot(blocks, vals, marker=marker, linewidth=2, color=color, label=label)
    ax.set(title="Khả năng lặp lại ở 800 request/s", xlabel="Block", ylabel="Đúng hạn (%)", xticks=blocks, ylim=(0, 104))
    ax.legend(frameon=False, ncol=2, fontsize=8, loc="center right")
    style(ax)
    fig.tight_layout()
    save(fig, "application-deadline.png")


def latency_queue_figure(rows):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.4))
    fig.suptitle("P95 tăng do chờ hàng đợi, không do thời gian phục vụ", fontsize=14, fontweight="bold", y=1.03)
    keys = [("peering", 8), ("tgw", 8), ("peering", 16), ("tgw", 16)]
    labels = ["Peering\n8 slots", "TGW\n8 slots", "Peering\n16 slots", "TGW\n16 slots"]
    x = np.arange(len(keys))

    ax = axes[0]
    agg = aggregate(rows, "p95")
    for offset, rate, color in [(-0.17, 600, GREEN), (0.17, 800, RED)]:
        means = [agg[(m, s, rate)][0] for m, s in keys]
        lows = [means[i] - agg[(m, s, rate)][1] for i, (m, s) in enumerate(keys)]
        highs = [agg[(m, s, rate)][2] - means[i] for i, (m, s) in enumerate(keys)]
        ax.errorbar(x + offset, means, yerr=[lows, highs], fmt="o", markersize=7, capsize=5, linewidth=2, color=color, label=f"{rate} request/s")
    ax.axhline(50, color=ORANGE, linestyle="--", linewidth=1.5, label="Deadline 50 ms")
    ax.set_yscale("log")
    ax.set(title="P95 end-to-end, mean và min-max", ylabel="P95 (ms, log scale)", xticks=x, xticklabels=labels)
    ax.legend(frameon=False, fontsize=8)
    style(ax)

    ax = axes[1]
    queue = aggregate([r for r in rows if r["rate"] == 800], "queue_p95")
    service = aggregate([r for r in rows if r["rate"] == 800], "service_p95")
    q_means = [queue[(m, s, 800)][0] for m, s in keys]
    s_means = [service[(m, s, 800)][0] for m, s in keys]
    ax.bar(x - 0.17, q_means, 0.34, color=RED, label="P95 chờ slot")
    ax.bar(x + 0.17, s_means, 0.34, color=BLUE, label="P95 phục vụ")
    ax.set_yscale("log")
    ax.set(title="Worker tại 800 request/s", ylabel="Thời gian (ms, log scale)", xticks=x, xticklabels=labels)
    ax.legend(frameon=False, fontsize=8)
    style(ax)
    fig.tight_layout()
    save(fig, "application-latency-queue.png")


if __name__ == "__main__":
    rtt_figure()
    rows = slots_data()
    deadline_figure(rows)
    latency_queue_figure(rows)
    print(f"Wrote primary figures to {OUT}")
