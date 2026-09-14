# BƯỚC ĐỘT PHÁ CÔNG NGHỆ: TỐI ƯU HÓA HIỆU NĂNG MẠNG TẦNG NHÂN BẰNG eBPF/XDP TRÊN AWS NITRO ENA

Tài liệu này trình bày giải pháp công nghệ mũi nhọn của đề tài: Ứng dụng **eBPF (Extended Berkeley Packet Filter)** và **XDP (eXpress Data Path)** để thực hiện kỹ thuật **bypassing generic kernel networking stack (Netfilter/conntrack/sk_buff)** trực tiếp tại tầng driver của card mạng **AWS Elastic Network Adapter (ENA)**. Đây là kỹ thuật xử lý gói tin ở tầng thấp nhất có thể trong nhân Linux, giúp giải phóng năng lực xử lý của máy chủ EC2, triệt tiêu độ trễ hàng đợi CPU SoftIRQ và ngăn ngừa hiện tượng nghẽn hàng đợi card mạng.

---

## 1. Vấn Đề Cốt Lõi: Nút Thắt Cổ Chai Của Network Stack Truyền Thống Trong Linux

Trong các hệ thống Cloud truyền thống chạy trên Linux (kể cả Amazon Linux 2023 hay Ubuntu Server), luồng xử lý một gói tin Inbound từ môi trường ảo hóa AWS diễn ra qua các bước phức tạp:

```
[ Gói tin từ AWS Nitro Card ]
              |
              v (PCIe DMA Transfer)
[ ENA Ring Buffer (RX Descriptors) ]
              |
              v (Kích hoạt Hardware Interrupt)
[ Nhân Linux CPU xử lý Top-Half Handler ]
              |
              v (Lên lịch ksoftirqd xử lý SoftIRQ)
+-------------------------------------------------------------------------------+
|                        VÙNG NGHẼN CPU: LINUX NETWORK STACK                    |
|  1. Cấp phát cấu trúc dữ liệu socket buffer khổng lồ: alloc_skb()             |
|  2. Sao chép và khởi tạo metadata gói tin (sk_buff tiêu tốn ~256-512 bytes)   |
|  3. Chuyển qua tầng Netfilter:                                                |
|     - Duyệt tuần tự qua các chuỗi iptables / nftables                         |
|     - Ghi nhận trạng thái phiên vào bảng conntrack (tiêu tốn bộ nhớ & lock)   |
|  4. Định tuyến IP (IP Routing Lookup & FIB Table)                             |
|  5. Xử lý TCP/UDP Protocol Stack & Checksum Verification                      |
|  6. Xếp hàng vào Socket Queue (sk_receive_queue)                              |
+-------------------------------------------------------------------------------+
              |
              v (Context Switch từ Kernel Space sang User Space)
[ Ứng dụng User Space đọc qua socket API (sys_recvfrom / epoll) ]
```

### Hậu quả nghiêm trọng ở tốc độ mạng 10 Gbps – 25 Gbps:
1. **Nghẽn tải CPU do ngắt mềm (SoftIRQ Starvation)**:
   - Khi tốc độ gói tin tăng lên vài triệu gói tin/giây (như trong các đợt lưu lượng microservices đột biến hoặc bị tấn công DDoS), tiến trình `ksoftirqd` chiếm tới **70% - 90% CPU** của toàn bộ các vCPU chỉ để làm một việc: cấp phát và giải phóng bộ đệm `sk_buff`.
2. **Độ trễ đuôi (Tail Latency P99/P99.9) tăng vọt**:
   - Hiện tượng tranh chấp tài nguyên hàng đợi (Queue Lock Contention) trong nhân khiến thời gian xử lý một gói tin biến thiên mạnh, gây jitter lớn.
3. **Chạm trần giới hạn phần cứng AWS Nitro**:
   - Cơ chế Stateful Tracking của Security Group và `iptables conntrack` nhanh chóng làm cạn kiệt bảng theo dõi trạng thái, dẫn đến lỗi drop gói `conntrack_allowance_exceeded` hoặc nghẽn PPS.

---

## 2. Giải Pháp Đột Phá: Kiến Trúc XDP (eXpress Data Path) Trên AWS ENA

