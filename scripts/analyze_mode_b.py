#!/usr/bin/env python3
"""Fail-closed analyzer for empirical Mode B run-tree artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_saturation import MetricError, parse_sockperf_probe  # noqa: E402


class DataIntegrityError(ValueError):
    """Raised when Mode B evidence is missing, inconsistent, or malformed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DataIntegrityError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataIntegrityError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON must contain an object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_run(run_dir: Path) -> dict[str, Any]:
    checksum_path = run_dir / "checksums.sha256"
    require(checksum_path.is_file(), f"missing checksums.sha256: {run_dir}")
    entries: dict[str, str] = {}
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        require(
            len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]) is not None,
            f"malformed checksum line {line_number}: {run_dir}",
        )
        digest, raw_name = parts
        pure = PurePosixPath(raw_name)
        require(
            not pure.is_absolute() and ".." not in pure.parts and "\\" not in raw_name,
            f"unsafe checksum path: {raw_name}",
        )
        name = pure.as_posix()
        require(name not in entries, f"duplicate checksum entry: {name}")
        entries[name] = digest

    actual: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*")):
        if path == checksum_path:
            continue
        require(not path.is_symlink(), f"symlink is forbidden in evidence: {path}")
        if path.is_file():
            name = path.relative_to(run_dir).as_posix()
            actual[name] = sha256(path)
    require(entries.keys() == actual.keys(), f"checksum coverage mismatch: {run_dir}")
    mismatches = [name for name, digest in entries.items() if actual[name] != digest]
    require(not mismatches, f"checksum mismatch in {run_dir}: {mismatches}")

    manifest = read_json(run_dir / "manifest.json")
    require(manifest.get("status") == "finalized", f"run is not finalized: {run_dir}")
    require(
        manifest.get("data_mode") == "empirical_aws" and manifest.get("empirical") is True,
        f"invalid Mode B evidence discriminator: {run_dir}",
    )
    require(isinstance(manifest.get("run_id"), int) and manifest["run_id"] > 0, f"invalid run_id: {run_dir}")
    return manifest


def parse_sockperf(path: Path) -> dict[str, float]:
    try:
        result = parse_sockperf_probe(path)
    except MetricError as exc:
        raise DataIntegrityError(str(exc)) from exc
    for percentile in ("p50_ms", "p95_ms", "p99_ms"):
        require(percentile in result, f"sockperf {percentile} is missing: {path}")
    return result


def parse_ping(path: Path) -> dict[str, float]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except OSError as exc:
        raise DataIntegrityError(f"cannot read ping artifact {path}: {exc}") from exc
    loss = re.search(r"([0-9]+(?:\.[0-9]+)?)% packet loss", text)
    rtt = re.search(
        r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = "
        r"[0-9.]+/[0-9.]+/[0-9.]+/([0-9.]+) ms",
        text,
    )
    require(loss is not None, f"ping packet-loss summary is missing: {path}")
    require(rtt is not None, f"ping jitter/mdev summary is missing: {path}")
    return {"loss_pct": float(loss.group(1)), "jitter_ms": float(rtt.group(1))}


def parse_iperf3_throughput(path: Path) -> dict[str, float]:
    payload = read_json(path)
    require(not payload.get("error"), f"iperf3 reported an error in {path}: {payload.get('error')}")
    end = payload.get("end")
    require(isinstance(end, dict), f"iperf3 end summary is missing: {path}")
    candidates = (end.get("sum_received"), end.get("sum_sent"), end.get("sum"))
    summary = next((item for item in candidates if isinstance(item, dict) and "bits_per_second" in item), None)
    require(summary is not None, f"iperf3 throughput summary is missing: {path}")
    bps = float(summary["bits_per_second"])
    require(bps > 0, f"iperf3 throughput must be positive: {path}")
    result = {"throughput_gbps": bps / 1_000_000_000.0}
    sent = end.get("sum_sent")
    require(isinstance(sent, dict) and sent.get("retransmits") is not None,
            f"iperf3 TCP retransmit summary is missing: {path}")
    result["retransmits"] = float(sent["retransmits"])
    return result


