# CẤU TRÚC THƯ MỤC & MỤC LỤC ĐỀ TÀI CHUYÊN NGÀNH

Dưới đây là cấu trúc chi tiết toàn bộ tài liệu, mã nguồn và kịch bản của methodology prototype đánh giá hiệu năng mạng trên AWS:

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

## BẢNG TRA CỨU NHANH TÀI LIỆU & MỤC ĐÍCH SỬ DỤNG

| Biểu tượng & Tên File | Mục đích sử dụng chính | Đối tượng phù hợp |
| :--- | :--- | :--- |
| [📄 **README.md**](README.md) | Tổng quan đề tài, ý nghĩa thực tiễn, topo mạng và ma trận 4 kịch bản trọng tâm. | Mọi người đọc đầu tiên |
| [🏛️ **CNCF_ECOSYSTEM_AND_TRI_LAYER_FOCUS.md**](docs/CNCF_ECOSYSTEM_AND_TRI_LAYER_FOCUS.md) | Phân tích Tam Giác Kiến Trúc (Lớp 2, 3, 5), đối chiếu Cilium CNI và hướng dẫn bật Grafana. | Định hình chiến lược đề tài |
| [⚡ **EBPF_XDP_NITRO_DEEP_DIVE.md**](docs/EBPF_XDP_NITRO_DEEP_DIVE.md) | Nghiên cứu công nghệ Kernel-Bypass eBPF/XDP (Lớp 5), triệt tiêu SoftIRQ và conntrack limits. | Đột phá học thuật & Chuyên gia |
| [📘 **THEORY_AND_METRICS.md**](docs/THEORY_AND_METRICS.md) | Nền tảng ảo hóa phần cứng Nitro, ENA allowance registers, Jumbo Frames MTU 9001. | Nghiên cứu kiến trúc sâu |
| [📐 **MATHEMATICAL_AND_KERNEL_FOUNDATIONS.md**](docs/MATHEMATICAL_AND_KERNEL_FOUNDATIONS.md) | Giải tích toán học: BDP, công thức Mathis, TCP CUBIC vs BBR, thống kê Run-level & Bootstrap. | Luận văn & Báo cáo kỹ thuật |
| [🖥️ **AWS_CONSOLE_SYDNEY_GUIDE.md**](docs/AWS_CONSOLE_SYDNEY_GUIDE.md) | Hướng dẫn thao tác đồ họa trên AWS Console Region Sydney (`ap-southeast-2`) click-by-click. | Thực hành trực quan bằng tay |
| [📊 **PERFORMANCE_ANALYSIS_REPORT.md**](docs/PERFORMANCE_ANALYSIS_REPORT.md) | Báo cáo Chế độ A (Calibrated Synthetic Reference), số liệu P50/P95/P99, Threats to Validity. | Nghiệm thu & Bảo vệ đề tài |
| [🧾 **ACADEMIC_EVIDENCE_MATRIX.md**](docs/ACADEMIC_EVIDENCE_MATRIX.md) | Truy nguyên từng tuyên bố tới artifact, automated gate, giới hạn và bằng chứng Chế độ B còn thiếu. | Phản biện & kiểm toán độc lập |
| [✅ **FINAL_MODE_A_READINESS_AUDIT.md**](docs/FINAL_MODE_A_READINESS_AUDIT.md) | Kết luận và bảng điểm nghiệm thu có phạm vi cho Methodology Prototype. | Hội đồng bảo vệ |
| [🔍 **OBSERVABILITY_AND_TROUBLESHOOTING_RUNBOOK.md**](docs/OBSERVABILITY_AND_TROUBLESHOOTING_RUNBOOK.md) | Custom Flow Logs v5, câu lệnh Athena SQL và quy trình xử lý sự cố mạng khi bị bóp nghẽn. | Quản trị vận hành (SRE/DevOps) |
| [🎯 **AWS_EXAM_MASTERY_DEEP_DIVE.md**](docs/AWS_EXAM_MASTERY_DEEP_DIVE.md) | 10 bài toán thực tế và bẫy thi cử cốt lõi từ ANS-C01 & DOP-C02 có lời giải chi tiết. | Ôn luyện thi chứng chỉ AWS |
| [🎓 **CAPSTONE_THESIS_AND_SLIDES_TEMPLATE.md**](docs/CAPSTONE_THESIS_AND_SLIDES_TEMPLATE.md) | Khung cấu trúc Khóa luận tốt nghiệp chuẩn 5 chương, 12 slides và 7 câu hỏi phản biện. | Trình bày trước Hội đồng |
| [📁 **monitoring/**](monitoring/) | Trọn bộ Docker Compose Prometheus + Grafana Dashboard trực quan hóa P50/P95/P99. | Trực quan hóa CNCF ($0) |
| [📁 **ebpf/**](ebpf/) | Trọn bộ mã nguồn C eBPF, Makefile, script quản lý nạp driver XDP và monitor thời gian thực. | Lập trình nhân Linux & DevOps |
| [📁 **terraform/**](terraform/) | Toàn bộ mã nguồn tự động hóa hạ tầng (chỉ triển khai khi có nhu cầu). | Tự động hóa IaC |
| [📁 **scripts/**](scripts/) | Bộ script chạy đo tự động, điều khiển DUT từ xa qua SSM, phân tích thống kê và cleanup. | Tự động hóa đo kiểm |
| [📁 **tests/**](tests/) | Kiểm thử hồi quy positive/negative và quality gate hoàn toàn ngoại tuyến. | QA & tái lập |
| [📁 **results/**](results/) | Dữ liệu gốc (raw JSON/CSV), manifest phần cứng, mã băm SHA256 và tóm tắt thống kê. | Tái lập & Kiểm thử khoa học |
