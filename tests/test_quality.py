import copy
import hashlib
import importlib.util
import json
import random
import tempfile
import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analysis = load_module("capstone_analysis", "scripts/analyze_results.py")
softirq = load_module("capstone_softirq", "scripts/calculate_softirq_delta.py")
exporter = load_module("capstone_exporter", "monitoring/mock_metrics_exporter.py")
generator = load_module("capstone_generator", "scripts/generate_reference_dataset.py")


def hcl_resource_block(text, resource_type, name):
    match = re.search(rf'resource\s+"{re.escape(resource_type)}"\s+"{re.escape(name)}"\s*\{{', text)
    if not match:
        raise AssertionError(f"Missing Terraform resource {resource_type}.{name}")
    start = match.start()
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"Unbalanced Terraform block {resource_type}.{name}")


class ChecksumManifestTests(unittest.TestCase):
    def make_fixture(self, directory):
        hashes = []
        for filename in analysis.REQUIRED_RAW_FILES:
            payload = f"fixture:{filename}\n".encode()
            (directory / filename).write_bytes(payload)
            hashes.append(f"{hashlib.sha256(payload).hexdigest()}  {filename}")
        (directory / "checksums.sha256").write_text("\n".join(hashes) + "\n", encoding="utf-8")

    def test_repository_manifest_verifies_all_required_files(self):
        result = analysis.verify_checksum_manifest(str(ROOT / "results/raw"))
        self.assertEqual(result["files_verified"], len(analysis.REQUIRED_RAW_FILES))
        self.assertEqual(result["status"], "passed")

    def test_missing_required_manifest_entry_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.make_fixture(directory)
            lines = (directory / "checksums.sha256").read_text(encoding="utf-8").splitlines()
            (directory / "checksums.sha256").write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
            with self.assertRaises(analysis.DataIntegrityError):
                analysis.verify_checksum_manifest(str(directory))

    def test_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.make_fixture(directory)
            (directory / analysis.REQUIRED_RAW_FILES[0]).write_text("tampered", encoding="utf-8")
            with self.assertRaises(analysis.DataIntegrityError):
                analysis.verify_checksum_manifest(str(directory))

    def test_generation_recipe_reproduces_repository_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = generator.generate(tmp)
            expected = {}
            for line in (ROOT / "results/raw/checksums.sha256").read_text(encoding="utf-8").splitlines():
                digest, filename = line.split()
                expected[filename] = digest
            self.assertEqual(generated, expected)

    def test_generator_refuses_implicit_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator.generate(tmp)
            with self.assertRaises(FileExistsError):
                generator.generate(tmp)


class RawSemanticValidationTests(unittest.TestCase):
    def test_repository_raw_dataset_passes(self):
        result = analysis.validate_raw_dataset(str(ROOT / "results/raw"))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["tc01_observations"], 6000)
        self.assertEqual(result["independent_runs"], 3)

    def test_tc01_duplicate_timestamp_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            for filename in analysis.REQUIRED_RAW_FILES:
                (destination / filename).write_bytes((ROOT / "results/raw" / filename).read_bytes())
            csv_path = destination / "tc01_peering_tgw_samples.csv"
            lines = csv_path.read_text(encoding="utf-8").splitlines()
            first = lines[1].split(",")
            second = lines[2].split(",")
            second[0] = first[0]
            lines[2] = ",".join(second)
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(analysis.DataIntegrityError):
                analysis.validate_raw_dataset(str(destination))

    def test_tc04_invalid_percentile_order_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            for filename in analysis.REQUIRED_RAW_FILES:
                (destination / filename).write_bytes((ROOT / "results/raw" / filename).read_bytes())
            path = destination / "tc04_xdp_iptables_samples.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["runs"][0]["xdp_series"][0]["probe_tcp_p99_ms"] = 0.001
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(analysis.DataIntegrityError):
                analysis.validate_raw_dataset(str(destination))

    def test_manifest_cannot_claim_empirical_or_change_recipe_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            for filename in analysis.REQUIRED_RAW_FILES:
                (destination / filename).write_bytes((ROOT / "results/raw" / filename).read_bytes())
            path = destination / "environment_manifest.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["provenance"]["empirical"] = True
            data["provenance"]["random_seeds"]["tc04"] = 1
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(analysis.DataIntegrityError):
                analysis.validate_raw_dataset(str(destination))

