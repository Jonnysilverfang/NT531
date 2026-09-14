# Preregistered Mode B Experimental Protocol

> Version 2, Region `us-east-1`, AZ `us-east-1a`. Status: implementation validated; AWS execution pending. No numeric outcome is preregistered or implied.

## Research questions and estimands

### TC01 — routing path

- Comparison: VPC Peering (`10.2.1.10`) versus Transit Gateway (`10.2.2.10`).
- Tools: `sockperf ping-pong --tcp --full-rtt` and Linux `ping`.
- Metrics: per-run RTT P50/P95/P99, ping jitter/mdev, and packet loss.
- Primary effect: paired per-run P99 delta, TGW minus Peering, with a run-level bootstrap confidence interval.
- Limitation: two target hosts are required for deterministic symmetric route tables. Host and path change together; the result cannot identify a pure TGW causal effect.

### TC02 — MTU × streams

- Fixed path/DUT: client to server-b1 through VPC Peering.
- Factorial cells: MTU `{1500, 9001}` × parallel TCP streams `{1, 4, 8}`.
- Tools: `iperf3`, `ethtool -S`, `/proc/stat`, `/proc/softirqs`.
- Metrics: received throughput, retransmits, ENA RX/TX packets per second, DUT total CPU, and DUT SoftIRQ CPU.
- Primary effects: paired per-run MTU 9001 minus 1500 deltas within each stream count.

### TC03 — packet-processing saturation

- Fixed path/DUT: client to server-b1 through VPC Peering, MTU 1500.
- Conditions: UDP/5201 `iptables INPUT DROP` versus XDP_DROP attached in native/driver mode to ENA.
- Offered-load stages: 100k, 250k, 500k, 750k, 1M, and 1.5M target PPS.
- Concurrent legitimate-flow probe: TCP sockperf on port 5202.
- Metrics: target PPS, iperf sender-achieved PPS, DUT ENA RX PPS, total CPU, SoftIRQ CPU, legitimate-flow P50/P95/P99, and loss.

The first stage violating any registered SLO is the saturation point:

- legitimate-flow loss greater than 1%; or
- legitimate-flow P99 greater than 5 ms; or
- DUT total CPU greater than 90%.

Maximum sustainable PPS is the largest achieved stage strictly before the first violation. If the first 100k stage violates an SLO, maximum sustainable PPS is censored below 100k and recorded as null, not zero. If no stage violates an SLO, the value is right-censored above the largest measured stage.

Every XDP stage must contain positive evidence from `ethtool -i`, `ip -details link`, `bpftool net`, and `bpftool prog` including an XDP program ID/tag. `xdpgeneric` or missing evidence invalidates the run.

## Run design

- Pilot: 3 independent runs.
- Final: 10 independent runs, allowed only after explicit pilot acceptance.
- Warmup: 10 s; measurement: 30 s; cooldown: 15 s.
- TC01 condition order and all six TC02 cells are randomized within each run.
- TC03 load stages increase monotonically for safety and saturation detection; iptables/XDP order is randomized within each stage.
- Early stop is allowed only after the first registered saturation violation for that condition. The analyzer requires a complete prefix of configured load stages.

The independent statistical unit is one run. The primary inference is paired run-level bootstrap with 10,000 resamples. Observations within a run are not presented as independent replicates.

## Environment controls

- Account must equal the Terraform allowlist.
- All three instances: same resolved AL2023 AMI, `c6i.large`, `us-east-1a`, ENA.
- CPU count, kernel, AMI, driver/version, offloads, congestion control, IRQ information, tool versions, instance IDs, MACs, routes, and configuration hash are recorded.
- VPC CIDRs do not overlap: `10.1.0.0/16` and `10.2.0.0/16`.
- Dedicated TGW attachment subnets: `10.1.255.0/28` and `10.2.255.0/28`.
- Explicit TGW route table: flat connectivity only between the two experiment VPC attachments.
- No SSH. SSM is the sole control plane.

## Preflight acceptance

Preflight runs on the EC2 client and must verify:

1. caller account and client IMDS identity;
2. Region, AZ, AMI, type, state, and identity of all instances;
3. SSM Online state for all instances;
4. active symmetric Peering/TGW routes and exact server security-group ports;
5. bootstrap markers, tools, daemons, ICMP/TCP reachability;
6. DF jumbo-frame probes at MTU 9001 over both paths;
7. ENA on client/DUT and a load/unload native-XDP capability test.

Any failure stops collection.

## Artifact and analysis contract

```text
results/mode_b/<experiment_id>/
  run_001..run_N/
    manifest.json
    environment.json
    experiment.yaml
    commands/
    tc01/ tc02/ tc03/
    checksums.sha256
  summary/mode_b_summary.json
  graphs/
```

Run directories are immutable and may not be overwritten. The analyzer accepts only `data_mode=empirical_aws`, `empirical=true`, finalized manifests, complete cells, identical config snapshots, valid target identities, native-XDP evidence, and full checksum coverage.

Final execution also produces `results/final_summary.json` and the four registered PNGs. Synthetic Mode A/local traffic can never satisfy this contract.