def parse_cpu_metrics(path: Path) -> dict[str, float]:
    payload = read_json(path)
    metrics = payload.get("metrics")
    require(isinstance(metrics, dict), f"CPU delta metrics are missing: {path}")
    result = {}
    for key in ("softirq_percent", "cpu_total_percent", "ena_rx_pps", "ena_tx_pps"):
        try:
            result[key] = float(metrics[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataIntegrityError(f"invalid {key}: {path}") from exc
        if key.endswith("_percent"):
            require(0 <= result[key] <= 100, f"{key} outside [0,100]: {path}")
        else:
            require(result[key] >= 0, f"{key} must be non-negative: {path}")
    return result


def describe(values: list[float]) -> dict[str, float | int]:
    require(bool(values), "cannot summarize an empty series")
    return {
        "n_runs": len(values),
        "mean": float(statistics.fmean(values)),
        "median": float(statistics.median(values)),
        "min": float(min(values)),
        "max": float(max(values)),
    }


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    require(bool(ordered), "percentile requires a non-empty series")
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * percent / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def paired_run_level_bootstrap(
    run_deltas: dict[int, float], n_resamples: int = 10000, seed: int = 42
) -> dict[str, Any]:
    """Bootstrap paired run summaries; no within-run resampling is claimed."""
    require(n_resamples > 0, "bootstrap resamples must be positive")
    require(bool(run_deltas), "paired bootstrap requires at least one run")
    run_ids = sorted(run_deltas)
    deltas = [float(run_deltas[run_id]) for run_id in run_ids]
    rng = random.Random(seed)
    bootstrap_means = [
        statistics.fmean(rng.choice(deltas) for _ in deltas)
        for _ in range(n_resamples)
    ]
    return {
        "method": "paired_run_level_bootstrap",
        "statistical_unit": "independent_run",
        "n_runs": len(run_ids),
        "resamples": n_resamples,
        "estimate": float(statistics.fmean(deltas)),
        "ci95": [
            percentile(bootstrap_means, 2.5),
            percentile(bootstrap_means, 97.5),
        ],
        "run_deltas": {str(run_id): run_deltas[run_id] for run_id in run_ids},
    }


def assignments(manifest: dict[str, Any], testcase: str) -> dict[str, dict[str, str]]:
    targets = manifest.get("target_assignments", {}).get(testcase)
    require(isinstance(targets, dict), f"missing target assignments for {testcase}, run {manifest['run_id']}")
    return targets


def analyze_tc01(
    runs: list[tuple[Path, dict[str, Any]]], n_resamples: int, seed: int
) -> dict[str, Any]:
    observations: dict[str, dict[str, list[float]]] = {
        condition: {metric: [] for metric in ("p50_ms", "p95_ms", "p99_ms", "jitter_ms", "loss_pct")}
        for condition in ("peering", "tgw")
    }
    deltas: dict[int, float] = {}
    same_backend_by_run: dict[str, bool] = {}
    target_ids: dict[str, dict[str, str]] = {}
    for run_dir, manifest in runs:
        run_id = manifest["run_id"]
        target = assignments(manifest, "tc01")
        for condition in ("peering", "tgw"):
            require(isinstance(target.get(condition), dict), f"missing TC-01 {condition} target metadata")
            require(bool(target[condition].get("target_id")), f"missing TC-01 {condition} target_id")
        same_backend = target["peering"]["target_id"] == target["tgw"]["target_id"]
        same_backend_by_run[str(run_id)] = same_backend
        target_ids[str(run_id)] = {condition: target[condition]["target_id"] for condition in ("peering", "tgw")}
        condition_metrics = {}
        for condition in ("peering", "tgw"):
            metrics = {
                **parse_sockperf(run_dir / "tc01" / condition / "latency.txt"),
                **parse_ping(run_dir / "tc01" / condition / "ping.txt"),
            }
            condition_metrics[condition] = metrics
            for metric in observations[condition]:
                observations[condition][metric].append(metrics[metric])
        deltas[run_id] = condition_metrics["tgw"]["p99_ms"] - condition_metrics["peering"]["p99_ms"]

    all_same_backend = all(same_backend_by_run.values())
    return {
        "n_runs": len(runs),
        "conditions": {
            condition: {metric: describe(values) for metric, values in metrics.items()}
            for condition, metrics in observations.items()
        },
        "p99_delta_ms_tgw_minus_peering": paired_run_level_bootstrap(deltas, n_resamples, seed),
        "design": {
            "same_backend_all_runs": all_same_backend,
            "same_backend_by_run": same_backend_by_run,
            "target_ids": target_ids,
            "allowed_claim": (
                "path effect with a common backend"
                if all_same_backend
                else "observed path-configuration association conditional on host assignment"
            ),
            "limitation": None if all_same_backend else "path and backend host change together; pure TGW causal effect is not identified",
        },
    }


def analyze_tc02(
    runs: list[tuple[Path, dict[str, Any]]], config: dict[str, Any], n_resamples: int, seed: int
) -> dict[str, Any]:
    mtus = [int(value) for value in config["tc02"]["mtu"]]
    streams_values = [int(value) for value in config["tc02"]["parallel_streams"]]
    require(set(mtus) == {1500, 9001}, "TC-02 analyzer requires MTU 1500 and 9001")
    by_cell: dict[tuple[int, int], dict[int, dict[str, float]]] = {}
    for run_dir, manifest in runs:
        run_id = manifest["run_id"]
        for mtu in mtus:
            for streams in streams_values:
                cell_dir = run_dir / "tc02" / f"mtu{mtu}-p{streams}"
                require(cell_dir.is_dir(), f"missing TC-02 cell: {cell_dir}")
                metrics = {
                    **parse_iperf3_throughput(cell_dir / "iperf3.json"),
                    **parse_cpu_metrics(cell_dir / "softirq_delta.json"),
                }
                by_cell.setdefault((mtu, streams), {})[run_id] = metrics

    cells: dict[str, Any] = {}
    for (mtu, streams), run_metrics in sorted(by_cell.items()):
        cells[f"mtu_{mtu}_p{streams}"] = {
            metric: describe([value[metric] for value in run_metrics.values()])
            for metric in ("throughput_gbps", "retransmits", "softirq_percent", "cpu_total_percent", "ena_rx_pps", "ena_tx_pps")
        }

    effects = {}
    for streams in streams_values:
        effects[str(streams)] = {}
        for metric in ("throughput_gbps", "retransmits", "softirq_percent", "cpu_total_percent", "ena_rx_pps", "ena_tx_pps"):
            deltas = {
                run_id: by_cell[(9001, streams)][run_id][metric] - by_cell[(1500, streams)][run_id][metric]
                for run_id in (manifest["run_id"] for _, manifest in runs)
            }
            effects[str(streams)][f"{metric}_mtu9001_minus_mtu1500"] = paired_run_level_bootstrap(
                deltas, n_resamples, seed + streams
            )
    return {"n_runs": len(runs), "cells": cells, "paired_effects_by_stream": effects}


def load_saturation_events(path: Path) -> list[dict[str, Any]]:
    require(path.is_file(), f"missing saturation event file: {path}")
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DataIntegrityError(f"invalid saturation JSONL line {line_number}: {path}") from exc
        require(isinstance(event, dict), f"saturation event must be an object: {path}:{line_number}")
        events.append(event)
    return events


def analyze_tc03(
    runs: list[tuple[Path, dict[str, Any]]], config: dict[str, Any], n_resamples: int, seed: int
) -> dict[str, Any]:
    configured_loads = [int(value) for value in config["tc03"]["load_pps"]]
    conditions = tuple(config["tc03"]["conditions"])
    require(set(conditions) == {"iptables", "xdp"}, "TC-03 requires iptables and xdp")
    per_condition: dict[str, dict[int, dict[str, Any] | None]] = {condition: {} for condition in conditions}
    curves: dict[str, dict[str, list[dict[str, Any]]]] = {condition: {} for condition in conditions}

    for run_dir, manifest in runs:
        run_id = manifest["run_id"]
        target = assignments(manifest, "tc03")
        require(isinstance(target.get("dut"), dict), f"missing TC-03 DUT target metadata, run {run_id}")
        events = load_saturation_events(run_dir / "tc03" / "saturation_events.jsonl")
        for event in events:
            require(event.get("run_id") == run_id, f"TC-03 run_id mismatch in {run_dir}")
        for condition in conditions:
            condition_events = [event for event in events if event.get("condition") == condition]
            targets = [event.get("load_target_pps") for event in condition_events]
            require(all(isinstance(value, int) and value > 0 for value in targets), f"invalid TC-03 target load")
            require(targets == sorted(targets), f"TC-03 loads are not increasing for {condition}, run {run_id}")
            saturated_indices = [
                index for index, event in enumerate(condition_events)
                if isinstance(event.get("saturation"), dict) and event["saturation"].get("saturated") is True
            ]
            expected = configured_loads if not saturated_indices else configured_loads[: saturated_indices[0] + 1]
            require(targets == expected, f"incomplete TC-03 load prefix for {condition}, run {run_id}")
            require(len(saturated_indices) <= 1, f"multiple saturation events after early stop for {condition}, run {run_id}")
            for event in condition_events:
                saturation = event.get("saturation")
                require(isinstance(saturation, dict), f"missing saturation metrics for {condition}, run {run_id}")
                for key in ("achieved_load_pps", "loss_pct", "p99_ms", "cpu_pct", "softirq_pct"):
                    require(isinstance(saturation.get(key), (int, float)), f"missing {key} for {condition}, run {run_id}")
                require(isinstance(saturation.get("dut_ena_rx_pps"), (int, float)),
                        f"missing DUT ENA RX PPS for {condition}, run {run_id}")
            first = condition_events[saturated_indices[0]] if saturated_indices else None
            per_condition[condition][run_id] = first
            curves[condition][str(run_id)] = condition_events

        xdp_stage_count = sum(1 for event in events if event.get("condition") == "xdp")
        native_evidence = []
        for path in (run_dir / "commands").glob("*_stdout.log"):
            text = path.read_text(encoding="utf-8", errors="strict")
            if "___XDP_NATIVE_EVIDENCE_BEGIN___" in text and "___XDP_NATIVE_EVIDENCE_END___" in text:
                require("driver: ena" in text, f"XDP evidence lacks ENA driver: {path}")
                require(not re.search(r"xdpgeneric|mode\s+generic", text, re.IGNORECASE),
                        f"generic XDP evidence is forbidden: {path}")
                require(re.search(r"type xdp", text, re.IGNORECASE) is not None,
                        f"XDP program ID/tag evidence is missing: {path}")
                native_evidence.append(path.name)
        require(len(native_evidence) == xdp_stage_count,
                f"TC-03 requires one native XDP evidence record per measured XDP stage, run {run_id}")

    condition_results = {}
    sustainable_by_condition: dict[str, dict[int, float | None]] = {condition: {} for condition in conditions}
    for condition in conditions:
        points = per_condition[condition]
        observed = {
            run_id: float(event["saturation"]["achieved_load_pps"])
            for run_id, event in points.items() if event is not None
        }
        for run_id in points:
            events = curves[condition][str(run_id)]
            sustainable = [
                float(event["saturation"]["achieved_load_pps"])
                for event in events if event["saturation"]["saturated"] is False
            ]
            sustainable_by_condition[condition][run_id] = max(sustainable) if sustainable else None
        sustainable_observed = [value for value in sustainable_by_condition[condition].values() if value is not None]
        condition_results[condition] = {
            "saturated_runs": len(observed),
            "right_censored_runs": [str(run_id) for run_id, event in points.items() if event is None],
            "saturation_achieved_pps": describe(list(observed.values())) if observed else None,
            "max_sustainable_achieved_pps": describe(sustainable_observed) if sustainable_observed else None,
            "max_sustainable_by_run": {
                str(run_id): value for run_id, value in sustainable_by_condition[condition].items()
            },
            "run_points": {
                str(run_id): (
                    None if event is None else {
                        "target_pps": event["load_target_pps"],
                        "achieved_pps": event["saturation"]["achieved_load_pps"],
                        "violations": event["saturation"].get("violations", []),
                    }
                )
                for run_id, event in points.items()
            },
        }

    comparable = {
        run_id: float(sustainable_by_condition["xdp"][run_id])
        - float(sustainable_by_condition["iptables"][run_id])
        for run_id in sustainable_by_condition["iptables"]
        if sustainable_by_condition["iptables"][run_id] is not None
        and sustainable_by_condition["xdp"][run_id] is not None
    }
    return {
        "n_runs": len(runs),
        "conditions": condition_results,
        "paired_max_sustainable_pps_xdp_minus_iptables": (
            paired_run_level_bootstrap(comparable, n_resamples, seed + 4) if comparable else None
        ),
        "load_curves": curves,
        "censoring_note": "A missing saturation point means right-censored above the largest achieved stage, not infinite capacity.",
    }


def analyze_experiment(
    experiment_dir: Path,
    output_json: Path | None = None,
    n_resamples: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    run_dirs = sorted(path for path in experiment_dir.iterdir() if path.is_dir() and re.fullmatch(r"run_\d+", path.name))
    require(bool(run_dirs), f"no runs found in {experiment_dir}")
    runs = [(run_dir, verify_run(run_dir)) for run_dir in run_dirs]
    run_ids = [manifest["run_id"] for _, manifest in runs]
    require(len(run_ids) == len(set(run_ids)), "duplicate Mode B run_id")

    config_bytes = [(run_dir / "experiment.yaml").read_bytes() for run_dir, _ in runs]
    require(all(value == config_bytes[0] for value in config_bytes), "experiment config drift across runs")
    try:
        config = json.loads(config_bytes[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataIntegrityError(f"invalid experiment.yaml snapshot: {exc}") from exc
    profile = runs[0][1].get("profile")
    require(all(manifest.get("profile") == profile for _, manifest in runs), "profile drift across runs")
    expected_runs = int(config["experiment"]["profiles"][profile])
    require(len(runs) == expected_runs, f"incomplete experiment: expected {expected_runs} runs, found {len(runs)}")

    analyzers: dict[str, Callable[[], dict[str, Any]]] = {
        "tc01": lambda: analyze_tc01(runs, n_resamples, seed + 101),
        "tc02": lambda: analyze_tc02(runs, config, n_resamples, seed + 202),
        "tc03": lambda: analyze_tc03(runs, config, n_resamples, seed + 303),
    }
    testcase_results = {}
    for testcase, analyzer in analyzers.items():
        require(config[testcase].get("enabled") is True, f"unified Mode B summary requires enabled {testcase}")
        testcase_results[testcase] = analyzer()

    summary = {
        "schema_version": 2,
        "data_mode": "empirical_aws",
        "empirical": True,
        "experiment_id": runs[0][1].get("experiment_id", experiment_dir.name),
        "profile": profile,
        "n_runs": len(runs),
        "run_ids": run_ids,
        "analysis": {
            "primary_method": "paired_run_level_bootstrap",
            "hierarchical_bootstrap_claimed": False,
            "bootstrap_resamples": n_resamples,
            "random_seed": seed,
        },
        **testcase_results,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--bootstrap-resamples", type=int, default=10000)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()
    output = args.output_json or args.experiment_dir / "mode_b_summary.json"
    try:
        analyze_experiment(args.experiment_dir, output, args.bootstrap_resamples, args.random_seed)
    except (DataIntegrityError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"MODE_B_ANALYSIS_ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"MODE_B_ANALYSIS=PASS output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