**XDP** là một hệ thống mạng hiệu năng cực cao được tích hợp sẵn trong Linux Kernel từ phiên bản 4.8+. Điểm khác biệt mang tính cách mạng của XDP: **Nó cho phép thực thi một chương trình eBPF bytecode an toàn ngay bên trong driver card mạng ENA (Driver Hook Level), trước khi nhân Linux kịp cấp phát bất kỳ cấu trúc `sk_buff` nào và trước khi Netfilter/iptables nhìn thấy gói tin!**

> [!NOTE]
> **Làm rõ ranh giới kỹ thuật & Cơ chế thực thi:**
> - **Không phải DPDK Userspace Bypass**: XDP chạy trong kernel context (không bypass toàn bộ kernel), nhưng nó **bypass toàn bộ ngăn xếp mạng tổng quát (generic network stack)** của Linux ở chiều Ingress.
> - **Thực thi trên Host CPU, không phải trên Nitro ASIC**: Trong môi trường ảo hóa EC2, chương trình XDP được biên dịch JIT và thực thi trực tiếp bởi CPU máy chủ tại hàm ngắt RX của driver ENA (`ena_clean_rx_irq`). AWS Nitro Card không hỗ trợ chế độ hardware-offload cho mã người dùng.

```
+-------------------------------------------------------------------------------+
|                       AWS NITRO CARD FOR NETWORKING                           |
+-------------------------------------------------------------------------------+
                                      |  DMA Transfer gói tin thô (Raw Frame)
                                      v
+-------------------------------------------------------------------------------+
|                  AWS ENA LINUX DRIVER (ena_netdev.c)                         |
|                                                                               |
|    +---------------------------------------------------------------------+    |
|    |           XDP HOOK POINT: xdp_network_optimizer()                   |    |
|    |    (Thực thi eBPF JIT-compiled Bytecode trực tiếp tại RX Buffer)    |    |
|    +---------------------------------------------------------------------+    |
|            |                      |                      |                    |
|       [XDP_DROP]             [XDP_PASS]             [XDP_TX]                  |
|            |                      |                      |                    |
|      Hủy gói tin tức        Chuyển tiếp lên        Dội ngược gói ra          |
|      thời tại NIC ring.     Linux Network          lưới mạng AWS ngay         |
|      Tải CPU cực thấp!      Stack tiêu chuẩn       tại card mạng             |
|      (Chặn packet flood)    (Cho traffic xịn)      (Router / Reflector)      |
+-------------------------------------------------------------------------------+
                                    |
                                    v (Chỉ khi cần thiết)
                      [ LINUX NETWORK STACK (sk_buff) ]
```

### Ba Chế Độ Thực Thi Của XDP:
1. **Offloaded Mode (XDP-Offload)**: Bytecode eBPF được nạp và chạy trực tiếp trên chip xử lý của SmartNIC (yêu cầu SmartNIC phần cứng chuyên dụng có SoC nhúng, không hỗ trợ trên EC2 tiêu chuẩn).
2. **Native Mode (XDP-Driver - Được sử dụng trong đề tài)**:
   - Bytecode eBPF được chạy trực tiếp bên trong hàm xử lý ngắt nhận gói của ENA driver (`ena_clean_rx_irq`).
   - Đây là chế độ đạt hiệu năng tối đa trên mọi instance ảo hóa AWS Nitro (`c6i`, `c5`, `m6i`,...) khi MTU $\le 1500$ bytes (single-buffer mode).
3. **Generic Mode (XDP-Generic)**: Chạy sau khi `sk_buff` đã được cấp phát (dùng cho mục đích kiểm thử trên card mạng không có native XDP driver).

---

## 3. Khắc Phục Triệt Để Hai Giới Hạn Cốt Lõi Của AWS Nitro

### 3.1. Triệt Tiêu Nguy Cơ Nghẽn `pps_allowance_exceeded`
- Trên máy chủ `c6i.large`, ngưỡng trần PPS bị giới hạn bởi năng lực xử lý ngắt của CPU và driver ENA.
- Bằng cách kích hoạt **XDP trong ENA Driver**, gói tin bị drop ngay tại RX Ring trước khi cấp phát `sk_buff` và duyệt Netfilter, giảm thời gian xử lý gói tin từ hàng trăm chu kỳ CPU xuống chỉ còn vài chục chỉ lệnh JIT tối giản.
- Mô hình Chế độ A đặt drop-rate tham chiếu khoảng 1.15M PPS cho iptables và 4.95M PPS cho XDP để thử pipeline. Đây không phải phép đo trên `c6i.large`; Mode B phải kiểm tra offered load, ENA counters, queue drops và native attachment trước khi quy nguyên nhân.

