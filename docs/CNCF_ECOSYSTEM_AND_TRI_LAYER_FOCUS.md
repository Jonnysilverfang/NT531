# TRỤ CỘT ĐỀ TÀI: BA TRỤ CỘT KIẾN TRÚC HIỆU NĂNG MẠNG & HỆ SINH THÁI CNCF

Tài liệu này định hình rõ ràng phạm vi nghiên cứu trọng tâm của đề tài, tập trung vào **Tam giác Kiến trúc Hiệu năng Mạng Đám mây (The Cloud Networking Performance Triangle)** gồm 3 trụ cột kỹ thuật phân tích then chốt: **Trụ cột 1 (Topology Vật lý & Phân vùng Mạng)**, **Trụ cột 2 (Định tuyến Mạng Ảo L3/L4)**, và **Trụ cột 3 (Datapath Tầng nhân Linux & Ingress Hook eBPF/CNCF)**.

---

## 1. TAM GIÁC KIẾN TRÚC HIỆU NĂNG MẠNG (TRI-PILLAR ARCHITECTURE)

```
                                  [ ĐỈNH CAO HỆ ĐIỀU HÀNH & CLOUD-NATIVE ]
                                   TRỤ CỘT 3: LINUX KERNEL DATAPATH & eBPF
                                   - Bypassing sk_buff & Netfilter at Ingress
                                   - eBPF / Native XDP Hook (ENA Driver)
                                   - Giảm 80.34% SoftIRQ, chịu 4.95M PPS flood
                                   - Đối chiếu nguyên lý với Cilium CNI (CNCF)
                                               /   \
                                              /     \
                                             /       \
                                            /         \
                                           /           \
                                          /             \
[ TẦNG VẬT LÝ & DATA CENTER ]            /               \            [ ĐỊNH TUYẾN MẠNG ẢO HÓA AWS ]
TRỤ CỘT 1: PHYSICAL TOPOLOGY & PLACEMENT /_________________\           TRỤ CỘT 2: ROUTING & TRANSIT PATHWAYS
- Same-AZ vs Cross-AZ (~1ms cáp quang)                                 - VPC Peering (0 hop, Line-rate, $0 data)
- Cluster Placement Group (High-bisection fabric < 100µs)              - Transit Gateway (+0.64ms hop, $0.02/GB)
                                                                       - PrivateLink (L4 Zero-Trust, Overlap CIDR)
```

### Tại sao tập trung vào 3 trụ cột này tạo nên đề tài hoàn chỉnh?
1. **Trụ cột 1 (Vật lý & Topology)**: Trả lời câu hỏi *"Khoảng cách cáp quang và cách bố trí máy chủ trong fabric trung tâm dữ liệu ảnh hưởng như thế nào đến độ trễ RTT?"*
2. **Trụ cột 2 (Định tuyến mạng ảo)**: Trả lời câu hỏi *"Lựa chọn kiến trúc mạng nào để tối ưu giữa chi phí, độ trễ và khả năng mở rộng hàng trăm VPC?"*
3. **Trụ cột 3 (Tầng nhân hệ điều hành & Cloud-Native)**: Trả lời câu hỏi *"Làm sao để phần mềm máy chủ và ngăn xếp mạng Linux không trở thành nút thắt cổ chai khi lưu lượng đạt hàng triệu gói tin mỗi giây?"*

---

## 2. MA TRẬN 4 KỊCH BẢN TẬP TRUNG VÀO 3 TRỤ CỘT

| Kịch Bản | Trụ Cột Phân Tích | Tên Kịch Bản | Phương Pháp Đo Đạc (Độc lập Đa Runs) | Phân Vị Trọng Tâm |
| :---: | :---: | :--- | :--- | :---: |
| **TC-01** | **Trụ cột 2 (Định tuyến L3)** | **Định Tuyến Microservices API**: So sánh **VPC Peering** vs **AWS Transit Gateway**. | `sockperf ping-pong`, `ping` (A/B testing ngẫu nhiên, tải 1-4KB). | **P95**, **P99**, P50 Latency (ms), Jitter. |
| **TC-02** | **Trụ cột 1 (Vật lý & Data Fabric)** | **Độ Trễ Vật Lý & Băng Thông Jumbo**: So sánh **MTU 1500** vs **MTU 9001** kết hợp **Cluster Placement Group**. | `iperf3 -P 8`, `sockperf --full-rtt` (đo thông lượng và độ trễ). | **P95**, **P99**, Throughput (Gbps), Tải CPU SoftIRQ. |
| **TC-03** | **Trụ cột 2 (Định tuyến L4)** | **Tích Hợp Đối Tác B2B Trùng Dải IP**: So sánh **AWS PrivateLink (L4)** vs **VPC Peering**. | `iperf3 -P 4`, `sockperf` (kiểm thử khả năng chịu overlap CIDR). | **P95**, **P99**, Phí xử lý dữ liệu ($/GB). |
| **TC-04** | **Trụ cột 3 (Nhân Linux & Datapath)** | **Đột Phá Tầng Nhân eBPF/XDP & Đối Chiếu CNCF**: So sánh **Linux iptables** vs **eBPF Native Hook**. | `iperf3 -u -b 5G` tới DUT, `mpstat -P ALL 1`, `bpftool` (stress-test). | **P99 Gói Hợp Lệ**, Tải CPU SoftIRQ (%), Max PPS. |

