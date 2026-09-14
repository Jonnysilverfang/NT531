#!/usr/bin/env python3
"""Generate a deterministic, reviewable Mode B schedule without touching AWS."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

from load_experiment_config import load_and_validate


TC_SEED_OFFSETS = {"tc01": 101, "tc02": 202, "tc03": 303, "tc04": 404}


def shuffled(values, seed: int):
    result = list(values)
    random.Random(seed).shuffle(result)
    return result


def build_plan(config_path: Path, profile: str | None, experiment_id: str) -> dict:
    config = load_and_validate(config_path, profile)
    exp = config["experiment"]
    runs = []
    for run_id in range(1, exp["independent_runs"] + 1):
        seeds = {tc: exp["random_seed"] + run_id * 1000 + offset
                 for tc, offset in TC_SEED_OFFSETS.items()}
        tc02_cells = [
            {"mtu": mtu, "parallel_streams": streams}
            for mtu, streams in product(config["tc02"]["mtu"], config["tc02"]["parallel_streams"])
        ]
        tc04_stages = []
        for stage, load in enumerate(config["tc04"]["load_pps"], 1):
            order = shuffled(config["tc04"]["conditions"], seeds["tc04"] + stage)
            tc04_stages.append({"stage": stage, "offered_load_pps": load, "condition_order": order})
        runs.append({
            "run_id": run_id,
            "block_id": f"block-{run_id:03d}",
            "seeds": seeds,
            "schedule": {
                "tc01": shuffled(config["tc01"]["conditions"], seeds["tc01"]),
                "tc02": shuffled(tc02_cells, seeds["tc02"]),
                "tc03_performance": shuffled(config["tc03"]["conditions"], seeds["tc03"]),
                "tc04": tc04_stages,
            },
        })
    raw_config = config_path.read_bytes()
    return {
        "schema_version": 1,
        "data_mode": "mode_b_plan_only",
        "aws_verified": False,
        "empirical": False,
        "experiment_id": experiment_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "config_sha256": hashlib.sha256(raw_config).hexdigest(),
        "profile": exp["selected_profile"],
        "independent_runs": exp["independent_runs"],
        "timing": exp["timing"],
        "saturation_preregistration": config["tc04"]["saturation"],
        "notes": [
            "This is a deterministic schedule, not AWS measurement evidence.",
            "TC01 target host identity must be persisted and treated as a blocking factor.",
            "TC03 overlapping-CIDR proof is a separate functional testcase and is not in this performance schedule.",
        ],
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("validation", "pilot", "final"))
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = build_plan(args.config, args.profile, args.experiment_id)
    serialized = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8", newline="\n")
        print(args.output)
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
