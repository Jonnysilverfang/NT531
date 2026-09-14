import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mode_b = load_module("mode_b_analysis", "scripts/analyze_mode_b.py")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def sockperf(p50, p95, p99):
    return (
        f"percentile 50.000 = {p50}\n"
        f"percentile 95.000 = {p95}\n"
        f"percentile 99.000 = {p99}\n"
        "#[Packets lost] = 0.000%\n"
    )


def iperf(gbps):
    return {"end": {"sum_received": {"bits_per_second": gbps * 1e9}}}


def cpu(softirq, total):
    return {"metrics": {"softirq_percent": softirq, "cpu_total_percent": total}}


def seal(run_dir):
    lines = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(run_dir).as_posix()}")
    (run_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


class ModeBAnalyzerTests(unittest.TestCase):
    def build_experiment(self, root):
        config = json.loads((ROOT / "experiment.yaml").read_text(encoding="utf-8"))
        for run_id in range(1, 4):
            run = root / f"run_{run_id:03d}"
            run.mkdir(parents=True)
            (run / "experiment.yaml").write_text(json.dumps(config), encoding="utf-8")
            manifest = {
                "status": "finalized",
                "data_mode": "empirical_aws",
                "empirical": True,
                "run_id": run_id,
                "experiment_id": root.name,
                "profile": "validation",
                "target_assignments": {
                    "tc01": {
                        "peering": {"target_id": "host-b1"},
                        "tgw": {"target_id": "host-b2"},
                    },
                    "tc03": {
                        "direct": {"target_id": "host-shared"},
                        "privatelink": {"target_id": "host-shared"},
                    },
                },
            }
            write_json(run / "manifest.json", manifest)
            for condition, shift in (("peering", 0.0), ("tgw", 0.7)):
                path = run / "tc01" / condition / "latency.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(sockperf(0.1 + shift, 0.2 + shift, 0.3 + shift), encoding="utf-8")
            for mtu in (1500, 9001):
                for streams in (1, 4, 8):
                    cell = run / "tc02" / f"mtu{mtu}-p{streams}"
                    write_json(cell / "iperf3.json", iperf(2.0 + streams / 10 + (1 if mtu == 9001 else 0)))
                    write_json(cell / "softirq_delta.json", cpu(30 if mtu == 9001 else 60, 50 if mtu == 9001 else 80))
            for condition, shift in (("direct", 0.0), ("privatelink", 0.4)):
                path = run / "tc03" / condition / "latency.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(sockperf(0.1 + shift, 0.2 + shift, 0.3 + shift), encoding="utf-8")
                write_json(run / "tc03" / condition / "iperf3.json", iperf(5.0 - shift))
            events = []
            for condition, achieved in (("iptables", 90000), ("xdp", 98000)):
                events.append({
                    "run_id": run_id,
                    "load_target_pps": 100000,
                    "condition": condition,
                    "saturation": {
                        "saturated": True,
                        "achieved_load_pps": achieved + run_id,
                        "loss_pct": 2.0,
                        "p99_ms": 6.0,
                        "cpu_pct": 91.0,
                        "softirq_pct": 40.0,
                        "violations": ["legitimate_loss_pct"],
                    },
                })
            saturation = run / "tc04" / "saturation_events.jsonl"
            saturation.parent.mkdir(parents=True, exist_ok=True)
            saturation.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
            seal(run)

    def test_unified_summary_covers_all_testcases_and_uses_honest_method_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "experiment_fixture"
            root.mkdir()
            self.build_experiment(root)
            result = mode_b.analyze_experiment(root, n_resamples=200, seed=7)
            self.assertEqual(result["analysis"]["primary_method"], "paired_run_level_bootstrap")
            self.assertFalse(result["analysis"]["hierarchical_bootstrap_claimed"])
            self.assertEqual([key for key in ("tc01", "tc02", "tc03", "tc04") if key in result], ["tc01", "tc02", "tc03", "tc04"])
            self.assertFalse(result["tc01"]["design"]["same_backend_all_runs"])
            self.assertTrue(result["tc03"]["same_backend_verified"])
            self.assertEqual(len(result["tc02"]["cells"]), 6)
            self.assertIsNotNone(result["tc04"]["paired_saturation_achieved_pps_xdp_minus_iptables"])

    def test_incomplete_cell_fails_closed_even_with_valid_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "experiment_fixture"
            root.mkdir()
            self.build_experiment(root)
            missing = root / "run_002" / "tc02" / "mtu1500-p4" / "iperf3.json"
            missing.unlink()
            seal(root / "run_002")
            with self.assertRaises(mode_b.DataIntegrityError):
                mode_b.analyze_experiment(root, n_resamples=20)

    def test_tc03_different_backend_fails_protocol_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "experiment_fixture"
            root.mkdir()
            self.build_experiment(root)
            run = root / "run_001"
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            manifest["target_assignments"]["tc03"]["privatelink"]["target_id"] = "wrong-host"
            write_json(run / "manifest.json", manifest)
            seal(run)
            with self.assertRaises(mode_b.DataIntegrityError):
                mode_b.analyze_experiment(root, n_resamples=20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
