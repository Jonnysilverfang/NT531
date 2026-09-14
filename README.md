# NT531 — AWS Empirical Network Performance Evaluation

> Current status: implementation and Terraform plan validated; **no AWS resources have been applied and no empirical results exist yet**.

This repository evaluates network performance on real AWS infrastructure in `us-east-1`, constrained to `us-east-1a`. It separates historical Mode A synthetic methodology artifacts from Mode B empirical evidence. Only a checksum-verified Mode B final run may support findings in the final report.

## Registered research scope

| Test | Comparison | Primary outputs |
|---|---|---|
| TC01 | VPC Peering vs Transit Gateway | RTT P50/P95/P99, ping jitter/mdev, packet loss |
| TC02 | MTU 1500/9001 × iperf3 streams 1/4/8 | Gbps, ENA RX/TX PPS, DUT CPU, SoftIRQ, retransmits |
| TC03 | iptables vs verified XDP native under increasing UDP load | target/achieved/DUT RX PPS, maximum sustainable PPS, CPU, SoftIRQ, P99, loss |

PrivateLink, placement groups, security benchmarking, and architecture scoring are outside the active experiment.

## AWS topology

```text
EC2 client — c6i.large / AL2023 / 10.1.1.10 / us-east-1a
  ├── 10.2.1.10 ── VPC Peering ── EC2 server-b1 (TC01, TC02, TC03 DUT)
  └── 10.2.2.10 ── Transit Gateway ── EC2 server-b2 (TC01 target)

VPC A 10.1.0.0/16                       VPC B 10.2.0.0/16
  workload 10.1.1.0/24                    peering workload 10.2.1.0/24
  TGW attach 10.1.255.0/28                TGW workload 10.2.2.0/24
                                             TGW attach 10.2.255.0/28
```

All three instances use the same resolved AMI, instance type, and AZ. There is no SSH ingress. The workstation only deploys, stages a hash-addressed runtime bundle, and invokes SSM; benchmark traffic originates on the EC2 client. The client role can send only `AWS-RunShellScript` commands to the two experiment servers.

TC01 still changes both route and destination host. Its permitted claim is therefore an observed path-configuration association conditional on the recorded host assignment, not an isolated causal TGW effect.

## Evidence workflow

1. Review [the implementation audit](docs/IMPLEMENTATION_AUDIT.md) and [registered protocol](docs/MODE_B_EXPERIMENTAL_PROTOCOL.md).
2. Authenticate with an assumed role or IAM Identity Center session. The controller refuses an IAM-user identity.
3. Run Terraform `fmt`, `init`, `validate`, and `plan`; review the billable components and explicit flat two-spoke TGW route table.
4. Apply only after the account and TGW-intent gates are approved.
5. Run AWS preflight from the EC2 client through SSM.
6. Execute pilot N=3, analyze and explicitly accept it.
7. Execute final N=10, seal checksums, analyze, graph, and complete the report.

```powershell
terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan

# After reviewed apply and SSM Online:
.\scripts\aws_controller.ps1 -Phase Preflight -Profile <assumed-role-profile>
.\scripts\aws_controller.ps1 -Phase Pilot -Profile <assumed-role-profile>
.\scripts\aws_controller.ps1 -Phase Final -Profile <assumed-role-profile> `
  -PilotSummary <pilot-summary-path>
```

The final controller writes `results/final_summary.json` and the following experiment-scoped figures:

- `tc01_latency.png`
- `tc02_mtu_throughput.png`
- `tc02_softirq.png`
- `tc03_xdp_saturation.png`

## Fail-closed gates

Execution stops on wrong account/Region/AZ/AMI/type, any SSM node not Online, route or port mismatch, failed jumbo-frame probe, non-ENA driver, generic/unverified XDP, missing cells, configuration drift, checksum mismatch, overwrite attempts, or absent pilot acceptance.

The current evidence status is tracked in [MODE_B_READINESS_REPORT.md](MODE_B_READINESS_REPORT.md). The final narrative belongs in [docs/FINAL_EXPERIMENT_REPORT.md](docs/FINAL_EXPERIMENT_REPORT.md) and must remain incomplete until real final artifacts pass every gate.

## Historical Mode A material

`results/raw`, `results/summary_statistics.json`, and older analysis documents are synthetic methodology-prototype artifacts with `empirical=false`. They are retained for provenance and regression testing only; they are never inputs to the Mode B analyzer.
