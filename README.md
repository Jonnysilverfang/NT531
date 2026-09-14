# ĐÁNH GIÁ THỰC NGHIỆM KIẾN TRÚC MẠNG AWS VÀ XỬ LÝ GÓI TIN LINUX

> **English Title:** Calibrated Reference Benchmark & Architecture Prototype: High-Throughput Cloud Networking and Linux Kernel-Bypass using eBPF/XDP on AWS Nitro ENA Architecture (Methodology Prototype – Not Yet an Empirical AWS Measurement)  
> **Region Triển Khai:** AWS Sydney (`ap-southeast-2`)  
> **Chế độ dữ liệu:** Calibrated Synthetic Reference Benchmark Model (Chế độ A - Kiểm chứng pipeline tự động hóa và toán thống kê, chi phí $0.00).  
> **Tác giả:** Đội ngũ Kỹ sư Mạng & Cloud DevOps

---

> [!IMPORTANT]
> **THÔNG CÁO MINH BẠCH HỌC THUẬT & KIỂM CHỨNG TÁI LẬP (DATA PROVENANCE & REPRODUCIBILITY):**  
> - **Chế độ A (Calibrated Synthetic Reference Model)**: Nhằm phục vụ thẩm định học thuật với chi phí $0.00, toàn bộ số liệu đối chứng là dữ liệu tổng hợp có tham số tham chiếu từ kiến trúc AWS Nitro/ENA và mô hình Sydney (`ap-southeast-2`). Việc “calibrated” không chứng minh số liệu đại diện cho phân phối thực tế của AWS; báo cáo không tuyên bố đây là phép đo production.
> - **Giảm Pseudoreplication**: Đơn vị phân tích độc lập là **Independent Run ($N = 3$)**. Hiệu ứng chính của cả TC-01 đến TC-04 được tính bằng chênh lệch ghép cặp từng run kết hợp **Hierarchical Bootstrap (10,000 resamples)** hai tầng (lấy mẫu lại run, sau đó observation). Các kiểm định Welch gộp chỉ mang tính thăm dò (exploratory only); $N=3$ vẫn là giới hạn về lực thống kê và khả năng khái quát.
> - **Kiểm tra toàn vẹn tự động**: Pipeline [`analyze_results.py`](scripts/analyze_results.py) đối chiếu trực tiếp mã băm SHA256 của 5/5 tệp thô trong [`results/raw/`](results/raw/) với [`checksums.sha256`](results/raw/checksums.sha256).
> - **Quality Gate ngoại tuyến**: `python scripts/run_quality_gate.py` chạy positive/negative tests cho checksum, SoftIRQ delta, numeric underflow, hierarchical bootstrap, exporter schema và các contract SSM/XDP; quality gate không gọi AWS, không deploy và không nạp XDP.
> - **Ma trận bằng chứng**: [`docs/ACADEMIC_EVIDENCE_MATRIX.md`](docs/ACADEMIC_EVIDENCE_MATRIX.md) ánh xạ từng tuyên bố tới mã nguồn, automated gate, giới hạn và bằng chứng Chế độ B còn cần thiết.
> - **Nghiệm thu chung cuộc Mode A**: [`docs/FINAL_MODE_A_READINESS_AUDIT.md`](docs/FINAL_MODE_A_READINESS_AUDIT.md) chấm 9,62/10 cho methodology prototype, không phải chứng nhận benchmark AWS empirical.
> - **Giao thức Mode B đã đăng ký trước**: [`docs/MODE_B_EXPERIMENTAL_PROTOCOL.md`](docs/MODE_B_EXPERIMENTAL_PROTOCOL.md) khóa 4 RQ, ma trận đo, saturation rule, randomization, metadata và fail-closed preflight. Chưa có run AWS nào được xác nhận trong repo.

---

## 1. Đặt Vấn Đề & Ý Nghĩa Thực Tiễn

Khi thiết kế hạ tầng mạng đám mây cho các hệ thống quy mô lớn (Enterprise Multi-Account & Multi-VPC Architecture), các kỹ sư mạng và kiến trúc sư giải pháp thường đứng trước những quyết định đánh đổi (**Architectural Trade-offs**) phức tạp giữa **Hiệu năng (Throughput / Latency / PPS)**, **Bảo mật (Security & Isolation)**, và **Chi phí (Cost Efficiency)**.