---

## 3. HỆ SINH THÁI GIÁM SÁT TRỰC QUAN CHUẨN CNCF (PROMETHEUS + GRAFANA)

Thay vì chỉ xem log text, đề tài tích hợp sẵn bộ đôi công cụ giám sát số 1 của **CNCF (Cloud Native Computing Foundation)** để trực quan hóa toàn bộ số liệu:

```
[ Máy Chủ EC2 / Benchmarks ] 
        |
        v (Thu thập metrics P50/P95/P99, PPS, SoftIRQ)
[ Prometheus Server (Port 9090) ]
        |
        v (Truy vấn PromQL thời gian thực)
[ Grafana Dashboard (Port 3000) ]
```

### 3.1. Khởi Chạy Ngay Bộ Giám Sát Cục Bộ (Chi phí $0.00)
Tại thư mục gốc dự án:
```bash
cd monitoring/
docker compose up -d
```

### 3.2. Truy Cập Dashboard Trực Quan
- Mở trình duyệt truy cập: `http://localhost:3000`
- Đăng nhập: Tài khoản `admin` / Mật khẩu `admin`.
- Dashboard mẫu [**`network_performance_p95_p99.json`**](file:///e:/repo/lab-aws/network-performance-capstone/monitoring/grafana/dashboards/network_performance_p95_p99.json) đã được nạp tự động, hiển thị 3 hàng chuyên dụng (3 Rows) tương ứng đúng với 3 trụ cột kỹ thuật:
  - **Hàng 1**: Biểu đồ thời gian thực phân vị **P50, P95, P99** của Peering, Transit Gateway và PrivateLink (Trụ cột 2).
  - **Hàng 2**: Biểu đồ đo đạc vi mô độ trễ vật lý và phân vùng băng thông cao của Cluster Placement Group (Trụ cột 1).
  - **Hàng 3**: Biểu đồ đo đạc tỷ lệ CPU SoftIRQ % và năng lực xử lý PPS của eBPF/XDP Kernel-Bypass (Trụ cột 3).

---

## 4. VAI TRÒ CỦA CILIUM CNI (CNCF GRADUATED PROJECT) TRONG ĐỀ TÀI

**Cilium** là dự án tốt nghiệp hàng đầu của CNCF, sử dụng eBPF để thay thế hoàn toàn `iptables` và `kube-proxy` trong môi trường Kubernetes (AWS EKS):
1. **Liên kết học thuật**: Chương trình mã nguồn C [**`xdp_packet_filter.c`**](file:///e:/repo/lab-aws/network-performance-capstone/ebpf/xdp_packet_filter.c) trong đồ án này chứng minh nguyên lý vận hành cấp thấp (low-level mechanics) của việc đánh giá và loại bỏ gói tin ngay tại tầng driver ENA trước khi cấp phát `sk_buff`.
2. **Khuyến nghị kiến trúc & Đối chiếu thực tế**: 
   - Chương trình XDP độc lập trong đề tài xác lập **cận trên lý thuyết (upper-bound benchmark)** của hiệu năng lọc gói tại tầng nhân.
   - Trong môi trường thực tế của Cilium CNI trên AWS EKS, Cilium bổ sung thêm các thành phần định tuyến Pod-to-Pod, eBGP/Geneve tunneling, Sockops BPF (tăng tốc giao tiếp socket giữa các container cùng node), và kiểm soát Network Policy. Mặc dù có thêm phụ tải của container orchestrator, Cilium vẫn bảo toàn ưu thế vượt trội về việc giảm ngắt CPU và hạn chế độ trễ đuôi P99 so với kiến trúc iptables truyền thống của kube-proxy.
