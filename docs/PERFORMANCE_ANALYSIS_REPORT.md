# BÁO CÁO MÔ HÌNH THAM CHIẾU HIỆU CHUẨN & PHÂN TÍCH ĐÁNH GIÁ HIỆU NĂNG MẠNG AWS
## (CALIBRATED REFERENCE BENCHMARK REPORT – METHODOLOGY PROTOTYPE)

> [!IMPORTANT]
> **THÔNG CÁO MINH BẠCH HỌC THUẬT & CHẾ ĐỘ DỮ LIỆU (ACADEMIC TRANSPARENCY & DATA PROVENANCE NOTICE):**  
> 1. **Chế độ dữ liệu (Data Mode - Chế độ A)**: Toàn bộ số liệu trong báo cáo này được tính toán trên **Bộ Dữ liệu Tham chiếu Tổng hợp được Hiệu chuẩn (Calibrated Synthetic Reference Model - Methodology Prototype)**, được xây dựng dựa trên đặc tả kỹ thuật kiến trúc AWS Nitro Card, driver ENA Linux kernel 6.1+, và các mô hình độ trễ mạng Sydney (`ap-southeast-2`). Bộ dữ liệu này được thiết kế nhằm **kiểm chứng pipeline đo lường tự động, mô hình toán thống kê và hệ thống dashboard giám sát** mà không phát sinh chi phí hạ tầng AWS không cần thiết ($0.00). **Đây là nguyên mẫu phương pháp luận, không phải là kết quả đo lường production trực tiếp trên AWS.**
> 2. **Giảm Pseudoreplication**: Đơn vị phân tích độc lập là **independent run ($N = 3$)**. Hiệu ứng chính của cả TC-01 đến TC-04 dùng **Run-level Paired Deltas** và **Hierarchical Bootstrap (10,000 resamples)** hai tầng. Welch gộp chỉ là exploratory; $N=3$ vẫn giới hạn lực thống kê và không cho phép tuyên bố khái quát như một nghiên cứu production đa môi trường.
> 3. **Kiểm tra tính toàn vẹn tự động (Automated Checksum Verification)**: Mã nguồn [`analyze_results.py`](file:///e:/repo/lab-aws/network-performance-capstone/scripts/analyze_results.py) tự động đối chiếu mã băm SHA256 của toàn bộ 5 tệp tin thô bắt buộc trong [`results/raw/`](file:///e:/repo/lab-aws/network-performance-capstone/results/raw/) với [`checksums.sha256`](file:///e:/repo/lab-aws/network-performance-capstone/results/raw/checksums.sha256). Mọi trường hợp thiếu file hoặc sai lệch đều bị dừng ngay lập tức (fail-fast).
> 4. **Tránh hiểu lầm số học**: Giá trị $p$-value quá nhỏ do kích thước mẫu lớn được định dạng chuẩn xác là $p < 1 \times 10^{-300}$ (kèm cờ `numeric_underflow: true`), không bao giờ biểu diễn $p = 0.0$.

---

## 1. TỔNG HỢP KẾT QUẢ 4 KỊCH BẢN ĐỐI CHỨNG (3 KIẾN TRÚC DOANH NGHIỆP + 1 TỐI ƯU NHÂN LINUX)

Bảng số liệu dưới đây được trích xuất tự động từ nguồn dữ liệu duy nhất [`results/summary_statistics.json`](file:///e:/repo/lab-aws/network-performance-capstone/results/summary_statistics.json):

| Kịch Bản | Phân Loại | Bài Toán Kỹ Thuật | Mô Hình So Sánh | P50 (ms) | **P95 (ms)** | **P99 (ms)** | Tải CPU SoftIRQ / Throughput | Kiểm Định Thống Kê & Effect Size |
| :---: | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-01** | **Thực tế 1** | **Microservices & Fan-out RPC** | **VPC Peering**<br>vs **Transit Gateway** | 0.173<br>0.810 | **0.195**<br>**0.925** | **0.204**<br>**0.975** | N/A (Đo RTT)<br>N/A (Đo RTT) | **Hierarchical Bootstrap $\Delta$P99**: **+0.773 ms** ($CI_{95\%}$: [0.757, 0.792] ms)<br>Welch exploratory: $t = -477.15, p < 1 \times 10^{-300}$ |
| **TC-02B** | **Thực tế 2** | **Đồng bộ CSDL & Big Data ETL** | **MTU 1500 (Standard)**<br>vs **MTU 9001 (Jumbo)** | N/A<br>N/A | N/A<br>N/A | N/A<br>N/A | 68.25% SoftIRQ / 3.22 Gbps<br>**21.95% SoftIRQ / 4.85 Gbps** | **$\Delta$ SoftIRQ: -46.30 điểm %** ($CI_{95\%}$: [-46.67, -45.93])<br>**$\Delta$ throughput: +1.637 Gbps** (CI: [1.609, 1.669]); Welch exploratory |
| **TC-03** | **Thực tế 3** | **Tích hợp Đối tác B2B Trùng Dải IP** | **VPC Peering**<br>vs **AWS PrivateLink** | 0.174<br>0.510 | **0.197**<br>**0.581** | **0.210**<br>**0.604** | N/A (L4 Endpoint)<br>N/A (NLB Proxy) | **$\Delta$P99 PrivateLink - Peering: +0.395 ms** ($CI_{95\%}$: [0.386, 0.405]); Welch exploratory |
| **TC-04** | **Thử nghiệm 4**| **Chống Bão Hòa UDP tại DUT Ingress** | **Linux iptables**<br>vs **eBPF/XDP Native Hook** | N/A<br>N/A | N/A<br>N/A | N/A<br>N/A | 84.57% SoftIRQ / 1.15M PPS drop<br>**4.23% SoftIRQ / 4.95M PPS drop** | **$\Delta$ SoftIRQ: -80.34 điểm %** (CI: [-80.66, -79.98])<br>**$\Delta$ interval-P99: -14.156 ms** (CI: [-14.478, -13.820]) |

*(Ghi chú: Kịch bản TC-02A - Placement Group Same-AZ vs Cross-AZ là kiến trúc thiết kế mô hình lý thuyết (Architecture-planned), được ghi nhận trong phần Thiết kế kiến trúc).*

---

## 2. PHÂN TÍCH ĐỊNH LƯỢNG CHI TIẾT THEO TỪNG KỊCH BẢN

### 2.1. KỊCH BẢN 1 (TC-01): GIAO TIẾP MICROSERVICES & BACKEND API (VPC PEERING VS TRANSIT GATEWAY)
- **Thiết kế kiểm soát Confounding**: Cả hai máy chủ đích Server B1 (VPC Peering target) và Server B2 (TGW target) đều được đặt trong cùng Availability Zone `ap-southeast-2a`, cùng loại phiên bản `c6i.large`, không gắn Placement Group, và dùng cùng Security Group. Thiết kế này giúp **giảm thiểu tối đa các confounder đã nhận diện** để phản ánh chính xác sự khác biệt về đường truyền mạng (Network Routing Path).

#### A. Phân tích theo từng Run độc lập ($N=3$ Independent Runs):
Để giảm **pseudoreplication** (không xem 3,000 gói tin là 3,000 đơn vị độc lập), ta đánh giá độ trễ đuôi P99 trên từng run:
- **Run 1**: Peering P99 = `0.2000 ms` | TGW P99 = `0.9647 ms` | $\Delta \text{P99}_{1} = +0.7647\text{ ms}$
- **Run 2**: Peering P99 = `0.2035 ms` | TGW P99 = `0.9734 ms` | $\Delta \text{P99}_{2} = +0.7698\text{ ms}$
- **Run 3**: Peering P99 = `0.2061 ms` | TGW P99 = `0.9879 ms` | $\Delta \text{P99}_{3} = +0.7818\text{ ms}$
- **Chênh lệch trung bình theo run**: **$+0.7721\text{ ms}$** (Min: $+0.7647\text{ ms}$, Max: $+0.7818\text{ ms}$).

#### B. Ước lượng Kích thước Hiệu ứng bằng Hierarchical Bootstrap (10,000 Resamples):
- **Phương pháp**: Mỗi vòng lặp chọn ngẫu nhiên có hoàn lại các run ($k=3$), sau đó trong mỗi run chọn ngẫu nhiên có hoàn lại 1,000 gói tin của từng điều kiện, tính toán $\text{P99}_{\text{TGW}} - \text{P99}_{\text{Peering}}$.
- **Kết quả ước lượng**:
  - Điểm ước lượng $\Delta \text{P99}$: **$+0.7728\text{ ms}$**
  - **Khoảng tin cậy 95% Bootstrap ($CI_{95\%}$)**: **$[0.7566\text{ ms}, 0.7918\text{ ms}]$**
- **Độ trễ phân vị tổng thể (Reference Summary)**:
  - **VPC Peering**: Mean = `0.1726 ms`, P50 = `0.1726 ms`, P95 = `0.1955 ms`, P99 = `0.2040 ms`.
  - **Transit Gateway**: Mean = `0.8099 ms`, P50 = `0.8096 ms`, P95 = `0.9248 ms`, P99 = `0.9750 ms`.
- **Kiểm định tham số thăm dò (Exploratory Welch's t-Test)**:
  - $t = -477.15$, $df = 3224.6$, $p\text{-value} < 1 \times 10^{-300}$ (numeric underflow flag). Cohen's $d = -12.32$; exploratory only.
- **Ý nghĩa giả thuyết**: Mô hình tạo ra $\Delta P99\approx0.773$ ms để kiểm thử cách pipeline lượng hóa trade-off. Việc chọn Peering hay TGW trong production phải dựa trên Mode B, yêu cầu quản trị kết nối, chi phí và quy mô topology; Chế độ A không đủ để đưa ra mệnh lệnh kiến trúc.

---

### 2.2. KỊCH BẢN 2 (TC-02B): ĐỒNG BỘ CƠ SỞ DỮ LIỆU & BIG DATA ETL (MTU 1500 VS MTU 9001)
- **Ngữ cảnh**: Truyền dữ liệu lớn qua 4 luồng TCP song song (`iperf3 -P 4 -t 10`).

#### Bảng số liệu đối chứng MTU (30 intervals per condition across 3 runs):
| Cấu Hình MTU | Throughput TB ($\bar{X}$) | CPU SoftIRQ ($\bar{X}$) | Tốc độ gói tin ($\bar{X}$) | Khoảng tin cậy 95% SoftIRQ |
| :--- | :---: | :---: | :---: | :---: |
| **MTU 1500 (Standard)** | **3.20 Gbps** ($\pm 0.05$) | **67.94%** ($\pm 0.97\%$) | **261,618 PPS** | [67.59%, 68.28%] |
| **MTU 9001 (Jumbo Frame)**| **4.85 Gbps** ($\pm 0.06$) | **22.08%** ($\pm 0.58\%$) | **67,256 PPS** | [21.86%, 22.30%] |

- **Kiểm định thống kê SoftIRQ (Welch's t-Test)**:
  - $t = 248.72$, $df = 48.53$, $p\text{-value} = 4.94 \times 10^{-77}$; exploratory only.
  - Mức giảm SoftIRQ tuyệt đối: **$-46.30$ điểm phần trăm** ($CI_{95\%}$ run-aware: $[-46.67, -45.93]$).
- **Cơ chế kỹ thuật**: 
  - Khi dùng chuẩn MTU 1500, payload TCP tối đa (MSS) chỉ là 1,460 bytes. Để truyền đạt tốc độ ~3.2 Gbps, hệ điều hành phải xử lý hơn 261 nghìn gói tin mỗi giây, gây áp lực nghẽn ngắt mềm (`ksoftirqd`) chiếm tới 67.94% CPU.
  - Trong mô hình Chế độ A, MTU 9001 có PPS trung bình 67,151 thay vì 261,795 và SoftIRQ thấp hơn 46.30 điểm %. Đây là minh họa giả thuyết cơ chế, chưa phải phép đo CPU AWS.

---

### 2.3. KỊCH BẢN 3 (TC-03): TÍCH HỢP ĐỐI TÁC B2B TRÙNG DẢI IP (AWS PRIVATELINK VS VPC PEERING)
- **Ngữ cảnh**: Kết nối dịch vụ tới đối tác bên ngoài khi cả hai bên đều dùng dải IP `10.0.0.0/16`.

#### Bảng so sánh độ trễ Round-Trip Time (1,500 observations):
| Mô Hình Tích Hợp | Mean RTT (ms) | P50 (ms) | **P95 (ms)** | **P99 (ms)** | Khả năng giải quyết trùng IP |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **VPC Peering** | **0.1742** | 0.1743 | **0.1974** | **0.2099** | Không định tuyến được khi CIDR hai VPC chồng lấn |
| **AWS PrivateLink** | **0.5107** | 0.5102 | **0.5811** | **0.6045** | Mô hình kết nối dịch vụ không yêu cầu định tuyến CIDR end-to-end |

- **Welch RTT gộp (exploratory)**: $t = 299.85, df = 1854.2, p\text{-value} < 1 \times 10^{-300}$.
- **Chênh lệch mean của mô hình**: $+0.3366\text{ ms}$. Hiệu ứng suy luận chính là $\Delta P99=+0.3946\text{ ms}$ với hierarchical CI $[0.3862,0.4054]$ ms.
- **Ý nghĩa kỹ thuật**: PrivateLink hoạt động thông qua cơ chế Endpoint Service gắn với Network Load Balancer (NLB) ở tầng 4. Quá trình proxy và mapping địa chỉ IP riêng của AWS làm tăng độ trễ thêm $\approx 0.34\text{ ms}$, nhưng đây là kiến trúc chuẩn enterprise bắt buộc khi hai doanh nghiệp không thể thay đổi quy hoạch địa chỉ IP nội bộ của mình.

---

### 2.4. KỊCH BẢN 4 (TC-04): BẢO VỆ MÁY CHỦ TRƯỚC BÃO HÒA UDP BẰNG eBPF/XDP KERNEL-BYPASS
- **Kiến trúc đo lường, điều khiển và tính toán SoftIRQ Delta**: 
  - Máy client phát lưu lượng UDP Flood 64-byte tới DUT port 5201 và đồng thời phát lưu lượng TCP Probe hợp lệ tới DUT port 5202.
  - Cơ chế điều khiển bộ lọc (iptables hoặc XDP) và lấy mẫu SoftIRQ `/proc/stat`, `/proc/softirqs` được thực thi từ xa trên chính DUT thông qua AWS Systems Manager Run Command (`run_on_dut`), hoàn toàn không lấy mẫu trên client. Kết quả snapshot được truyền về controller qua SSM invocation stdout.
  - Tỷ lệ CPU SoftIRQ được tính bằng công thức delta chuẩn xác bởi `calculate_softirq_delta.py` trong cửa sổ phát tải ($T_1 \to T_6$):
    $$\text{SoftIRQ\%} = 100 \times \frac{\Delta \text{softirq jiffies}}{\Delta \text{total CPU jiffies}} = 100 \times \frac{\text{softirq}_{after} - \text{softirq}_{before}}{\text{total}_{after} - \text{total}_{before}}$$
  - Sau khi gắn hook, script tự động xác thực bằng lệnh `iptables -C` hoặc `ip -details link` (bắt buộc bằng chứng dương tính native/driver hook và từ chối `xdpgeneric`) kết hợp `bpftool net show`; hai map thực tế `xdp_config_map` và `xdp_stats_map` đều là điều kiện fail-fast.

#### Bảng số liệu đối chứng hiệu năng bảo vệ DUT (90 intervals per condition across 3 runs):
| Cơ Chế Bộ Lọc | Dropped PPS Quan Sát ($\bar{X}$) | CPU SoftIRQ ($\bar{X}$) | **Interval P50 Probe TCP** | **Interval P99 Probe TCP** | Trạng Thái Phục Vụ Gói Hợp Lệ |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Linux iptables (-j DROP)**| **1,148,535 PPS** | **84.57%** | **1.850 ms** | **14.505 ms** | Giá trị mô hình tham chiếu |
| **eBPF Native XDP (XDP_DROP)**| **4,953,503 PPS** | **4.23%** | **0.190 ms** | **0.347 ms** | Giá trị mô hình tham chiếu |

- **Kiểm định thống kê CPU SoftIRQ (Welch's t-Test)**:
  - Welch gộp: $t = 677.28$, $df = 101.0$, $p\text{-value} = 1.43 \times 10^{-186}$; exploratory only.
  - Mức giảm SoftIRQ: **$-80.34$ điểm phần trăm** ($CI_{95\%}$ run-aware: $[-80.66, -79.98]$).
- **Kiểm định độ trễ đuôi của gói hợp lệ (TCP Probe Interval P99)**:
  - $t = 107.84$, $df = 89.1$, $p\text{-value} = 3.37 \times 10^{-96} \ll 0.05$.
- **Cơ chế kỹ thuật**:
  - Cơ chế giả thuyết: `iptables` xử lý sau khi đã đi vào conventional kernel networking path, còn native XDP có thể trả `XDP_DROP` trước khi tạo `sk_buff`.
  - Các giá trị 84.57%, 4.23%, 14.505 ms và 0.347 ms là đầu ra generator Chế độ A dùng để kiểm tra pipeline. Chỉ Mode B mới được dùng để xác nhận mức cải thiện trên ENA.

---

## 3. CÂY QUYẾT ĐỊNH THIẾT KẾ KIẾN TRÚC MẠNG DOANH NGHIỆP (DECISION TREE)

```
                            BÀI TOÁN KẾT NỐI MẠNG CLOUD
                                         |
                 +-----------------------+-----------------------+
                 |                                               |
         [Nội bộ Doanh Nghiệp]                         [Đối tác / B2B SaaS]
                 |                                               |
        +--------+--------+                                      v
        |                 |                          AWS PrivateLink (TC-03)
  [Dưới 10 VPCs]    [Hàng chục/trăm VPCs]            - Giải quyết trùng IP CIDR
        |                 |                          - Bảo mật một chiều L4
        v                 v                          - Trễ thêm +0.34ms do NLB
   VPC Peering     Transit Gateway (TC-01)
     (TC-01)       - Quản trị kết nối tập trung
  - P99 < 0.23ms   - Chấp nhận trễ +0.84ms tại P99
  - Không mất phí  - Dễ dàng chèn Inspection VPC
        |
        v
  [Truyền tải lớn / Database Replication / ETL] (TC-02B)
        |
        v
  Mô hình MTU 9001 -> SoftIRQ thấp hơn 46.30 điểm %, throughput cao hơn 1.637 Gbps
        |
        v
  [Hạ tầng High-Throughput / Chống Tấn Công UDP Ingress / FinTech] (TC-04)
        |
        v
  Ứng dụng eBPF/XDP Native Hook -> Giảm 80.34% SoftIRQ, xử lý 4.95M PPS tại driver ENA
```

---

## 4. PHÂN TÍCH RỦI RO HIỆU LỰC & GIỚI HẠN CỦA ĐỀ TÀI (THREATS TO VALIDITY & LIMITATIONS)

### 4.1. Internal Validity (Hiệu lực nội tại)
- **Noisy Neighbor**: Chế độ A không mô hình hóa đầy đủ multi-tenancy. Terraform giữ cùng instance type/AZ để chuẩn hóa thiết kế, nhưng chỉ randomized Mode B runs mới đo được biến thiên host theo thời gian.
- **Cửa sổ đo đạc SoftIRQ**: Tải SoftIRQ được đo bằng delta của `/proc/stat` và `/proc/softirqs` ngay trong cửa sổ phát sinh tải (từ $T_1$ bắt đầu flood đến $T_6$ kết thúc flood), loại bỏ nhiễu nền ngoài thời gian thử nghiệm.
- **Xác minh Hook từ xa**: Sử dụng AWS Systems Manager Run Command để điều khiển DUT, loại bỏ rủi ro chạy nhầm script bộ lọc trên máy client.

### 4.2. External Validity (Khả năng khái quát hóa)
- **Phạm vi phần cứng**: Đề tài tập trung vào dòng máy ảo `c6i.large` trên nền tảng AWS Nitro System tại Region Sydney (`ap-southeast-2`). Kết quả không đại diện cho tất cả các thế hệ ENA, các dòng vi xử lý ARM/Graviton hoặc máy chủ Bare-metal.
- **Tính chất dữ liệu**: Toàn bộ số liệu trong báo cáo này thuộc **Chế độ A (Calibrated Synthetic Reference Model)**, phản ánh mô hình toán học dựa trên đặc tả kỹ thuật phần cứng để kiểm chứng pipeline tự động hóa. Khi triển khai đo đạc thực nghiệm thực tế, cần thay thế bằng raw logs từ các phiên benchmark AWS trực tiếp.

### 4.3. Construct Validity (Hiệu lực khái niệm)
- **Khái niệm P99 trong TC-04**: `14.505 ms` là trung bình của các giá trị interval-P99 do generator tạo, không phải P99 gộp của packet-level probe và không phải observation AWS.
- **Tốc độ gói tin (Packet Rate)**: `4,950,056 PPS` là giá trị của mô hình tham chiếu Chế độ A cho tốc độ xử lý/loại bỏ tại interface ENA; không phải observation AWS và không đồng nhất với wire-rate lý thuyết.

### 4.4. Conclusion Validity (Hiệu lực kết luận)
- **Số lượng Run**: Phiên pilot gồm $N=3$ independent runs. Để đưa ra kết luận mang tính sản xuất hoàn chỉnh, giao thức mở rộng khuyến nghị thực hiện 10–30 runs ngẫu nhiên chéo (Randomized Crossover A/B testing).
- **Pseudoreplication**: Phân tích chính của TC-01 đến TC-04 dùng chênh lệch ghép cặp theo run và Hierarchical Bootstrap 10,000 resamples để phản ánh cấu trúc quan sát lồng. Các Welch test trên dữ liệu gộp được gắn nhãn `exploratory_only_pooled_observations` trong nguồn JSON và không phải bằng chứng suy luận chính.