Ba mô hình kết nối liên VPC cốt lõi trên AWS hiện nay:
1. **VPC Peering**:
   - *Ưu điểm*: Kết nối trực tiếp qua mạng trục AWS (Line-rate backbone), không bị thắt cổ chai băng thông, không phát sinh chi phí dữ liệu trong cùng một Availability Zone ($0.00/GB), độ trễ thấp nhất.
   - *Nhược điểm*: Không hỗ trợ định tuyến bắc cầu (Non-transitive routing), tạo mô hình Full-mesh phức tạp khi số lượng VPC tăng lên ($N \times (N-1) / 2$), khó kiểm soát tập trung, không hỗ trợ dải IP trùng lặp (Overlapping CIDR).
2. **AWS Transit Gateway (TGW)**:
   - *Ưu điểm*: Kiến trúc Hub-and-Spoke tập trung, dễ quản lý định tuyến cho hàng trăm/nghìn VPC và mạng On-premises, hỗ trợ Multicast, SD-WAN Connect (GRE), hỗ trợ cô lập mạng qua nhiều Route Table.
   - *Nhược điểm*: Thêm một chặng trung chuyển mạng (Network Hop) làm tăng độ trễ (~0.5ms - 1ms), chi phí cao (tính phí $0.07/giờ mỗi attachment + $0.02/GB dữ liệu xử lý tại Sydney), băng thông cơ sở 50 Gbps mỗi VPC attachment trên mỗi AZ.
3. **AWS PrivateLink (VPC Endpoint Service)**:
   - *Ưu điểm*: Bảo mật cao nhất (Zero-Trust), kết nối một chiều (Unidirectional), giải quyết triệt để vấn đề trùng lặp CIDR, ẩn giấu hoàn toàn cấu trúc mạng nội bộ, quản lý truy cập theo IAM Principal.
   - *Nhược điểm*: Chỉ hỗ trợ giao thức tầng 4 TCP/TLS (thông qua Network Load Balancer), phát sinh độ trễ xử lý qua proxy/NLB, tính phí theo giờ và phí dữ liệu $0.01/GB.

Bên cạnh đó, các cơ chế tối ưu hóa cấp thấp của phần cứng ảo hóa **AWS Nitro System**:
- **Enhanced Networking Adapter (ENA)**: Cung cấp enhanced networking và các hàng đợi đa luồng; giới hạn thực tế phụ thuộc instance type, kích thước gói và allowance của ENA.
- **Jumbo Frames (MTU 9001 vs MTU 1500)**: Có thể giảm số packet cần xử lý cho cùng lượng payload. Mức giảm SoftIRQ/PPS là giả thuyết cần đo ở Mode B, không phải thuộc tính cố định của AWS.
- **Cluster Placement Groups**: Có thể giảm biến thiên placement cho workload cần thông lượng cao/độ trễ thấp trong một Availability Zone; repo chưa có phép đo AWS để định lượng mức cải thiện.

---

## 2. Mục Tiêu Cụ Thể của Đề Tài

1. **Về mặt kỹ thuật**:
   - Xây dựng hoàn chỉnh hạ tầng kiểm thử đa VPC trên AWS gồm: VPC A (Client), VPC B (Target Server B1 và B2), VPC Shared Services (PrivateLink Provider) tại Sydney (`ap-southeast-2`).
   - Cấu hình song song 3 đường truyền: **VPC Peering**, **AWS Transit Gateway**, và **AWS PrivateLink**.
   - Cài đặt và cấu hình bộ công cụ đo kiểm hiệu năng mạng chuyên sâu: `iperf3` (Throughput/Jitter/Loss), `sockperf` (Sub-millisecond RTT Latency Distribution P50/P95/P99), `ethtool` (ENA Nitro hardware drops).
2. **Về mặt nguyên mẫu đo kiểm**:
   - Thực hiện 4 kịch bản kiểm thử; phiên pilot gồm **$N = 3$ independent runs** đối chứng, protocol mở rộng hoàn chỉnh dự kiến 10–30 randomized runs.
   - Trích xuất dữ liệu thô, phân tích biểu đồ phân vị độ trễ (Latency CDF), và đánh giá tải CPU ngắt mềm SoftIRQ.
   - Đánh giá ngưỡng bão hòa của eBPF/XDP Native Hook so với Linux iptables tại Ingress DUT theo các mức offered load đã đăng ký trong `experiment.yaml`; phải báo cả target PPS và achieved PPS.
3. **Về mặt ứng dụng & Kinh tế**:
   - Đánh giá tương quan Chi phí / Hiệu năng (Cost-to-Performance Ratio: Gbps per Dollar).
   - Đưa ra bản hướng dẫn kỹ thuật kiến trúc mạng (Design Decision Framework) áp dụng cho doanh nghiệp và các bài toán thi tuyển chứng chỉ cao cấp AWS ANS-C01 & DOP-C02.

