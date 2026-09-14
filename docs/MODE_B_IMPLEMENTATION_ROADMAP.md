# MODE B IMPLEMENTATION ROADMAP

> **Status**: Work plan to transition from Mode A (methodology prototype, 9.62/10) to Mode B (empirical AWS measurement).  
> **Target**: Executable, fail-closed AWS experiment with N≥10, run-tree provenance, saturation analysis, decision framework.

---

## PHASE 1: TC Design Refinement

### 1.1 TC-01: Peering vs TGW (Host Confounding)

**Current**: B1 (peering path) and B2 (tgw path) are different hosts.

**Problem**: Host placement variation confounds routing effect.

**Solutions** (pick one):

**Option A: Metadata-aware constrained claim** (minimal infra change)
- Keep B1/B2 separate
- Log `host_id` and `path` in manifest
- Report: "observed path-configuration association conditional on host assignment"
- Limitation: a fixed host/path pairing cannot estimate or remove the host effect

**Option B: Dual-path single target** (requires routing change)
- Deploy B3 in new subnet with both peering + TGW routes
- Client A selects path via destination IP or policy routing
- Same host for both conditions
- Requires Terraform refactor

**Option C: Crossover with host swap** (current infra)
```text
Run 1: B1→peering, B2→tgw
Run 2: B1→tgw, B2→peering (swap routes)
Run N: randomized
```
- Requires dynamic route table mutation
- Risky for fail-closed protocol
- Runner complexity high

**Recommendation**: **Option A** only for tooling pilot (N=3). Use Option B or a balanced Option C before making a causal route claim.

**Action**:
- [x] Record target instance identity and path in each run manifest
- [x] Analyzer exposes the host/path confounding and restricts the allowed claim
- [ ] Implement same-backend dual path or balanced host-path crossover for causal RQ1

---

### 1.2 TC-02: MTU × Parallel Streams (2D Matrix)

**Current**: MTU 1500 vs 9001, single parallel config (P=4).

**Target**: Full matrix MTU × {1, 4, 8} streams.

**Matrix**:
```text
MTU 1500
  ├─ P1
  ├─ P4
  └─ P8

MTU 9001
  ├─ P1
  ├─ P4
  └─ P8
```

**Metrics per cell**:
- Throughput (Gbps)
- PPS
- SoftIRQ delta (%)
- CPU (%)
- Retransmit count
- ENA queue depth

**Actions**:
- [x] Refactor `tc02_mtu.sh` to loop `mtu × streams`
- [x] Update `experiment.yaml`: `parallel_streams: [1, 4, 8]`
- [x] Randomize cell order within run
- [x] Separate output dirs for all six cells
- [x] Analyzer reports paired effects separately for P1/P4/P8

---

### 1.3 TC-03: Functional vs Performance Split

**Current**: TC-03 conflates overlapping CIDR validation with PrivateLink performance overhead.

**Target**: Split into TC-03F (functional) and TC-03P (performance).

**TC-03F: Overlapping CIDR Architecture Validation**
- Purpose: prove PrivateLink resolves CIDR conflict
- Method: deploy `10.3.0.0/16` in both VPC A and Shared
- Measure: connectivity PASS/FAIL
- Output: `tc03f_functional_validation.json`
- Not part of performance RQ; pure architecture demo

**TC-03P: PrivateLink Performance Overhead**
- RQ3: "PrivateLink pays how much latency for service isolation?"
- Compare: direct path vs PrivateLink to **same backend**
- Metrics: P50/P95/P99 RTT, throughput
- Must use same EC2 instance as target
- Paired run-level delta

**Actions**:
- [ ] Separate `tc03_functional.sh` and `tc03_performance.sh`
- [ ] TC-03F runs once per experiment (not per run)
- [ ] TC-03P runs every run with randomized order
- [ ] Protocol: state TC-03F is not replicated performance evidence

---

### 1.4 TC-04: Saturation Point Detection

**Current**: Fixed load stages, manual saturation interpretation.

**Target**: Automated saturation detection with fail-fast.

**Saturation criteria** (from protocol):
```python
saturated = (
    legitimate_loss_pct > 1.0 or
    legitimate_p99_ms > 5.0 or
    cpu_sustained_pct > 90.0
)
```

**Enhancement**:
- [x] After each stage, check saturation in `tc04_packet_processing.sh`
- [x] If saturated: log threshold and stop increasing load per condition
- [x] Report achieved load from iperf3 sender packets/duration versus target load
- [x] Keep target and achieved PPS as separate fields
- [x] Schema example: `load_target_pps=1000000 achieved_load_pps=850000 saturated=true`

**Actions**:
- [x] Add fail-closed `check_saturation()` using `evaluate_saturation.py`
- [x] Parse legitimate probe output for loss/P99
- [x] Calculate CPU busy percentage from before/after `/proc/stat` deltas
- [x] Write `tc04/saturation_events.jsonl`

