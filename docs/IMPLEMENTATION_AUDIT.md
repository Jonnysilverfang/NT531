# Implementation Audit — AWS Empirical Network Performance

> Audit baseline: commit `ac5f39b` on 2026-09-14. This document records the repository state **before** the us-east-1 empirical implementation is changed. It is not AWS execution evidence.

## 1. Executive finding

The repository has a useful fail-closed Mode B artifact and analysis foundation, but the checked-in implementation cannot yet execute the requested three-test empirical study end to end. The current infrastructure and experiment schema still describe the former non-target-Region four-test design, including PrivateLink and placement-group resources. No Terraform apply, AWS preflight, pilot, final run, or empirical raw-data tree exists in this checkout.

Current readiness verdict: **NOT READY FOR AWS EXECUTION**.

## 2. Requested final experiment contract

The implementation must converge on exactly these test groups:

1. **TC01 — VPC Peering versus Transit Gateway**: RTT P50/P95/P99, jitter, and packet loss using `sockperf` and `ping`.
2. **TC02 — MTU and parallel streams**: MTU 1500/9001 crossed with 1/4/8 streams; collect throughput, PPS, host CPU, SoftIRQ, and TCP retransmits using `iperf3`, `ethtool`, and `/proc` counters.
3. **TC03 — Linux packet-processing saturation**: iptables versus verified XDP native mode under an increasing UDP offered-load sweep beginning at 100 kpps; measure maximum sustainable PPS, achieved RX/TX PPS, CPU, SoftIRQ, P99 probe latency, and loss.

The authoritative Region/AZ contract is `us-east-1` / `us-east-1a`. Mode B traffic must originate from the EC2 client, all host control must use Systems Manager, and empirical results must never be synthesized.

## 3. Repository implementation findings

### 3.1 Experiment schema and orchestration

- `experiment.yaml` is pinned to the former non-target Region and contains four test cases. Its TC03 is direct versus PrivateLink and its TC04 is iptables versus XDP.
- `scripts/load_experiment_config.py`, `scripts/generate_run_plan.py`, `scripts/manage_run_artifacts.py`, `scripts/benchmark_runner.sh`, and `scripts/analyze_mode_b.py` encode the same four-test schema.
- `benchmark_runner.sh` expects PrivateLink inventory and sources `tc03_privatelink.sh` plus `tc04_packet_processing.sh`; this is incompatible with the requested three-test contract.
- The benchmark runner is designed to execute on Linux, but there is no complete controller path that stages this repository on the EC2 client and invokes the run through SSM. Running it from the Windows workstation would violate the “EC2 client is the traffic source” requirement.
- The artifact manager provides useful immutable-run controls, manifests, and checksums. These should be retained and tightened rather than replaced.

### 3.2 Terraform and network topology

- Terraform defaults to N. Virginia and requires a manually supplied baked AMI. The example variable file contains an unusable AMI placeholder and an SSH key name.
- The graph provisions three VPCs, PrivateLink/NLB resources, a placement group, and six EC2 instances. These resources are outside the requested final scope and add cost and confounders.
- The client and DUTs share one IAM instance profile with only `AmazonSSMManagedInstanceCore`. The EC2 client therefore lacks the required least-privilege `ssm:SendCommand` and `ssm:GetCommandInvocation` permissions for DUT control.
- An SSH ingress rule and SSH configuration variables remain despite the explicit SSM-only control requirement.
- Security groups allow broad `10.0.0.0/8` traffic instead of only the benchmark paths and ports.
- The TGW attachments reuse workload subnets, and VPC A attaches two AZs. The requested study is single-AZ and should use dedicated `/28` TGW attachment subnets in `us-east-1a` to avoid attachment/workload ambiguity.
- TC01 currently compares two different destination instances. Keeping separate routed subnets is operationally simple but leaves residual host-placement confounding. The report must constrain causal claims unless a crossover/same-DUT routing design is implemented.
- The requested VPC-B `10.2.1.0/24` alone cannot provide distinct symmetric Peering and TGW return paths for two servers. A second workload subnet is methodologically necessary unless policy routing or ENI reassignment is introduced. The smallest deterministic design is B1 in `10.2.1.0/24` through Peering and B2 in `10.2.2.0/24` through TGW, both in `us-east-1a`, with identical AMI/type/security group.
- VPC/TGW flow-log evidence, encrypted log destinations, and explicit retention are absent.