---

## 3. Kiến Trúc Mạng Thực Nghiệm (Architecture Diagram)

```
====================================================================================================
AWS Region: Sydney (ap-southeast-2) - Giảm thiểu tối đa Confounder (Cùng AZ-a, cùng instance, no PG)
====================================================================================================

+-------------------------------------+                +-------------------------------------+
| VPC A: Client VPC (10.1.0.0/16)     |                | VPC B: Target VPC (10.2.0.0/16)     |
| Subnet A1 (ap-southeast-2a)         |                | Subnet B1 (ap-southeast-2a)         |
|   - EC2 Client 1 (c6i.large / ENA)  |                |   - EC2 Target B1 (Peering Target)  |
|     [c6i.large, no Placement Group] |                |     [c6i.large, no Placement Group] |
|     [Private IP: 10.1.1.10]         |                |     [Private IP: 10.2.1.10]         |
|                                     |                | Subnet B2 (ap-southeast-2a)         |
|                                     |                |   - EC2 Target B2 (TGW Target)      |
| Subnet A2 (ap-southeast-2b)         |                |     [c6i.large, no Placement Group] |
|   - Subnet dự phòng Cross-AZ        |                |     [Private IP: 10.2.2.10]         |
|                                     |                |                                     |
+-------------------------------------+                +-------------------------------------+
        |                 |                                      |                 |
        |                 |====== [ĐƯỜNG 1: VPC PEERING] =======|                 |
        |                 |       - Direct Line-rate             |                 |
        |                 |       - Mode B latency: pending      |                 |
        |                 |       - Cost snapshot: pending       |                 |
        |                 |                                      |                 |
        |                 \------- [ĐƯỜNG 2: TRANSIT GATEWAY] --/                 |
        |                          - Hub-and-Spoke Centralized                     |
        |                          - TGW Route Tables                              |
        |                          - Mode B latency/cost: pending                  |
        |                                                                          |
        v                                                                          |
  +-----------------------------------------------------------------------------+  |
  | Interface VPC Endpoint (AWS PrivateLink) [10.1.1.50]                         |  |
  +-----------------------------------------------------------------------------+  |
        |                                                                          |
        v [ĐƯỜNG 3: AWS PRIVATELINK (AWS Backbone Layer 4)]                       |
  +-----------------------------------------------------------------------------+  |
  | VPC Shared: Service Provider VPC (10.3.0.0/16)                              |  |
  |   - Internal Network Load Balancer (NLB)                                    |  |
  |   - VPC Endpoint Service (PrivateLink)                                      |  |
  |   - EC2 Backend Service (iperf3 server trên port 5201)                      |  |
  |   - SSM Interface Endpoints (ssm, ssmmessages, ec2messages)                 |  |
  +-----------------------------------------------------------------------------+--+
```

---

## 4. Ma Trận Kịch Bản Thực Nghiệm & Phương Pháp Đa Phiên (3 Pilot Runs)

Bộ tham chiếu tổng hợp Mode A gồm **$N = 3$ Independent Runs**, áp dụng **Run-level Paired Deltas** và **Hierarchical Bootstrap hai tầng (10,000 resamples)** trên observations được sinh có kiểm soát. Analyzer Mode B dùng **paired run-level bootstrap** trên các summary của từng run; repo không tuyên bố hierarchical bootstrap cho Mode B khi chưa thu raw observations bên trong run.