---

## PHASE 2: Analyzer & Provenance

### 2.1 Mode B Run-Tree Schema

**Current**: Mode A uses flat `results/raw/*.csv|json`.

**Mode B schema**:
```text
results/mode_b/
└── <experiment_id>/
    ├── experiment.yaml (snapshot)
    ├── plan.json
    └── run_001/
        ├── manifest.json
        ├── environment.json
        ├── tc01/
        │   ├── peering/
        │   │   ├── latency.txt
        │   │   └── metadata.json
        │   └── tgw/
        │       ├── latency.txt
        │       └── metadata.json
        ├── tc02/
        │   ├── mtu_1500_p1/
        │   ├── mtu_1500_p4/
        │   └── ...
        ├── tc03p/
        ├── tc04/
        │   ├── load_100000/
        │   │   ├── iptables/
        │   │   └── xdp/
        │   └── saturation_events.jsonl
        └── checksums.sha256
```

**Actions**:
- [x] Create `scripts/analyze_mode_b.py` with `analyze_tc01()` … `analyze_tc04()`
- [x] Load all runs and reject incomplete run/cell coverage
- [x] Validate checksum coverage and digest per run
- [x] Compute paired run-level deltas
- [x] Use honestly labeled paired run-level bootstrap for Mode B summary artifacts
- [x] Detect per-run TC-04 saturation with right-censoring semantics
- [x] Output `results/mode_b/<exp_id>/mode_b_summary.json`

---

### 2.2 Provenance Requirements

Per `MODE_B_EXPERIMENTAL_PROTOCOL.md`, each run must have:
- Region, AZ, instance ID/type, AMI, kernel, ENA version
- Interface, MTU, TCP congestion control, IRQ affinity
- GRO/GSO/TSO state
- Tool versions (iperf3, sockperf, bpftool)
- Git commit SHA
- Random seed, condition order
- SSM command IDs
- Before/after snapshots (SoftIRQ, ENA counters, iptables/XDP stats)

**Actions**:
- [ ] Enhance `collect_environment_manifest.py` for Mode B
- [ ] Collect from DUT via SSM: `uname -r`, `modinfo ena`, `ethtool -k eth0`
- [ ] Write to `run_NNN/environment.json`
- [ ] `manage_run_artifacts.py finalize` locks all files + SHA256

---

## PHASE 3: Decision Framework

**Purpose**: Answer "when to switch architecture?"

**Template structure** (`docs/DECISION_FRAMEWORK.md`):

### 3.1 Performance Boundaries

For each TC, plot saturation point or performance vs cost tradeoff:

**TC-01: Peering vs TGW**
- X-axis: topology complexity (# VPCs, # spoke-to-spoke flows)
- Y-axis: P99 latency + monthly cost
- Decision rule: TGW when `VPC_count > N` or `inter-vpc_flows > M`

**TC-02: MTU Selection**
- X-axis: workload (bulk transfer, streaming, RPC)
- Y-axis: throughput, SoftIRQ %
- Decision rule: Jumbo when `sustained_Gbps > X` and `path_supports_9001`

**TC-03: Direct vs PrivateLink**
- X-axis: isolation requirement (partner, multi-tenant SaaS)
- Y-axis: P99 overhead (ms), cost ($/GB)
- Decision rule: PrivateLink when `isolation=required` and `latency_budget > +0.4ms`

**TC-04: iptables vs XDP**
- X-axis: offered load (PPS)
- Y-axis: legitimate P99, drop rate, CPU
- Decision rule: XDP when `PPS > saturation_iptables` and `kernel_supports_xdp`

**Actions**:
- [ ] Create `docs/DECISION_FRAMEWORK.md`
- [ ] Define decision tree per TC
- [ ] Include cost snapshot (TGW $0.02/GB, PrivateLink $0.01/GB + $0.01/h)
- [ ] Limitations: single region, instance type, kernel

---

## PHASE 4: AWS Execution Checklist

### 4.1 Pre-deployment

- [ ] Review `terraform.tfvars.example` → create `terraform.tfvars`
- [ ] Set `aws_region`, `benchmark_ami_id`, `instance_type`
- [ ] `terraform plan` → review placement, routing, endpoints
- [ ] Estimate cost: pilot N=3 ~$5, final N=20 ~$30-50

### 4.2 Deployment

- [ ] `terraform apply`
- [ ] Capture outputs: `terraform output -json > inventory.json`
- [ ] Extract IPs: `TARGET_PEERING_IP`, `TARGET_TGW_IP`, etc.
- [ ] Wait for SSM online: `aws ssm describe-instance-information`

### 4.3 Preflight

```bash
export DUT_INSTANCE_ID=$(jq -r .server_b1_instance_id.value inventory.json)
bash scripts/preflight_check.sh --scope aws --profile pilot --dut-instance-id "$DUT_INSTANCE_ID"
```

Must PASS:
- AWS identity
- SSM online for all DUTs
- Interface `eth0` up
- Commands: `iperf3`, `sockperf`, `bpftool`, `clang`
- XDP native support (not generic)

### 4.4 Pilot Run

```bash
export TARGET_PEERING_IP=$(jq -r .server_b1_peering_ip.value inventory.json)
export TARGET_TGW_IP=$(jq -r .server_b2_tgw_ip.value inventory.json)
export DIRECT_TARGET_IP=$(jq -r .shared_server_direct_ip.value inventory.json)
export PRIVATELINK_ENDPOINT_IP=$(jq -r .privatelink_endpoint_ip.value inventory.json)

bash scripts/benchmark_runner.sh \
  --execute \
  --execution-mode aws-remote \
  --profile pilot \
  --experiment-id pilot_001
```

### 4.5 Validation

- [ ] Check `results/mode_b/pilot_001/run_00*/checksums.sha256` all PASS
- [ ] No missing TC outputs
- [ ] `analyze_mode_b.py` runs without error
- [ ] Summary CI non-empty
- [ ] Review saturation events from TC-04

### 4.6 Final Run

- [ ] Repeat with `--profile final` (N=10 or N=20)
- [ ] Duration: ~45 min per run → 7-15 hours total
- [ ] Monitor CloudWatch for throttling, SSM failures
- [ ] After completion: `terraform destroy` to stop billing

---

## PHASE 5: Report & Defense

### 5.1 Update Documents

- [ ] `README.md`: change watermark to `empirical=true, mode=B`
- [ ] `PERFORMANCE_ANALYSIS_REPORT.md`: replace Mode A data with Mode B
- [ ] `ACADEMIC_EVIDENCE_MATRIX.md`: mark Mode B rows COMPLETE
- [ ] `FINAL_MODE_A_READINESS_AUDIT.md` → archive or rename

### 5.2 Graphs

Generate from `summary.json`:
- TC-01: Box plot P99 by condition + run
- TC-02: Heatmap throughput (MTU × streams)
- TC-03: Bar chart direct vs PrivateLink overhead
- TC-04: Line plot PPS vs P99 (iptables vs XDP), mark saturation

Tools: Python (matplotlib/seaborn) or Grafana snapshots.

### 5.3 Thesis Chapters

1. Problem, Motivation, RQs
2. AWS + ENA + Linux + XDP background
3. Experimental Methodology (cite protocol)
4. Results (Mode B data)
5. Discussion, Decision Framework, Limitations

### 5.4 Slides (12-15)

1. Problem
2. Why it matters
3. Research Questions
4. Architecture diagram
5. Experimental method
6-9. TC-01 to TC-04 results
10. Saturation point
11. Cost/performance tradeoff
12. Decision Framework
13. Limitations
14. Contribution
15. Demo / Q&A

### 5.5 Defense Prep

- [ ] Run demo: `--plan-only` → show deterministic schedule
- [ ] Reproduce analysis: `analyze_mode_b.py` → same summary
- [ ] Q&A scenarios:
  - "Why N=10 not N=100?" → cost, time, cloud variability
  - "Can this generalize to other regions?" → no, limitations clear
  - "Why not DPDK?" → scope, thesis boundary
  - "How to handle noisy neighbor?" → randomization, replication, report variance

---

## MILESTONE GATES

### M1: Methodology Ready
- [x] TC-01 host tracking and constrained claim
- [x] TC-02 2D matrix
- [ ] TC-03 split F/P
- [x] TC-04 saturation auto-detect using CPU deltas and achieved PPS
- [x] Mode B analyzer for TC-01..TC-04 with incomplete-data gates

### M2: AWS Ready
- [ ] Terraform deploy PASS
- [ ] Preflight --scope aws PASS
- [ ] SSM all DUTs online
- [ ] XDP native verified
- [ ] PrivateLink healthy

### M3: Data Ready
- [ ] Pilot N=3 complete
- [ ] All checksums PASS
- [ ] No missing TC outputs
- [ ] Saturation detected TC-04
- [ ] Summary reproducible

### M4: Defense Ready
- [ ] Final N≥10 complete
- [ ] Graphs rendered
- [ ] Decision Framework written
- [ ] Report Mode B version
- [ ] Slides + demo script
- [ ] Limitations documented

---

## PRIORITY ORDER

1. **TC-04 saturation** (highest scientific contribution)
2. **TC-02 matrix** (expands performance space)
3. **Mode B analyzer** (enables empirical claims)
4. **Decision Framework** (practical impact)
5. **TC-01 crossover** (optional refinement)
6. **TC-03 split** (clarity, not new RQ)

ponytail: full crossover (Option C) deferred; if host effect dominates routing effect in pilot, revisit.