### 3.2. Quản Trị Phiên Động Bằng BPF Stateful Maps
- Để mở rộng từ bộ lọc phi trạng thái (Stateless filter trong `xdp_packet_filter.c`) sang theo dõi phiên trạng thái cao cấp:
- Kiến trúc cho phép sử dụng **BPF LRU Hash Map (`BPF_MAP_TYPE_LRU_HASH`)** nằm trong bộ nhớ RAM máy chủ. Bản đồ này có thể theo dõi hàng triệu kết nối đồng thời với thuật toán tra cứu $O(1)$ lock-less, giảm phụ thuộc vào bảng `nf_conntrack` cồng kềnh của nhân Linux.

---

## 4. Dữ Liệu Đo Đạc Đối Chứng (Calibrated Reference Summary)

Dưới đây là bảng kết quả đối chứng Chế độ A trích xuất từ [`results/summary_statistics.json`](../results/summary_statistics.json); đây không phải phép đo UDP flood đã chạy trên AWS:

| Chỉ số Hiệu năng Đo Đạc | Tường Lửa Linux iptables (`-j DROP`) | Giải Pháp eBPF / XDP Native (`XDP_DROP`) | Mức Độ Cải Thiện & Ý Nghĩa Thống Kê |
| :--- | :---: | :---: | :---: |
| **Tốc độ loại bỏ gói quan sát (Dropped PPS)** | **1,149,004 PPS** | **4,950,056 PPS** | **Tăng 4.3 lần (Loại bỏ 99% bão UDP 5 Mpps)** |
| **Mức CPU SoftIRQ Chế độ A** | **84.57%** | **4.23%** | **$\Delta=-80.34$ điểm % (CI run-aware [-80.66, -79.98])** |
| **Độ trễ P50 gói TCP Probe hợp lệ (port 5202)**| **1.850 ms** | **0.190 ms** | **P50 nhanh hơn 9.7 lần** |
| **Interval-P99 TCP Probe Chế độ A (port 5202)**| **14.505 ms** | **0.347 ms** | **$\Delta=-14.156$ ms (CI [-14.478, -13.820])** |
| **Chỉ số ENA `pps_allowance_exceeded`** | Tăng liên tục (+18,450 / phút) | **0 (Không bị drop gói tin hợp lệ)** | **Triệt tiêu hiện tượng nghẽn hàng đợi NIC** |

---

## 5. Tầm Nhìn Ứng Dụng Thực Tiễn Trong Doanh Nghiệp (Enterprise Value)

1. **Phòng thủ tấn công từ chối dịch vụ (Line-rate Cloud DDoS Mitigation)**:
   - Hủy bỏ các gói tin rác (SYN Flood, UDP Flood, NTP Amplification) ngay tại lớp đệm card mạng ENA với tốc độ hàng chục triệu gói/giây mà không làm ảnh hưởng tới các dịch vụ nghiệp vụ chạy cùng máy chủ.
2. **Hạ tầng Microservices & Service Mesh Thế Hệ Mới (Cilium / eBPF Service Mesh)**:
   - Loại bỏ hoàn toàn sự cồng kềnh của Sidecar Proxy (như Envoy trong Istio) bằng cách định tuyến trực tiếp giữa các Container Pods thông qua Socket eBPF, giảm độ trễ giao tiếp liên microservices tới 50%.
3. **Hệ thống Giao Dịch Tài Chính Tần Suất Cao (High-Frequency Trading on AWS)**:
   - Sử dụng công nghệ **AF_XDP (Address Family XDP)** để chuyển dữ liệu trực tiếp từ Ring Buffer của ENA vào vùng nhớ người dùng (Zero-Copy UMEM), đạt độ trễ xử lý gói tin mức **Sub-Microsecond (< 1 µs)**.