| Mã Kịch Bản | Trụ Cột Đề Tài | Bài Toán Kỹ Thuật Nghiệp Vụ | Kiến Trúc So Sánh | Công Cụ Đo | Chỉ Số Trọng Tâm (Single Source of Truth) |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **TC-01** | **Lớp 3 (Định tuyến)** | **Giao tiếp Microservices & Backend API** (gRPC/HTTP/2, gói 1-4KB). | **VPC Peering** vs **AWS Transit Gateway** | `sockperf`, `ping` | **P99 Delta: +0.773 ms** ($CI_{95\%}$: [0.757, 0.792] ms)<br>Welch exploratory: $t = -477.15, p < 1 \times 10^{-300}$. |
| **TC-02A** | **Lớp 2 (Vật lý)** | **Thiết kế Vị trí Vật lý & Gom Rack ToR Switch** (*Architecture Planned*). | **Same-AZ** vs **Cross-AZ** vs **Cluster Placement Group** | `sockperf` | Phân tích lý thuyết BDP & Fabric switch ToR (< 100 µs). |
| **TC-02B** | **Lớp 2 (Vật lý)** | **Đồng bộ Cơ sở Dữ liệu & Big Data ETL** (*Mode A Reference Benchmark*). | **MTU 1500 (Standard)** vs **MTU 9001 (Jumbo Frames)** | `iperf3 -P 4` | **Giảm 46.30 điểm % CPU SoftIRQ** (CI run-aware: [-46.67, -45.93])<br>Throughput tăng 1.637 Gbps (CI: [1.609, 1.669]). |
| **TC-03** | **Lớp 3 (Định tuyến)** | **Tích hợp Đối tác B2B Trùng Dải IP (Zero-Trust SaaS Integration)**. | **AWS PrivateLink** vs **VPC Peering** | `sockperf`, `iperf3` | **P99 = 0.604 ms**; $\Delta$P99 run-aware: +0.395 ms (CI: [0.386, 0.405])<br>Giải quyết xung đột CIDR trong mô hình Chế độ A. |
| **TC-04** | **Lớp 5 (Nhân & CNCF)** | **Chống Bão Hòa UDP Flood & eBPF Kernel-Bypass tại Ingress DUT**. | **Linux iptables** vs **eBPF/XDP Native Hook** | `iperf3 -u`, `bpftool` | **Giảm 80.34 điểm % CPU SoftIRQ** (CI run-aware: [-80.66, -79.98])<br>Drop-rate tăng 3.805M PPS; interval-P99 giảm 14.156 ms. |

> Các số trong bảng là **Mode A synthetic reference**, không phải AWS observation. Riêng TC-01 hiện đổi đồng thời path và backend host; vì vậy claim hợp lệ chỉ là “cấu hình đường đi TGW quan sát được có latency cao hơn trong môi trường này”, không phải “TGW gây thêm latency”. Mode B lưu target identity cho từng run và fail-closed nếu metadata bị thiếu.

---

## 5. Cấu Trúc Thư Mục Dự Án

