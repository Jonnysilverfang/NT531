# DECISION FRAMEWORK: AWS NETWORK ARCHITECTURE SELECTION

> **Purpose**: Quantitative rules for choosing network architecture based on Mode B experimental results.  
> **Status**: Template for Mode B data. Placeholders marked `[PLACEHOLDER]` require empirical measurements.

---

## 1. VPC PEERING vs TRANSIT GATEWAY (TC-01)

### Performance Boundary

| Metric | Peering | TGW | Delta |
|---|---|---|---|
| P99 RTT | [PLACEHOLDER] ms | [PLACEHOLDER] ms | +[PLACEHOLDER] ms |
| Throughput | Line-rate | Line-rate | ~0 |
| Cost (same-AZ) | $0.00/GB | $0.02/GB | - |
| Cost (cross-AZ) | $0.01/GB | $0.02/GB | - |

### Decision Rule

**Use VPC Peering when:**
- VPC count ≤ 10
- Hub-spoke or simple mesh topology
- Same-region, latency-sensitive (P99 < 1ms required)
- Traffic stays in same AZ (zero data cost)

**Use Transit Gateway when:**
- VPC count > 10 (peering O(N²) explosion)
- Multi-region transit routing needed
- Centralized firewall inspection required
- P99 latency budget > 1ms acceptable
- Cost of management > cost of TGW data transfer

**Crossover Point**: 
```text
If (VPC_count > 10) OR (spoke_to_spoke_flows > 50) OR (require_centralized_inspection):
    → TGW
Else:
    → Peering
```

### Cost Model

Peering connections: Free, but O(N²) management overhead.

TGW: $0.05/attachment/hour + $0.02/GB → Monthly for 10 VPCs, 1TB inter-VPC: ~$36 + $20 = $56.

Break-even: When operational cost of managing peering mesh > $56/month.

---

## 2. MTU 1500 vs MTU 9001 (TC-02)

### Performance Matrix

| MTU | Streams | Throughput | PPS | SoftIRQ % | Retrans |
|---|---|---|---|---|---|
| 1500 | 1 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 1500 | 4 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 1500 | 8 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 9001 | 1 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 9001 | 4 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 9001 | 8 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |

### Decision Rule

**Use MTU 9001 (Jumbo Frames) when:**
- Workload: bulk transfer, database replication, big data ETL
- Sustained throughput > 5 Gbps
- CPU budget constrained (want to reduce SoftIRQ)
- Path supports jumbo (intra-region AWS, no legacy NAT/VPN in path)

**Stay with MTU 1500 when:**
- Workload: microservices RPC, API gateway, small messages
- Path includes internet, VPN, on-prem hybrid
- Compatibility > performance
- Throughput < 2 Gbps (overhead negligible)

**Crossover Point**:
```text
If (sustained_Gbps > 5) AND (path_supports_jumbo) AND (cpu_budget_tight):
    → MTU 9001
Else:
    → MTU 1500 (safer default)
```

### Caution

Jumbo frames require consistent MTU across entire path. One 1500 MTU hop → fragmentation → performance loss.

---

## 3. DIRECT vs PRIVATELINK (TC-03)

### Performance & Cost

| Path | P99 RTT | Isolation | Cost (Data) | Cost (Endpoint) |
|---|---|---|---|---|
| Direct Peering | [PLACEHOLDER] ms | CIDR must not overlap | $0.00/GB (same-AZ) | $0 |
| PrivateLink | [PLACEHOLDER] ms | Service-level isolation, CIDR independent | $0.01/GB | $0.01/hour/AZ |

### Decision Rule

**Use PrivateLink when:**
- CIDR ranges overlap (cannot route directly)
- B2B partner integration (need service isolation)
- Multi-tenant SaaS backend exposure
- Latency budget > [PLACEHOLDER + 0.5] ms
- Compliance requires network-level isolation

**Use Direct Peering when:**
- CIDR ranges do not conflict
- Internal workloads (same organization)
- P99 latency critical (< 0.5 ms)
- Cost-sensitive (PrivateLink adds ~$7/month/AZ + $0.01/GB)

