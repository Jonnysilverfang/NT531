# Final AWS Network Performance Experiment Report

> Status: **INCOMPLETE — NO EMPIRICAL AWS DATA YET**. This file is a controlled report shell, not evidence that the experiment ran.

## Environment

- Account: pending assumed-role deployment evidence
- Region/AZ: `us-east-1` / `us-east-1a`
- Instance type: `c6i.large`
- Resolved AL2023 AMI: pending apply inventory
- Kernel/ENA/tool versions: pending preflight manifest
- Pilot experiment ID: pending
- Final experiment ID: pending
- Final run count: 0/10

## Execution gates

| Gate | Status | Evidence |
|---|---|---|
| Terraform apply | Not run | — |
| SSM Online (3/3) | Not run | — |
| Route/port/MTU preflight | Not run | — |
| Native XDP capability | Not run | — |
| Pilot N=3 accepted | Not run | — |
| Final N=10 checksum-valid | Not run | — |
| Unified analyzer | Not run | — |
| Graph generation | Not run | — |

## TC01 — Peering versus TGW

No results. Report P50/P95/P99, jitter, loss, paired P99 delta, CI, host assignments, and the residual host/path confound only after final evidence validates.

## TC02 — MTU × streams

No results. Report all six cells for throughput, ENA PPS, CPU, SoftIRQ, retransmits, paired MTU effects, and any ENA allowance-counter changes only after final evidence validates.

## TC03 — iptables versus XDP native

No results. Report offered/achieved/DUT RX PPS curves, native-XDP program evidence, saturation and censoring, maximum sustainable PPS, CPU, SoftIRQ, legitimate P99, and loss only after final evidence validates.

## Limitations

- TC01 route and destination host change together.
- A single account, Region, AZ, instance family, AMI, kernel, and measurement window limit external validity.
- Shared-cloud placement and transient network contention remain possible despite paired runs.
- `c6i.large` network bursting/allowance behavior may cap observed throughput or PPS.
- XDP conclusions are invalid if any run lacks verified ENA native/driver attachment evidence.

## Findings and recommendation

Pending real final data. No architecture recommendation is currently justified.

## Artifact index

Pending `results/final_summary.json`, experiment-scoped raw run tree, checksum manifests, controller/preflight evidence, and four PNG graphs.
