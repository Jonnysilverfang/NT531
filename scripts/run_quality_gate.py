#!/usr/bin/env python3
"""Offline quality gate: không gọi AWS, không deploy, không nạp XDP."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command):
    print("+", " ".join(map(str, command)))
    subprocess.run(command, cwd=ROOT, check=True)


def validate_markdown():
    checked_links = 0
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        forbidden = (
            "số liệu thực nghiệm chuẩn Chế độ A",
            "Tốc độ loại bỏ gói tin quan sát được (Observed Dropped Packet Rate)",
        )
        if "\ufffd" in text or any(phrase in text for phrase in forbidden):
            raise SystemExit(f"FAIL documentation integrity: {path.relative_to(ROOT)}")
        for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", text):
            target = target.strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "file:///", "mailto:")):
                continue
            checked_links += 1
            if not (path.parent / target).resolve().exists():
                raise SystemExit(f"FAIL broken Markdown link: {path.relative_to(ROOT)} -> {target}")
    print(f"PASS Markdown: UTF-8/claim guard and {checked_links} relative links")


def validate_shell_syntax():
    bash = shutil.which("bash")
    if sys.platform == "win32":
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if git_bash.exists():
            bash = str(git_bash)
    if not bash:
        raise SystemExit("FAIL: bash unavailable; shell syntax cannot be certified")
    scripts = [
        "scripts/benchmark_runner.sh", "scripts/dut_server_setup.sh",
        "scripts/collect_ena_metrics.sh", "scripts/cleanup_resources.sh",
        "ebpf/ebpf_loader.sh",
    ]
    run([bash, "-n", *scripts])
    print(f"PASS bash syntax: {len(scripts)} scripts")


def main():
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])

    dashboard = ROOT / "monitoring/grafana/dashboards/network_performance_p95_p99.json"
    json.loads(dashboard.read_text(encoding="utf-8"))
    print(f"PASS JSON: {dashboard.relative_to(ROOT)}")
    validate_markdown()
    validate_shell_syntax()

    with tempfile.TemporaryDirectory() as raw_tmp:
        run([sys.executable, "scripts/generate_reference_dataset.py", "--output-dir", raw_tmp])
        generated_manifest = (Path(raw_tmp) / "checksums.sha256").read_text(encoding="utf-8")
        repository_manifest = (ROOT / "results/raw/checksums.sha256").read_text(encoding="utf-8")
        if generated_manifest != repository_manifest:
            raise SystemExit("FAIL: raw dataset không tái lập từ generation recipe")
        print("PASS raw reproducibility: recipe regenerates all 5 source hashes")

    with tempfile.TemporaryDirectory() as tmp:
        generated = Path(tmp) / "summary_statistics.json"
        run([
            sys.executable, "scripts/analyze_results.py",
            "--input-dir", "results/raw",
            "--output-json", str(generated),
            "--bootstrap-resamples", "10000",
            "--random-seed", "42",
        ])
        expected = json.loads((ROOT / "results/summary_statistics.json").read_text(encoding="utf-8"))
        actual = json.loads(generated.read_text(encoding="utf-8"))
        if actual != expected:
            raise SystemExit("FAIL: summary_statistics.json không tái lập từ raw data")
        print("PASS reproducibility: generated summary equals repository summary")

    print("QUALITY_GATE=PASS (offline-only; no AWS/XDP workload executed)")


if __name__ == "__main__":
    main()