**Crossover Point**:
```text
If (cidr_overlap) OR (external_partner) OR (compliance_isolation_required):
    → PrivateLink
Else:
    → Direct Peering
```

### Cost Example

PrivateLink for 1 endpoint, 3 AZs, 100 GB/month: (3 × $0.01/h × 730h) + (100 × $0.01) = $22 + $1 = $23.

---

## 4. IPTABLES vs XDP (TC-04)

### Saturation Point

| Filter | Saturation PPS | P99 at Saturation | CPU at Saturation | Drop Rate |
|---|---|---|---|---|
| iptables | [PLACEHOLDER] | [PLACEHOLDER] ms | [PLACEHOLDER] % | [PLACEHOLDER] % |
| XDP | [PLACEHOLDER] | [PLACEHOLDER] ms | [PLACEHOLDER] % | [PLACEHOLDER] % |

### Decision Rule

**Use XDP when:**
- Offered load > [PLACEHOLDER] PPS (iptables saturation point)
- DDoS mitigation, high PPS filtering required
- Kernel 5.10+ with BPF native support
- Team has eBPF expertise
- SLO requires P99 < 5ms under attack load

**Stay with iptables when:**
- Offered load < [PLACEHOLDER] PPS (below saturation)
- Legacy kernel (< 5.0)
- Complex stateful filtering (iptables easier)
- No eBPF expertise in team

**Crossover Point**:
```text
If (offered_PPS > saturation_iptables) AND (kernel >= 5.10) AND (team_has_bpf_skill):
    → XDP
Else:
    → iptables (simpler, adequate for most workloads)
```

### Implementation Cost

iptables: Zero learning curve, widely understood.

XDP: Requires C/eBPF coding, BPF toolchain, verifier understanding. Development cost ~5-10 engineer-days for first filter.

---

## 5. DECISION TREE SUMMARY

```text
START
  │
  ├─ Need inter-VPC routing?
  │   ├─ VPC count ≤ 10 → Peering
  │   └─ VPC count > 10 → TGW
  │
  ├─ Need high throughput (> 5 Gbps)?
  │   ├─ Path supports jumbo → MTU 9001
  │   └─ Path has legacy hops → MTU 1500
  │
  ├─ CIDR overlap or external partner?
  │   ├─ Yes → PrivateLink
  │   └─ No → Direct Peering
  │
  └─ High PPS filtering (> [saturation_iptables])?
      ├─ Yes + eBPF capable → XDP
      └─ No or legacy kernel → iptables
```

---

## 6. COST OPTIMIZATION MATRIX

| Scenario | Architecture | Monthly Cost (Est.) | Performance |
|---|---|---|---|
| 5 VPCs, internal, < 1 TB | Peering + MTU 1500 + Direct | ~$10 (data only) | Optimal latency |
| 20 VPCs, internal, 5 TB | TGW + MTU 9001 + Direct | ~$140 | Centralized routing |
| B2B partner, overlapping CIDR | Peering + MTU 1500 + PrivateLink | ~$50 | Isolation, slight latency |
| DDoS mitigation, 2M PPS | Peering + MTU 9001 + XDP | ~$15 + dev cost | Survives attack |

---

## 7. LIMITATIONS

- Single region (us-east-1)
- Single instance type (c5n.large or similar)
- Single kernel family (Amazon Linux 2023, kernel 6.1)
- N = [PLACEHOLDER] runs (statistical power limited)
- No multi-region, DPDK, or production noisy-neighbor modeling

Decision rules valid only for workloads similar to benchmark conditions. Production validation required.

---

## 8. NEXT STEPS AFTER MODE B

1. Replace all `[PLACEHOLDER]` with empirical Mode B data
2. Generate graphs: P99 vs load, throughput heatmap, cost curves
3. Add real-world case studies (3-5 scenarios)
4. Validate decision rules with pilot production deployments
5. Update annually as AWS pricing/features change

ponytail: Multi-region transit, Global Accelerator, CloudFront integration deferred; add when cross-region RQ defined.
