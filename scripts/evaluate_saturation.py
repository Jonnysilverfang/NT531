#!/usr/bin/env python3
"""Evaluate one TC-04 load stage from measured artifacts.

The evaluator is fail-closed: malformed or missing probe, CPU-delta, or iperf3
evidence aborts the stage instead of silently turning the metric into zero.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


class MetricError(ValueError):
    """Raised when a raw metric cannot be interpreted safely."""


NUMBER = r"([0-9]+(?:\.[0-9]+)?)"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetricError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MetricError(f"JSON artifact must be an object: {path}")
    return value


def parse_sockperf_probe(path: Path) -> dict[str, float]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except OSError as exc:
        raise MetricError(f"cannot read sockperf probe {path}: {exc}") from exc

    percentile_values: dict[float, float] = {}
    for match in re.finditer(
        rf"percentile\s+{NUMBER}\s*(?:=|:)\s*{NUMBER}", text, re.IGNORECASE
    ):
        percentile_values[float(match.group(1))] = float(match.group(2))
    if 99.0 not in percentile_values:
        raise MetricError(f"sockperf P99 is missing: {path}")

    # Sockperf normally labels the summary as usec. Explicit labels win; ms is
    # the conservative default for fixtures/wrappers that already normalize it.
    nearby_unit = re.search(r"(?:usec|microsecond|\[us\])", text, re.IGNORECASE)
    scale_to_ms = 0.001 if nearby_unit else 1.0

    explicit_loss = re.search(
        rf"Packets\s+lost[^\n\r%]*?{NUMBER}\s*%", text, re.IGNORECASE
    )
    if explicit_loss:
        loss_pct = float(explicit_loss.group(1))
    else:
        sent = re.findall(rf"SentMessages\s*[=:]\s*{NUMBER}", text, re.IGNORECASE)
        received = re.findall(rf"ReceivedMessages\s*[=:]\s*{NUMBER}", text, re.IGNORECASE)
        if not sent or not received:
            raise MetricError(f"sockperf legitimate-flow loss evidence is missing: {path}")
        sent_count = float(sent[-1])
        received_count = float(received[-1])
        if sent_count <= 0 or received_count > sent_count:
            raise MetricError(f"invalid sockperf message counters: {path}")
        loss_pct = 100.0 * (sent_count - received_count) / sent_count

    result = {"loss_pct": round(loss_pct, 6)}
    for percentile, key in ((50.0, "p50_ms"), (95.0, "p95_ms"), (99.0, "p99_ms")):
        if percentile in percentile_values:
            result[key] = round(percentile_values[percentile] * scale_to_ms, 6)
    return result


def parse_iperf3_achieved_pps(path: Path) -> dict[str, float]:
    payload = _read_json(path)
    error = payload.get("error")
    if error:
        raise MetricError(f"iperf3 reported an error: {error}")
    end = payload.get("end")
    if not isinstance(end, dict):
        raise MetricError(f"iperf3 end summary is missing: {path}")

    candidates = [end.get("sum_sent"), end.get("sum")]
    summary = next(
        (item for item in candidates if isinstance(item, dict) and item.get("packets") is not None),
        None,
    )
    if summary is None:
        raise MetricError(f"iperf3 sender packet summary is missing: {path}")
    packets = float(summary.get("packets", 0))
    seconds = float(summary.get("seconds", 0))
    if packets <= 0 or seconds <= 0:
        raise MetricError(f"invalid iperf3 packets/duration: {path}")
    bits_per_second = float(summary.get("bits_per_second", 0))
    return {
        "achieved_load_pps": round(packets / seconds, 3),
        "achieved_load_bits_per_second": round(bits_per_second, 3),
        "sender_packets": int(packets),
        "measurement_seconds": round(seconds, 6),
    }


def parse_cpu_delta(path: Path) -> dict[str, float]:
    payload = _read_json(path)
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise MetricError(f"CPU delta metrics are missing: {path}")
    try:
        cpu_pct = float(metrics["cpu_total_percent"])
        softirq_pct = float(metrics["softirq_percent"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MetricError(f"CPU delta percentages are invalid: {path}") from exc
    if not (0 <= cpu_pct <= 100 and 0 <= softirq_pct <= 100):
        raise MetricError(f"CPU delta percentages are outside [0,100]: {path}")
    return {"cpu_pct": cpu_pct, "softirq_pct": softirq_pct}


def evaluate(
    probe_output: Path,
    cpu_delta: Path,
    load_output: Path,
    loss_threshold: float,
    p99_threshold_ms: float,
    cpu_threshold: float,
) -> dict[str, Any]:
    probe = parse_sockperf_probe(probe_output)
    cpu = parse_cpu_delta(cpu_delta)
    achieved = parse_iperf3_achieved_pps(load_output)
    violations = []
    if probe["loss_pct"] > loss_threshold:
        violations.append("legitimate_loss_pct")
    if probe["p99_ms"] > p99_threshold_ms:
        violations.append("legitimate_p99_ms")
    if cpu["cpu_pct"] > cpu_threshold:
        violations.append("cpu_total_percent")
    return {
        "saturated": bool(violations),
        **probe,
        **cpu,
        **achieved,
        "thresholds": {
            "loss_pct_gt": loss_threshold,
            "p99_ms_gt": p99_threshold_ms,
            "cpu_pct_gt": cpu_threshold,
        },
        "violations": violations,
        "reason": ",".join(violations),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-output", type=Path, required=True)
    parser.add_argument("--cpu-delta", type=Path, required=True)
    parser.add_argument("--load-output", type=Path, required=True)
    parser.add_argument("--loss-threshold", type=float, required=True)
    parser.add_argument("--p99-threshold-ms", type=float, required=True)
    parser.add_argument("--cpu-threshold", type=float, required=True)
    args = parser.parse_args()
    try:
        result = evaluate(
            args.probe_output,
            args.cpu_delta,
            args.load_output,
            args.loss_threshold,
            args.p99_threshold_ms,
            args.cpu_threshold,
        )
    except MetricError as exc:
        parser.exit(2, f"SATURATION_EVIDENCE_ERROR: {exc}\n")
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