class SoftirqDeltaTests(unittest.TestCase):
    def snapshots(self):
        before = {
            "host": "dut-a", "instance_id": "i-abc", "interface": "eth0",
            "mac_address": "00:11:22:33:44:55", "timestamp_monotonic_ns": 1_000_000_000,
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "cpu_stat": {"total_jiffies": 1000, "softirq": 100},
            "softirqs": {"net_rx": 1000, "net_tx": 500},
        }
        after = copy.deepcopy(before)
        after.update(timestamp_monotonic_ns=11_000_000_000, timestamp_utc="2026-01-01T00:00:10Z")
        after["cpu_stat"] = {"total_jiffies": 2000, "softirq": 150}
        after["softirqs"] = {"net_rx": 3000, "net_tx": 800}
        return before, after

    def compute(self, before, after):
        with tempfile.TemporaryDirectory() as tmp:
            before_path, after_path = Path(tmp) / "before.json", Path(tmp) / "after.json"
            before_path.write_text(json.dumps(before), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            return softirq.compute_delta(str(before_path), str(after_path), "test", 1)

    def test_formula(self):
        result = self.compute(*self.snapshots())
        self.assertEqual(result["metrics"]["delta_total_jiffies"], 1000)
        self.assertEqual(result["metrics"]["delta_softirq_jiffies"], 50)
        self.assertEqual(result["metrics"]["softirq_percent"], 5.0)
        self.assertEqual(result["duration_sec"], 10.0)

    def test_identity_mismatch_fails(self):
        before, after = self.snapshots()
        after["instance_id"] = "i-other"
        with self.assertRaises(ValueError):
            self.compute(before, after)

    def test_non_positive_duration_fails(self):
        before, after = self.snapshots()
        after["timestamp_monotonic_ns"] = before["timestamp_monotonic_ns"]
        with self.assertRaises(ValueError):
            self.compute(before, after)

    def test_counter_reset_fails(self):
        before, after = self.snapshots()
        after["cpu_stat"]["total_jiffies"] = 999
        with self.assertRaises(ValueError):
            self.compute(before, after)


class StatisticalTests(unittest.TestCase):
    def test_percentile_linear_interpolation(self):
        self.assertEqual(analysis.calculate_percentile([1, 2, 3, 4], 50), 2.5)

    def test_numeric_underflow_is_never_reported_as_zero(self):
        info = analysis.student_t_two_sided_p_value(1e9, 100)
        self.assertIsNone(info["p_value"])
        self.assertTrue(info["numeric_underflow"])
        self.assertEqual(info["formatted"], "< 1e-300")

    def test_hierarchical_bootstrap_is_reproducible_and_run_aware(self):
        a = {1: [1.0] * 20, 2: [2.0] * 20, 3: [3.0] * 20}
        b = {1: [2.0] * 20, 2: [3.0] * 20, 3: [4.0] * 20}
        random.seed(42)
        result = analysis.hierarchical_bootstrap_p99_delta(a, b, num_resamples=200)
        self.assertEqual(result["statistical_unit"], "independent_run")
        self.assertEqual(result["independent_runs"], 3)
        self.assertAlmostEqual(result["estimate_delta_ms"], 1.0)

    def test_generic_hierarchical_bootstrap_preserves_paired_run_unit(self):
        a = {1: [10.0, 10.0], 2: [20.0, 20.0], 3: [30.0, 30.0]}
        b = {1: [8.0, 8.0], 2: [18.0, 18.0], 3: [28.0, 28.0]}
        random.seed(42)
        result = analysis.hierarchical_bootstrap_paired_effect(
            a, b, statistic="mean", num_resamples=200,
            effect_name="b_minus_a", unit="percentage_points")
        self.assertEqual(result["statistical_unit"], "independent_run")
        self.assertEqual(len(result["run_level_results"]), 3)
        self.assertAlmostEqual(result["estimate"], -2.0)
        self.assertEqual(result["ci_95"], [-2.0, -2.0])

    def test_welch_is_machine_labeled_exploratory(self):
        result = analysis.welch_t_test([1.0, 2.0, 3.0], [2.0, 3.0, 5.0])
        self.assertEqual(result["interpretation"], "exploratory_only_pooled_observations")


class ExporterSchemaTests(unittest.TestCase):
    def test_current_summary_schema(self):
        stats = json.loads((ROOT / "results/summary_statistics.json").read_text(encoding="utf-8"))
        self.assertEqual(exporter.validate_stats_schema(stats), (True, "Schema OK"))

    def test_missing_nested_field_fails(self):
        stats = json.loads((ROOT / "results/summary_statistics.json").read_text(encoding="utf-8"))
        del stats["tc04_ebpf_xdp"]["xdp_native"]["pps_drop"]
        ok, message = exporter.validate_stats_schema(stats)
        self.assertFalse(ok)
        self.assertIn("pps_drop", message)

    def test_exporter_contains_no_random_metric_generation(self):
        text = (ROOT / "monitoring/mock_metrics_exporter.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", text)
        self.assertNotIn("random.uniform", text)
        self.assertNotIn("demo_simulated_rtt", text)
        self.assertNotIn('dataset_version="2.0.0"', text)
        self.assertNotIn("}} 92.4", text)
        self.assertNotIn("}} 173.4", text)
        self.assertNotIn("}} 985.0", text)

    def test_compose_mounts_summary_and_prometheus_has_single_exporter_target(self):
        compose = (ROOT / "monitoring/docker-compose.yml").read_text(encoding="utf-8")
        prometheus = (ROOT / "monitoring/prometheus/prometheus.yml").read_text(encoding="utf-8")
        dashboard = json.loads((ROOT / "monitoring/grafana/dashboards/network_performance_p95_p99.json").read_text(encoding="utf-8"))
        self.assertIn("../results/summary_statistics.json:/results/summary_statistics.json:ro", compose)
        self.assertIn("targets: ['mock-metrics-exporter:9100']", prometheus)
        self.assertNotIn("host.docker.internal:9100", prometheus)
        self.assertEqual(dashboard["panels"][0]["type"], "text")
        self.assertIn("NOT AWS TELEMETRY", dashboard["panels"][0]["options"]["content"])


class DocumentationConsistencyTests(unittest.TestCase):
    def test_primary_effects_are_synchronized_with_summary(self):
        stats = json.loads((ROOT / "results/summary_statistics.json").read_text(encoding="utf-8"))
        combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
            "README.md", "docs/PERFORMANCE_ANALYSIS_REPORT.md",
            "docs/CAPSTONE_THESIS_AND_SLIDES_TEMPLATE.md"))
        expected_tokens = [
            f'{stats["tc01_peering_tgw"]["hierarchical_p99_effect"]["estimate"]:.3f}',
            f'{stats["tc02_jumbo_frames"]["hierarchical_softirq_effect"]["estimate"]:.2f}',
            f'{stats["tc02_jumbo_frames"]["hierarchical_throughput_effect"]["estimate"]:.3f}',
            f'{stats["tc03_privatelink"]["hierarchical_p99_effect"]["estimate"]:.3f}',
            f'{stats["tc04_ebpf_xdp"]["hierarchical_softirq_effect"]["estimate"]:.2f}',
            f'{stats["tc04_ebpf_xdp"]["hierarchical_probe_latency_effect"]["estimate"]:.3f}',
        ]
        for token in expected_tokens:
            self.assertIn(token, combined)

    def test_structure_avoids_mode_a_empirical_overclaim(self):
        text = (ROOT / "STRUCTURE.md").read_text(encoding="utf-8")
        self.assertNotIn("số liệu thực nghiệm chuẩn Chế độ A", text)


