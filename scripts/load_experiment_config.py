#!/usr/bin/env python3
"""Validate the dependency-free YAML 1.2/JSON experiment contract.

The committed ``experiment.yaml`` uses JSON syntax, which is valid YAML 1.2,
so both Bash and the offline quality gate can load it with the Python standard
library. This avoids silently depending on PyYAML on benchmark hosts.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the experiment contract is incomplete or unsafe."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def positive_int(value: Any, field: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{field} must be a positive integer")
    return value


def number_gt_zero(value: Any, field: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0,
            f"{field} must be a positive number")
    return float(value)


def exact_conditions(section: dict[str, Any], expected: list[str], field: str) -> None:
    require(section.get("conditions") == expected,
            f"{field}.conditions must be exactly {expected}")


def load_and_validate(path: Path, profile_override: str | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"experiment.yaml must be UTF-8 JSON-compatible YAML: {exc}") from exc

    require(isinstance(data, dict), "config root must be an object")
    require(data.get("schema_version") == 2, "schema_version must be 2")
    experiment = data.get("experiment")
    require(isinstance(experiment, dict), "experiment must be an object")

    profiles = experiment.get("profiles")
    require(isinstance(profiles, dict) and set(profiles) == {"validation", "pilot", "final"},
            "experiment.profiles must contain validation, pilot, and final")
    for name, count in profiles.items():
        positive_int(count, f"experiment.profiles.{name}")
    require(profiles["final"] >= 10, "final profile must use at least 10 independent runs")

    active_profile = profile_override or experiment.get("active_profile")
    require(active_profile in profiles, f"unknown profile: {active_profile}")
    experiment["selected_profile"] = active_profile
    experiment["independent_runs"] = profiles[active_profile]

    require(isinstance(experiment.get("name"), str) and experiment["name"].strip(),
            "experiment.name is required")
    require(experiment.get("region") == "us-east-1",
            "this protocol is controlled for us-east-1")
    require(experiment.get("availability_zone") == "us-east-1a",
            "this protocol is controlled for us-east-1a")
    positive_int(experiment.get("random_seed"), "experiment.random_seed")
    require(experiment.get("results_root") == "results/mode_b",
            "experiment.results_root must keep Mode B separate at results/mode_b")
    require(isinstance(experiment.get("interface"), str) and experiment["interface"],
            "experiment.interface is required")

    timing = experiment.get("timing")
    require(isinstance(timing, dict), "experiment.timing must be an object")
    for key in ("warmup_seconds", "measurement_seconds", "cooldown_seconds"):
        positive_int(timing.get(key), f"experiment.timing.{key}")
    require(timing["measurement_seconds"] >= 30,
            "measurement_seconds must be at least 30 for Mode B")

    require(set(data) == {"schema_version", "experiment", "tc01", "tc02", "tc03"},
            "active experiment contract must contain exactly tc01, tc02, and tc03")
    for tc in ("tc01", "tc02", "tc03"):
        require(isinstance(data.get(tc), dict), f"{tc} must be an object")
        require(isinstance(data[tc].get("enabled"), bool), f"{tc}.enabled must be boolean")

    exact_conditions(data["tc01"], ["peering", "tgw"], "tc01")
    exact_conditions(data["tc03"], ["iptables", "xdp"], "tc03")

    require(data["tc02"].get("mtu") == [1500, 9001], "tc02.mtu must be [1500, 9001]")
    streams = data["tc02"].get("parallel_streams")
    require(streams == [1, 4, 8], "tc02.parallel_streams must be [1, 4, 8]")

    loads = data["tc03"].get("load_pps")
    require(isinstance(loads, list) and loads, "tc03.load_pps must be a non-empty list")
    require(all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in loads),
            "tc03.load_pps values must be positive integers")
    require(loads == sorted(set(loads)), "tc03.load_pps must be strictly increasing and unique")
    require(loads[0] == 100000, "tc03.load_pps must start at 100000 PPS")
    payload = positive_int(data["tc03"].get("udp_payload_bytes"), "tc03.udp_payload_bytes")
    require(payload <= 1472, "tc03.udp_payload_bytes must fit MTU 1500 without fragmentation")

    saturation = data["tc03"].get("saturation")
    require(isinstance(saturation, dict), "tc03.saturation must be an object")
    for key in ("packet_loss_percent_gt", "probe_p99_ms_gt", "cpu_percent_gt"):
        number_gt_zero(saturation.get(key), f"tc03.saturation.{key}")
    require(saturation["cpu_percent_gt"] <= 100, "cpu threshold cannot exceed 100 percent")
    return data


def shell_array(values: list[Any]) -> str:
    return "(" + " ".join(shlex.quote(str(value)) for value in values) + ")"


def emit_shell(data: dict[str, Any]) -> None:
    exp = data["experiment"]
    timing = exp["timing"]
    scalar_values = {
        "EXPERIMENT_NAME": exp["name"],
        "AWS_REGION": exp["region"],
        "AVAILABILITY_ZONE": exp["availability_zone"],
        "EXPERIMENT_PROFILE": exp["selected_profile"],
        "NUM_RUNS": exp["independent_runs"],
        "RANDOM_SEED": exp["random_seed"],
        "RESULTS_ROOT_REL": exp["results_root"],
        "INTERFACE": exp["interface"],
        "WARMUP_SECONDS": timing["warmup_seconds"],
        "MEASUREMENT_SECONDS": timing["measurement_seconds"],
        "COOLDOWN_SECONDS": timing["cooldown_seconds"],
        "SATURATION_LOSS_PCT": data["tc03"]["saturation"]["packet_loss_percent_gt"],
        "SATURATION_P99_MS": data["tc03"]["saturation"]["probe_p99_ms_gt"],
        "SATURATION_CPU_PCT": data["tc03"]["saturation"]["cpu_percent_gt"],
        "UDP_PAYLOAD_BYTES": data["tc03"]["udp_payload_bytes"],
    }
    for name, value in scalar_values.items():
        print(f"{name}={shlex.quote(str(value))}")
    for tc in ("tc01", "tc02", "tc03"):
        print(f"{tc.upper()}_ENABLED={'true' if data[tc]['enabled'] else 'false'}")
    print(f"TC01_CONDITIONS={shell_array(data['tc01']['conditions'])}")
    print(f"TC02_MTUS={shell_array(data['tc02']['mtu'])}")
    print(f"TC02_STREAMS={shell_array(data['tc02']['parallel_streams'])}")
    print(f"TC03_CONDITIONS={shell_array(data['tc03']['conditions'])}")
    print(f"TC03_LOAD_PPS={shell_array(data['tc03']['load_pps'])}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("validation", "pilot", "final"))
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    args = parser.parse_args()
    try:
        data = load_and_validate(args.config, args.profile)
    except ConfigError as exc:
        print(f"CONFIG_ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "shell":
        emit_shell(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