### 3.3 Preflight and measurement validity

- `preflight_check.sh` defaults to N. Virginia and checks only one DUT for SSM Online state.
- It does not verify all instance identities, AMI equality, instance type, AZ, route tables, security-group ports, path MTU, ENA driver, XDP driver/native attach evidence, clock state, server daemons, or client-to-target reachability.
- Merely finding `bpftool` and `clang` is not proof of XDP native mode. Execution must record `ip -details link`, `bpftool net`, program ID/tag, ENA driver/version, and a fail-closed native attach result for every applicable run.
- The requested pilot/final sequence is not enforced as a controller workflow. The current config even aliases `validation` and `pilot` to three runs without recording an AWS deployment gate between them.
- There is no graph generator for the four required PNG outputs and no `results/final_summary.json` aggregator.

### 3.4 Documentation consistency

- README and multiple documents still identify the former Region, four test cases, PrivateLink, placement groups, or Mode A modeled results as the central design.
- Historical Mode A files can remain as clearly labeled historical methodology evidence, but active Mode B protocol, deployment, commands, outputs, and final report must not mix synthetic and empirical claims.
- `docs/FINAL_EXPERIMENT_REPORT.md` does not exist. It must remain explicitly incomplete until real AWS artifacts pass checksum, completeness, environment, and native-XDP gates.

## 4. Live-access findings at audit time

- The local AWS CLI has no usable credentials.
- A read-only managed AWS API call returned account `411509276671` and principal `arn:aws:iam::411509276671:user/kien1`.
- That principal is a long-lived IAM user, not the short-lived assumed role or IAM Identity Center session required for this deployment gate. No resource creation is authorized from it.
- TGW route-table segmentation intent is not yet confirmed. The safe pending default is a dedicated experiment TGW with flat connectivity limited to the two experiment attachments, but creation must wait for an explicit answer.

## 5. Required remediation sequence

1. Replace the active schema with exactly TC01/TC02/TC03 and pin `us-east-1` / `us-east-1a`.
2. Reduce Terraform to VPC A, VPC B, Peering, TGW, dedicated attachment subnets, three c6i.large AL2023 instances, SSM-only control, least-privilege split IAM roles, encrypted flow logs, and explicit outputs.
3. Add a fail-closed AWS controller that stages a versioned bundle on the EC2 client and invokes preflight/benchmark through SSM; the workstation must never generate benchmark traffic.
4. Expand preflight to validate identity, Region/AZ/AMI/type, SSM state for all instances, routes, required ports, MTU reachability, ENA, server processes, and verified XDP native capability.
5. Refactor collection and analysis for the three-test schema, preserve raw artifacts/checksums, and emit `results/final_summary.json` plus the four required graphs.
6. Run offline tests and `terraform fmt/init/validate/plan` before any apply.
7. After a short-lived deployment role and TGW intent are confirmed: apply, wait for SSM, run AWS preflight, execute pilot N=3, review gates, execute final N=10, analyze, graph, and write the evidence-backed final report.

## 6. Hard gates

The following states must stop execution rather than be skipped:

- wrong account, Region, AZ, AMI, instance type, or target identity;
- any required managed instance not `Online` in SSM;
- missing/asymmetric routes, blocked benchmark ports, unexpected MTU behavior, or failed reachability;
- unverified ENA driver or XDP generic/offload mode when native mode is required;
- missing run/cell/telemetry, checksum mismatch, environment drift, or overwritten run directory;
- absent pilot acceptance decision before final N=10;
- any request to label Mode A/local-emulation data as Mode B empirical AWS data.

Until all gates pass against real AWS artifacts, the honest project status remains: **implementation in progress; no empirical AWS conclusion**.