class ArchitectureContractTests(unittest.TestCase):
    def test_runner_requires_explicit_remote_or_local_mode(self):
        text = (ROOT / "scripts/benchmark_runner.sh").read_text(encoding="utf-8")
        self.assertIn('EXECUTION_MODE="${EXECUTION_MODE:-aws-remote}"', text)
        self.assertIn("aws ssm get-command-invocation", text)
        self.assertIn("ResponseCode", text)
        self.assertIn("___DUT_SNAPSHOT_JSON_BEGIN___", text)
        self.assertNotIn('elif [ -f "${DUT_CONTROLLER}" ]', text)

    def test_xdp_native_verification_is_fail_fast(self):
        text = (ROOT / "scripts/dut_server_setup.sh").read_text(encoding="utf-8")
        for required in ("ip -details link show", "xdpgeneric", "bpftool net show", "xdp_config_map", "xdp_stats_map"):
            self.assertIn(required, text)
        self.assertNotIn("xdp_drop_counter", text)

    def test_standalone_loader_verifies_native_hook_and_maps(self):
        text = (ROOT / "ebpf/ebpf_loader.sh").read_text(encoding="utf-8")
        for required in ("verify_native_hook", "ip -details link show", "xdpgeneric",
                         "bpftool net show", "xdp_config_map", "xdp_stats_map"):
            self.assertIn(required, text)
        self.assertNotIn("xdp off 2>/dev/null || true", text)

    def test_xdp_c_has_modern_maps_and_verifier_bounds(self):
        text = (ROOT / "ebpf/xdp_packet_filter.c").read_text(encoding="utf-8")
        for required in ('SEC("xdp")', 'SEC(".maps")', "BPF_MAP_TYPE_PERCPU_ARRAY",
                         "BPF_MAP_TYPE_ARRAY", "data_end", "ip->ihl < 5",
                         "IP_OFFSET | IP_MF", "bpf_htons(TARGET_BENCHMARK_PORT)"):
            self.assertIn(required, text)

    def test_terraform_tc01_controls_and_private_endpoints(self):
        text = (ROOT / "terraform/main.tf").read_text(encoding="utf-8")
        subnet_b1 = hcl_resource_block(text, "aws_subnet", "subnet_b1")
        subnet_b2 = hcl_resource_block(text, "aws_subnet", "subnet_b2")
        self.assertIn('availability_zone = "${var.aws_region}a"', subnet_b1)
        self.assertIn('availability_zone = "${var.aws_region}a"', subnet_b2)
        for server in ("ec2_server_b1", "ec2_server_b2"):
            block = hcl_resource_block(text, "aws_instance", server)
            self.assertIn("instance_type", block)
            self.assertNotIn("placement_group", block)
        for suffix in ("b", "shared"):
            for service in ("ssm", "ssmmessages", "ec2messages"):
                block = hcl_resource_block(text, "aws_vpc_endpoint", f"{service}_endpoint_{suffix}")
                self.assertIn(f'.{service}"', block)
                self.assertIn('private_dns_enabled = true', block)
        shared_sg = hcl_resource_block(text, "aws_security_group", "sg_vpc_endpoints_shared")
        self.assertIn("from_port   = 443", shared_sg)
        self.assertIn("to_port     = 443", shared_sg)

    def test_mode_a_titles_are_explicit(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        report = (ROOT / "docs/PERFORMANCE_ANALYSIS_REPORT.md").read_text(encoding="utf-8")
        slides = (ROOT / "docs/CAPSTONE_THESIS_AND_SLIDES_TEMPLATE.md").read_text(encoding="utf-8")
        self.assertIn("Not Yet an Empirical AWS Measurement", readme)
        self.assertIn("CALIBRATED REFERENCE BENCHMARK REPORT – METHODOLOGY PROTOTYPE", report)
        self.assertIn("Methodology Prototype", slides)
        self.assertNotIn("CHƯƠNG 4: KẾT QUẢ THỰC NGHIỆM", slides)


if __name__ == "__main__":
    unittest.main(verbosity=2)
