# Repository Structure

```text
NT531/
├── experiment.yaml                    # Version-2 three-test contract
├── terraform/                         # us-east-1 two-VPC/three-node infrastructure
├── scripts/
│   ├── aws_controller.ps1             # Workstation deploy-control and artifact retrieval
│   ├── preflight_check.sh             # Runs on EC2 client; fail-closed AWS validation
│   ├── benchmark_runner.sh             # Runs on EC2 client; no local-emulation path
│   ├── benchmarks/                     # TC01, TC02, TC03 collectors
│   ├── lib/                            # SSM, metrics, metadata helpers
│   ├── manage_run_artifacts.py         # Immutable run manifests/checksums
│   ├── analyze_mode_b.py               # Unified empirical analyzer
│   └── generate_mode_b_graphs.py       # Four registered final PNGs
├── ebpf/                               # XDP filter, loader, and native-mode gates
├── docs/
│   ├── IMPLEMENTATION_AUDIT.md
│   ├── MODE_B_EXPERIMENTAL_PROTOCOL.md
│   ├── MODE_B_IMPLEMENTATION_ROADMAP.md
│   └── FINAL_EXPERIMENT_REPORT.md
├── tests/                              # Offline integrity and contract tests
└── results/
    ├── raw/                            # Historical Mode A synthetic evidence only
    ├── mode_b/                         # Real AWS preflight/controller/run trees
    └── final_summary.json              # Created only after validated final N>=10
```

Older theory, console, Mode A analysis, thesis, and monitoring files are retained as historical/supporting material. They are not part of the active three-test Mode B evidence path.
