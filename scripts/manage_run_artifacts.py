#!/usr/bin/env python3
"""Create and seal auditable Mode B run directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_NAME = "checksums.sha256"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def safe_leaf_files(run_dir: Path) -> Iterable[Path]:
    root = run_dir.resolve()
    for path in sorted(run_dir.rglob("*"), key=lambda item: item.as_posix()):
        if path.name == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise ValueError(f"symlink is forbidden in raw evidence: {path}")
        if path.is_file():
            resolved = path.resolve()
            if root not in resolved.parents:
                raise ValueError(f"artifact escapes run directory: {path}")
            yield path


def write_json_atomic(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def init_run(args: argparse.Namespace) -> None:
    run_dir = args.run_dir
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(f"refusing to overwrite non-empty run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    for tc in ("tc01", "tc02", "tc03"):
        (run_dir / tc).mkdir()
    shutil.copyfile(args.config, run_dir / "experiment.yaml")
    root = Path(__file__).resolve().parents[1]
    manifest = {
        "schema_version": 2,
        "data_mode": args.data_mode,
        "empirical": args.data_mode == "empirical_aws",
        "experiment_id": args.experiment_id,
        "run_id": args.run_id,
        "block_id": f"block-{args.run_id:03d}",
        "status": "collecting",
        "started_at_utc": utc_now(),
        "finished_at_utc": None,
        "region": args.region,
        "profile": args.profile,
        "seed": args.seed,
        "git_commit": git_commit(root),
        "condition_schedule": {},
        "target_assignments": {},
        "exclusions": [],
    }
    write_json_atomic(run_dir / "manifest.json", manifest)


def record_schedule(args: argparse.Namespace) -> None:
    path = args.run_dir / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "collecting":
        raise ValueError("cannot modify a finalized run")
    if args.testcase in data["condition_schedule"]:
        raise ValueError(f"schedule already recorded for {args.testcase}")
    data["condition_schedule"][args.testcase] = {
        "seed": args.seed,
        "order": args.conditions,
    }
    write_json_atomic(path, data)


def record_target(args: argparse.Namespace) -> None:
    path = args.run_dir / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "collecting":
        raise ValueError("cannot modify a finalized run")
    testcase = data.setdefault("target_assignments", {}).setdefault(args.testcase, {})
    if args.condition in testcase:
        raise ValueError(f"target assignment already recorded for {args.testcase}/{args.condition}")
    testcase[args.condition] = {
        "target_id": args.target_id,
        "target_address": args.target_address,
        "path": args.path,
    }
    write_json_atomic(path, data)


def finalize(args: argparse.Namespace) -> None:
    manifest_path = args.run_dir / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("status") != "collecting":
        raise ValueError("run is not in collecting state")
    expected = {"tc01", "tc02", "tc03"}
    if set(data.get("condition_schedule", {})) != expected:
        missing = sorted(expected - set(data.get("condition_schedule", {})))
        raise ValueError(f"cannot finalize: missing condition schedules {missing}")
    data["status"] = "finalized"
    data["finished_at_utc"] = utc_now()
    write_json_atomic(manifest_path, data)

    lines = []
    for path in safe_leaf_files(args.run_dir):
        relative = path.relative_to(args.run_dir).as_posix()
        lines.append(f"{sha256(path)}  {relative}")
    (args.run_dir / MANIFEST_NAME).write_text("\n".join(lines) + "\n",
                                               encoding="utf-8", newline="\n")


def parse_checksum_manifest(run_dir: Path) -> dict[str, str]:
    path = run_dir / MANIFEST_NAME
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or not DIGEST_RE.fullmatch(parts[0]):
            raise ValueError(f"malformed checksum line {line_number}")
        digest, raw_name = parts
        pure = PurePosixPath(raw_name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in raw_name:
            raise ValueError(f"unsafe checksum path at line {line_number}: {raw_name}")
        normalized = pure.as_posix()
        if normalized in entries:
            raise ValueError(f"duplicate checksum entry: {normalized}")
        entries[normalized] = digest
    return entries


def verify(args: argparse.Namespace) -> None:
    entries = parse_checksum_manifest(args.run_dir)
    actual = {path.relative_to(args.run_dir).as_posix(): sha256(path)
              for path in safe_leaf_files(args.run_dir)}
    if entries.keys() != actual.keys():
        missing = sorted(actual.keys() - entries.keys())
        untracked = sorted(entries.keys() - actual.keys())
        raise ValueError(f"checksum coverage mismatch; missing={missing}, absent={untracked}")
    mismatches = [name for name, digest in entries.items() if actual[name] != digest]
    if mismatches:
        raise ValueError(f"checksum mismatch: {mismatches}")
    manifest = json.loads((args.run_dir / "manifest.json").read_text(encoding="utf-8"))
    valid_discriminators = {
        ("empirical_aws", True),
        ("local_emulation", False),
    }
    if (manifest.get("data_mode"), manifest.get("empirical")) not in valid_discriminators:
        raise ValueError("Mode B run manifest has an invalid evidence discriminator")
    if manifest.get("status") != "finalized":
        raise ValueError("Mode B run has not been finalized")
    print(f"MODE_B_RUN_VERIFY=PASS files={len(entries)} run={manifest['run_id']}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--run-dir", type=Path, required=True)
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--experiment-id", required=True)
    init.add_argument("--run-id", type=int, required=True)
    init.add_argument("--region", required=True)
    init.add_argument("--profile", required=True)
    init.add_argument("--seed", type=int, required=True)
    init.add_argument("--data-mode", choices=("empirical_aws", "local_emulation"), default="empirical_aws")
    init.set_defaults(func=init_run)

    record = sub.add_parser("record-schedule")
    record.add_argument("--run-dir", type=Path, required=True)
    record.add_argument("--testcase", choices=("tc01", "tc02", "tc03"), required=True)
    record.add_argument("--seed", type=int, required=True)
    record.add_argument("conditions", nargs="+")
    record.set_defaults(func=record_schedule)

    target = sub.add_parser("record-target")
    target.add_argument("--run-dir", type=Path, required=True)
    target.add_argument("--testcase", choices=("tc01", "tc03"), required=True)
    target.add_argument("--condition", required=True)
    target.add_argument("--target-id", required=True)
    target.add_argument("--target-address", required=True)
    target.add_argument("--path", required=True)
    target.set_defaults(func=record_target)

    seal = sub.add_parser("finalize")
    seal.add_argument("--run-dir", type=Path, required=True)
    seal.set_defaults(func=finalize)

    check = sub.add_parser("verify")
    check.add_argument("--run-dir", type=Path, required=True)
    check.set_defaults(func=verify)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        require_positive = getattr(args, "run_id", 1)
        if require_positive < 1:
            raise ValueError("run_id must be positive")
        args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ARTIFACT_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