```
NT531/
├── 📄 README.md                                   <-- Đề cương tổng quan, ma trận kiểm thử 4 kịch bản
├── 📄 STRUCTURE.md                                <-- Bảng mục lục tra cứu nhanh & sơ đồ dự án
├── 📁 docs/
│   ├── 🏛️ CNCF_ECOSYSTEM_AND_TRI_LAYER_FOCUS.md   <-- Tam Giác Kiến Trúc (Lớp 2, 3, 5) & Chuẩn CNCF
│   ├── ⚡ EBPF_XDP_NITRO_DEEP_DIVE.md            <-- Tối ưu hóa Kernel-Bypass eBPF/XDP trên AWS ENA
│   ├── 📘 THEORY_AND_METRICS.md                  <-- Lý thuyết Nitro ENA, SR-IOV, MTU 9001, Placement Groups
│   ├── 📐 MATHEMATICAL_AND_KERNEL_FOUNDATIONS.md <-- Mô hình BDP, Mathis, TCP CUBIC/BBR & Thống kê Run-level
│   ├── 🖥️ AWS_CONSOLE_SYDNEY_GUIDE.md            <-- Hướng dẫn click-by-click Console Sydney (ap-southeast-2)
│   ├── 📊 PERFORMANCE_ANALYSIS_REPORT.md         <-- Báo cáo mô hình tham chiếu Chế độ A & Threats to Validity
│   ├── 🧾 ACADEMIC_EVIDENCE_MATRIX.md            <-- Ma trận claim → evidence → automated gate → giới hạn
│   ├── ✅ FINAL_MODE_A_READINESS_AUDIT.md         <-- Nghiệm thu >9,5 có giới hạn rõ ràng cho Mode A
│   ├── 🔍 OBSERVABILITY_AND_TROUBLESHOOTING_RUNBOOK.md <-- Flow Logs v5, Athena SQL & Xử lý nghẽn phần cứng
│   ├── 🎯 AWS_EXAM_MASTERY_DEEP_DIVE.md          <-- 10 bài toán thực tế & Bẫy thi ANS-C01 & DOP-C02
│   └── 🎓 CAPSTONE_THESIS_AND_SLIDES_TEMPLATE.md <-- Khung luận văn chuẩn, 12 slides & 7 câu hỏi phản biện
├── 📁 monitoring/                                 <-- Hệ thống giám sát trực quan Prometheus + Grafana ($0.00)
│   ├── docker-compose.yml                        <-- Khởi chạy Prometheus + Grafana cục bộ
│   ├── mock_metrics_exporter.py                  <-- Exporter đọc summary_statistics.json (data_source="synthetic_calibrated_reference")
│   ├── prometheus/prometheus.yml                 <-- Cấu hình thu thập metrics 1-2s
│   └── grafana/                                  <-- Dashboard tự động vẽ biểu đồ P50/P95/P99, eBPF vs iptables
├── 📁 ebpf/                                       <-- Mã nguồn C eBPF, Makefile & Monitor Python
│   ├── xdp_packet_filter.c                       <-- Chương trình C eBPF Native Hook (BTF map, Direct Packet Access)
│   ├── Makefile                                  <-- Script biên dịch Clang/LLVM BPF bytecode
│   ├── ebpf_loader.sh                            <-- Quản lý nạp (load)/gỡ (unload) XDP vào ENA
│   └── ebpf_monitor.py                           <-- Giám sát PPS & Throughput thời gian thực từ BPF Map
├── 📁 terraform/                                  <-- Mã nguồn IaC (VPC, Peering, TGW, PrivateLink, EC2, SSM, Placement)
│   └── main.tf, variables.tf, outputs.tf, terraform.tfvars.example (SẴN SÀNG, CHƯA DEPLOY)
├── 📁 scripts/                                    <-- Bộ kịch bản đo đạc tự động, phân tích thống kê & dọn dẹp
│   ├── benchmark_runner.sh                       <-- Runner 4 TC, remote SSM run_on_dut, synchronized SoftIRQ
│   ├── dut_server_setup.sh                       <-- Quản lý DUT Receiver, daemons & toggling iptables/XDP
│   ├── calculate_softirq_delta.py                <-- Tính toán SoftIRQ delta chuẩn xác giữa 2 snapshot Before/After
│   ├── analyze_results.py                        <-- Pipeline SHA256 verify, run-level paired analysis, 10k bootstrap
│   ├── generate_reference_dataset.py             <-- Recipe deterministic tạo lại 100% raw Chế độ A
│   ├── run_quality_gate.py                       <-- Quality gate ngoại tuyến một lệnh, không gọi AWS/XDP
│   ├── collect_ena_metrics.sh                    <-- Thu thập thanh ghi ethtool phần cứng ENA
│   └── cleanup_resources.sh                      <-- Dọn dẹp tài nguyên 1-click
├── 📁 tests/
│   └── test_quality.py                           <-- Positive/negative regression tests cho provenance và thống kê
└── 📁 results/                                    <-- Kho dữ liệu gốc và bằng chứng tái lập
    ├── raw/                                      <-- Dữ liệu đo đạc chi tiết cấp độ quan sát (observation-level)
    │   ├── environment_manifest.json             <-- Thông số chi tiết AMI, kernel 6.1, driver ENA, SHA256
    │   ├── tc01_peering_tgw_samples.csv          <-- 6,000 observations RTT packet-level Peering vs TGW
    │   ├── tc02_jumbo_frames_samples.json        <-- Chuỗi quan sát Throughput, SoftIRQ & PPS MTU 1500 vs 9001
    │   ├── tc03_privatelink_samples.json         <-- 3,000 RTT observations (hai điều kiện) & throughput fields
    │   ├── tc04_xdp_iptables_samples.json        <-- 180 intervals (hai điều kiện) SoftIRQ, PPS & probe latency
    │   └── checksums.sha256                      <-- Bảng mã băm SHA256 bảo đảm tính toàn vẹn dữ liệu
    └── summary_statistics.json                   <-- Kết quả tính toán thống kê (Mean, CI, Welch p-value, Cohen's d)
```

---

## 6. Lệnh Tái Lập Thống Kê Duy Nhất (1-Command Reproduction)

Để tái lập 100% kết quả phân tích thống kê và xác thực toàn vẹn mã băm SHA256:

```bash
python3 scripts/analyze_results.py \
  --input-dir results/raw \
  --output-json results/summary_statistics.json \
  --bootstrap-resamples 10000 \
  --random-seed 42
```

Mode B dùng analyzer và schema riêng sau khi đã có run AWS được niêm phong checksum:

```bash
python3 scripts/analyze_mode_b.py \
  --experiment-dir results/mode_b/<experiment_id> \
  --output-json results/mode_b/<experiment_id>/mode_b_summary.json \
  --bootstrap-resamples 10000 \
  --random-seed 42
```

Analyzer từ chối dataset thiếu run/cell, checksum sai, TC-03 không cùng backend hoặc TC-04 thiếu chuỗi load hợp lệ. Chưa có `mode_b_summary.json` từ AWS thật trong repo.
