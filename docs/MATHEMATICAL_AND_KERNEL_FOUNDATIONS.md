# MÔ HÌNH TOÁN HỌC & CƠ CHẾ NHÂN HỆ ĐIỀU HÀNH TRONG HIỆU NĂNG MẠNG AWS

Tài liệu này cung cấp các mô hình toán học giải tích, nguyên lý vận hành tầng truyền tải (Transport Layer) và các cơ chế xử lý I/O mạng cấp thấp của nhân hệ điều hành Linux (Linux Kernel Network Subsystem) khi chạy trên nền tảng ảo hóa phần cứng **AWS Nitro System**.

---

## 1. Mô Hình Toán Học Hiệu Năng TCP

### 1.1. Tích Số Băng Thông - Độ Trễ (Bandwidth-Delay Product - BDP)
BDP là đại lượng đo lường thể tích dữ liệu tối đa có thể "lưu thông đồng thời trên đường cáp quang" (in-flight data) giữa hai đầu mút kết nối tại bất kỳ thời điểm nào mà chưa cần nhận gói xác nhận (ACK).

$$\text{BDP (bits)} = \text{Bandwidth (bits/sec)} \times \text{RTT (sec)}$$

$$\text{BDP (Bytes)} = \frac{\text{Bandwidth (bps)} \times \text{RTT (sec)}}{8}$$

#### Ví dụ tính toán trên môi trường AWS:
1. **Trường hợp 1: Hai EC2 cùng Availability Zone qua VPC Peering (`c6i.large`)**
   - Băng thông $BW = 10\text{ Gbps} = 10^{10}\text{ bps}$
   - Độ trễ vòng $RTT = 0.18\text{ ms} = 0.00018\text{ s}$
   $$\text{BDP} = \frac{10^{10} \times 0.00018}{8} = 225,000\text{ Bytes} \approx 220\text{ KB}$$
   - *Nhận xét*: BDP nhỏ (chỉ 220 KB), một socket TCP tiêu chuẩn với cửa sổ mặc định của Linux (`net.ipv4.tcp_wmem`) có thể dễ dàng lấp đầy đường ống này và đạt 10 Gbps ngay trong vài chu kỳ RTT.

2. **Trường hợp 2: Hai EC2 liên vùng (Inter-Region: N. Virginia `us-east-1` tới US-East `us-east-1`)**
   - Băng thông $BW = 10\text{ Gbps}$
   - Độ trễ vòng $RTT = 160\text{ ms} = 0.16\text{ s}$
   $$\text{BDP} = \frac{10^{10} \times 0.16}{8} = 200,000,000\text{ Bytes} \approx 190.7\text{ MB}$$
   - *Nhận xét*: Cần một cửa sổ nhận TCP (TCP Receive Window - RWIN) tối thiểu **191 MB** để một luồng đơn TCP duy nhất có thể bão hòa đường truyền 10 Gbps! Nếu kích thước bộ đệm socket mặc định bị giới hạn ở 4 MB hoặc không bật **TCP Window Scaling (RFC 1323)**, thông lượng tối đa của 1 TCP stream sẽ bị nghẽn ở:
   $$\text{Throughput}_{\max} = \frac{\text{Buffer Size}}{\text{RTT}} = \frac{4\text{ MB}}{0.16\text{ s}} = 25\text{ MB/s} = 200\text{ Mbps}$$
   (Chỉ tận dụng được 2% băng thông 10 Gbps có sẵn!).

---

### 1.2. Công Thức Mathis & Tác Động Của Tỷ Lệ Mất Gói (Packet Loss)
Công thức Mathis (Mathis, Semke, Mahdavi, 1997) xác định cận trên của thông lượng TCP ổn định khi xảy ra hiện tượng mất gói ngẫu nhiên:

$$\text{Throughput} \le \frac{\text{MSS}}{\text{RTT}} \times \frac{C}{\sqrt{p}}$$

Trong đó:
- $\text{MSS}$ (Maximum Segment Size): Kích thước phân đoạn dữ liệu TCP tối đa ($\text{MTU} - 40\text{ bytes}$ gồm 20 bytes IPv4 header tiêu chuẩn + 20 bytes TCP header không options).
  - Với MTU 1500 (Standard Ethernet): $\text{MSS} = 1500 - 20 - 20 = 1460\text{ bytes}$.
  - Với MTU 9001 (AWS Jumbo Frames): $\text{MSS} = 9001 - 20 - 20 = 8961\text{ bytes}$ (chính xác theo RFC 791/793, không làm tròn 8960).
- $\text{RTT}$: Thời gian trễ khứ hồi (Round-Trip Time).
- $p$: Tỷ lệ mất gói tin ngẫu nhiên (Packet Loss Probability, ví dụ $0.01 = 1\%$).
- $C$: Hằng số thực nghiệm phụ thuộc vào cơ chế ACK (thông thường $C \approx \sqrt{3/2} \approx 1.22$ với delayed ACK).

#### Phân tích định lượng ý nghĩa của Jumbo Frames & Giới hạn giả định của mô hình Mathis:
Từ công thức trên, tỷ lệ gia tăng thông lượng lý thuyết giữa Jumbo Frames và Standard Frames là:
$$\frac{\text{Throughput}_{\text{MTU 9001}}}{\text{Throughput}_{\text{MTU 1500}}} = \frac{8961}{1460} \approx 6.138$$

> [!NOTE]
> **Điều kiện áp dụng & Giới hạn của Mô hình Mathis:**
> 1. **Giả định toán học lý tưởng**: Tỷ lệ ~6.14 lần này là **cận trên tiệm cận lý thuyết** (theoretical upper bound), chỉ xuất hiện khi thỏa mãn đồng thời:
>    - Cùng một độ trễ RTT và cùng một xác suất mất gói độc lập $p$ trên mỗi packet.
>    - Thuật toán TCP ở chế độ tránh tắc nghẽn ổn định (Congestion Avoidance regime của CUBIC/Reno).
>    - Băng thông không bị bão hòa bởi giới hạn phần cứng (Line-rate NIC ceiling, CPU interrupt saturation, hoặc Receive Window bounds).
> 2. **Tác động của Hardware Offload (TSO/GSO/GRO)**: Trong hệ thống AWS Nitro thực tế với ENA driver, tính năng **TCP Segmentation Offload (TSO)** cho phép nhân Linux chuyển khối dữ liệu 64 KB xuống NIC phân mảnh phần cứng. Do đó, lợi ích thực tế của Jumbo Frames MTU 9001 trong trung tâm dữ liệu AWS chủ yếu đến từ việc **giảm thiểu 83.7% số lượng ngắt SoftIRQ trên CPU** và giảm áp lực lên các hàng đợi (Ring Buffers) của Nitro ASIC, thay vì tăng tuyến tính đúng 6.14 lần trong mọi tình huống.

---

### 1.3. Thuật Toán Điều Khiển Tắc Nghẽn: TCP CUBIC vs Google BBR
1. **TCP CUBIC (Loss-based Congestion Control)**:
   - Thuật toán mặc định trên hầu hết các bản phân phối Linux (kể cả Amazon Linux 2023).
   - Tăng dần kích thước cửa sổ tắc nghẽn ($cwnd$) theo hàm bậc ba cho đến khi phát hiện **mất gói** (Packet Loss) thì mới coi đó là tín hiệu tắc nghẽn và cắt giảm $cwnd$.
   - *Hạn chế*: Trên đường truyền đám mây tốc độ cao có độ trễ lớn (Long Fat Networks - LFN), mất gói ngẫu nhiên (chưa chắc do nghẽn) sẽ làm CUBIC sụt giảm thông lượng nghiêm trọng.
2. **Google BBR (Bottleneck Bandwidth and RTT - Delay-based)**:
   - Đo lường trực tiếp tốc độ chuyển tiếp tối đa của nút nghẽn (Bottleneck Bandwidth) và RTT tối thiểu thực tế, duy trì lượng in-flight data đúng bằng $1 \times \text{BDP}$.
   - Không phụ thuộc vào hiện tượng mất gói để điều chỉnh tốc độ.
   - *Thực nghiệm kích hoạt BBR trên EC2*:
     ```bash
     sudo sysctl -w net.core.default_qdisc=fq
     sudo sysctl -w net.ipv4.tcp_congestion_control=bbr
     ```
     Giúp duy trì thông lượng ổn định ngay cả khi đường truyền phát sinh nhiễu jitter hoặc mất gói nhẹ.

---

## 2. Kiến Trúc Ảo Hóa Mạng AWS Nitro & Linux Kernel I/O

```
+-------------------------------------------------------------------------------+
|                             USER SPACE APPLICATION                            |
|                       (iperf3, sockperf, Redis, Nginx)                         |
+-------------------------------------------------------------------------------+
                                      |  sys_sendto / sys_recvfrom
                                      v
+-------------------------------------------------------------------------------+
|                               LINUX KERNEL                                    |
|  +-------------------------------------------------------------------------+  |
|  | Socket Buffer (sk_buff) -> TCP/IP Protocol Stack (qdisc: fq / fq_codel) |  |
|  +-------------------------------------------------------------------------+  |
|  | Hardware Offloads:                                                      |  |
|  | - TSO (TCP Segmentation Offload): CPU giao việc chia gói to cho NIC     |  |
|  | - GRO (Generic Receive Offload): Ghép nhiều gói nhỏ thành sk_buff lớn   |  |
|  | - RSS (Receive Side Scaling): Phân phối gói vào nhiều hàng đợi RX       |  |
|  +-------------------------------------------------------------------------+  |
|  | ENA Linux Kernel Driver (drivers/net/ethernet/amazon/ena/)             |  |
|  | Multi-Queue Ring Buffers (TX/RX Descriptors)                            |  |
+-------------------------------------------------------------------------------+
                                      |  PCIe Direct Memory Access (DMA)
                                      v
+-------------------------------------------------------------------------------+
|                     AWS NITRO CARD FOR NETWORKING (ASIC)                      |
|  - Hardware Rate Limiters (Tokens Bucket)                                     |
|  - ENA Allowance Counters (bw_in, bw_out, pps, conntrack)                     |
|  - Encapsulation Engine (Geneve / VPC Tunneling / Flow Tracking)              |
|  - Physical Line-rate Uplink (10G / 25G / 100G Ethernet)                      |
+-------------------------------------------------------------------------------+
```

### 2.1. Các Cơ Chế Offload Phần Cứng Của Card Mạng ENA
Để đạt được thông lượng hàng chục Gbps mà không làm CPU đạt 100%, ENA kết hợp các cơ chế offload:
- **TSO (TCP Segmentation Offload)**:
  - Ứng dụng gửi một khối dữ liệu lớn (ví dụ 64 KB) xuống kernel. Thay vì CPU phải chia nhỏ thành 44 gói tin MTU 1500 và tạo 44 headers, CPU chuyển thẳng 64 KB xuống card mạng ENA. Chip Nitro tự động phân mảnh và chèn header phần cứng.
- **GRO (Generic Receive Offload)**:
  - Ở chiều nhận, khi hàng loạt gói tin liên tiếp của cùng một luồng TCP đến, driver ENA gộp chúng lại thành một bộ đệm duy nhất (`sk_buff`) trước khi chuyển lên TCP stack của Linux, giảm số lần gọi hàm và ngắt kernel.
- **RSS (Receive Side Scaling)**:
  - ENA tính toán giá trị băm Toeplitz Hash trên 4-tuple (Source IP, Dest IP, Source Port, Dest Port) của gói tin, từ đó định tuyến luồng dữ liệu vào các hàng đợi nhận (RX Queues) khác nhau gắn với từng lõi CPU (vCPU).
  - Điều này giải thích tại sao khi đo `iperf3` với tham số `-P 8` (8 luồng song song), tải xử lý ngắt SoftIRQ được chia đều cho các vCPU, giúp thông lượng đạt tối đa 10 Gbps.

---

### 2.2. Cơ Chế Throttling Bằng Thuật Toán Token Bucket Của Nitro
AWS quản lý giới hạn băng thông bằng thuật toán **Token Bucket** chạy trực tiếp trên ASIC Nitro:
1. **Burst Bucket (Tín dụng bùng nổ)**:
   - Các instance cỡ nhỏ và vừa (như `c6i.large`, `t3.large`) được cấp một lượng burst credit nhất định.
   - Khi luồng traffic tăng vọt, instance có thể truyền với tốc độ tối đa (Up to 12.5 Gbps).
2. **Exhaustion & Throttling (Cạn tín dụng & Bóp nghẽn)**:
   - Nếu truyền liên tục quá vài phút, burst bucket cạn kiệt, Nitro Card hạ tốc độ về mức **Baseline Bandwidth** (thường là 0.75 Gbps - 1.25 Gbps cho cỡ `large`).
   - Mọi gói tin vượt quá tốc độ baseline sẽ bị chip Nitro drop tại chỗ, và biến đếm `bw_out_allowance_exceeded` sẽ tăng lên tương ứng.

---

## 3. Bảng Tối Ưu Hóa Tham Số Hạt Nhân Linux (Kernel Sysctl Tuning) Cho 10G/25G ENA

Trước khi tiến hành các bài benchmark hiệu năng cao, các kỹ sư hệ thống cần áp dụng bảng tham số sysctl sau:

```ini
# /etc/sysctl.d/99-aws-network-tuning.conf

# Tăng kích thước hàng đợi backlog cho card mạng
net.core.netdev_max_backlog = 100000

# Tăng dung lượng bộ đệm socket tối đa và mặc định cho cả TX và RX
net.core.rmem_default = 262144
net.core.rmem_max = 67108864
net.core.wmem_default = 262144
net.core.wmem_max = 67108864

# Cấu hình dynamic window scaling cho TCP (min, default, max)
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# Kích hoạt TCP Window Scaling (RFC 1323)
net.ipv4.tcp_window_scaling = 1

# Kích hoạt Selective Acknowledgements (SACK)
net.ipv4.tcp_sack = 1

# Kích hoạt Forward Acknowledgements
net.ipv4.tcp_fack = 1

# Giảm số lần retry SYN
net.ipv4.tcp_syn_retries = 2
net.ipv4.tcp_synack_retries = 2

# Tăng kích thước bảng theo dõi kết nối nf_conntrack (nếu sử dụng iptables/SG)
net.netfilter.nf_conntrack_max = 1048576
```

Lệnh áp dụng ngay lập tức mà không cần khởi động lại máy chủ:
```bash
sudo sysctl --system
```

---

## 4. Phương Pháp Luận Thống Kê & Kiểm Định Ý Nghĩa (Statistical Significance)

Phần này định nghĩa phương pháp sẽ dùng cho Mode B và cách kiểm thử pipeline trên dữ liệu synthetic Mode A. Thống kê không thể “loại trừ” noisy neighbor, burst allowance hay jitter; randomized crossover, cooldown, blocking và telemetry chỉ giúp đo hoặc giảm bias từ các yếu tố đó.

### 4.1. Quy Chuẩn Số Phiên Chạy: Pilot Runs ($N = 3$) vs Giao Thức Mở Rộng ($N = 10 \sim 30$)
- **Phiên thử nghiệm sơ bộ (Pilot Runs - $N = 3$)**:
  - Phù hợp cho việc xác thực sơ bộ tính khả thi của pipeline kiểm thử và đo đạc sơ bộ độ lệch chuẩn.
  - *Lưu ý toán học*: Với $N = 3$ ($df = 2$), hệ số Student-t cho khoảng tin cậy 95% là $t_{0.025, 2} = 4.303$. Khoảng tin cậy này tương đối rộng và nhạy cảm với các điểm dị biệt (outliers).
- **Giao thức chuẩn nghiệm thu học thuật & sản xuất ($N = 10 \sim 30$ Runs)**:
  - Áp dụng kỹ thuật **Thiết kế ngẫu nhiên hóa khối (Randomized Block / Crossover A/B Testing)**: Thứ tự chạy các cấu hình (ví dụ: Peering trước rồi TGW, hoặc đảo ngược TGW trước rồi Peering) được tráo ngẫu nhiên để triệt tiêu độ lệch do hiện tượng làm nóng bộ đệm (Warm-up effect), biến động tài nguyên theo thời gian (temporal variance) và hiện tượng cạn kiệt ENA Token Bucket burst allowance.
  - Giữa mỗi phiên chạy có chu kỳ nghỉ tĩnh (Cooldown: 10 - 15 giây) để kernel giải phóng bộ đệm và socket tái lập trạng thái cân bằng.

- **Giá trị trung bình mẫu (Sample Mean)**:
  $$\bar{X} = \frac{1}{N} \sum_{i=1}^N X_i$$
- **Phương sai mẫu (Sample Variance)** & **Độ lệch chuẩn (Sample Standard Deviation)**:
  $$S^2 = \frac{1}{N-1} \sum_{i=1}^N (X_i - \bar{X})^2, \quad S = \sqrt{S^2}$$
- **Sai số chuẩn của giá trị trung bình (Standard Error of the Mean - SEM)**:
  $$\text{SEM} = \frac{S}{\sqrt{N}}$$
  *Hội tụ SEM*: Khi các mẫu đo đạc là độc lập, cùng phân phối (i.i.d) và có phương sai hữu hạn, việc tăng số lần chạy $N$ làm mẫu số $\sqrt{N}$ tăng lên, giúp giá trị trung bình mẫu $\bar{X}$ tiệm cận với giá trị kỳ vọng thực tế của quần thể $\mu$.

### 4.2. Khoảng Tin Cậy 95% (95% Confidence Interval - CI)
Do số lượng mẫu phiên chạy $N$ thường nhỏ hơn 30, phân phối chuẩn $Z$ không được áp dụng trực tiếp. Thay vào đó, đề tài áp dụng **Phân phối Student (Student's t-distribution)** với bậc tự do $df = N - 1$:

$$\text{CI}_{95\%} = \left[ \bar{X} - t_{\alpha/2, df} \times \text{SEM}, \ \bar{X} + t_{\alpha/2, df} \times \text{SEM} \right]$$

Với mức ý nghĩa $\alpha = 0.05$ (độ tin cậy $1 - \alpha = 95\%$):
- Khi $N = 3$ ($df = 2$): $t_{0.025, 2} = 4.303$.
- Khi $N = 5$ ($df = 4$): $t_{0.025, 4} = 2.776$.
- Khi $N = 10$ ($df = 9$): $t_{0.025, 9} = 2.262$.
- Khi $N = 30$ ($df = 29$): $t_{0.025, 29} = 2.045$.

### 4.3. Welch's t-Test — Chỉ dùng như Phân tích Thăm dò
Welch's t-Test không giả định hai phương sai bằng nhau ($\sigma_1^2 \neq \sigma_2^2$), nhưng vẫn giả định các observation đưa vào kiểm định là độc lập. Packet/interval trong cùng một run không đáp ứng giả định này. Vì vậy pipeline chỉ giữ Welch trên dữ liệu gộp để mô tả thăm dò và gắn nhãn machine-readable `exploratory_only_pooled_observations`; không dùng p-value này làm bằng chứng suy luận chính.

- **Giả thuyết vô hiệu ($H_0$)**: $\mu_1 = \mu_2$ (Không có sự khác biệt có ý nghĩa thống kê giữa hai kiến trúc).
- **Giả thuyết đối ($H_1$)**: $\mu_1 \neq \mu_2$ (Có sự khác biệt thực sự về hiệu năng giữa hai kiến trúc).

Thống kê kiểm định $t$:
$$t = \frac{\bar{X}_1 - \bar{X}_2}{\sqrt{\frac{S_1^2}{N_1} + \frac{S_2^2}{N_2}}}$$

Bậc tự do hiệu chỉnh theo công thức Welch–Satterthwaite:
$$df \approx \frac{\left(\frac{S_1^2}{N_1} + \frac{S_2^2}{N_2}\right)^2}{\frac{(S_1^2/N_1)^2}{N_1-1} + \frac{(S_2^2/N_2)^2}{N_2-1}}$$

#### Phân tích chính cho TC-01:

- Đơn vị độc lập: ba run, không phải 6.000 packet.
- Hiệu ứng ghép cặp: $\Delta_i=P99_{TGW,i}-P99_{Peering,i}$ lần lượt là 0.7647, 0.7698 và 0.7818 ms.
- Hierarchical Bootstrap hai tầng 10.000 lần cho ước lượng $\Delta P99=0.7728$ ms, $CI_{95\%}=[0.7566,0.7918]$ ms.
- Welch gộp cho $t=-477.15$, $df=3224.64$, $p<10^{-300}$ chỉ là exploratory vì 6.000 packet không phải 6.000 experimental units.
- Không diễn giải p-value là “xác suất $H_0$ đúng”, không dùng cụm “bác bỏ hoàn toàn”, và không suy rộng Chế độ A thành hiệu năng AWS production.

### 4.4. Phương Pháp Xác Định Phân Vị Độ Trễ Đuôi (P50, P95, P99) & Bootstrap CI
- **Nguyên lý thu thập phân vị**:
  - Không thể tính P95 hay P99 bằng cách lấy trung bình cộng của 3 giá trị phân vị riêng rẽ.
  - Phân vị được tính trực tiếp từ observation-level samples trong từng run. Bộ Chế độ A hiện có 1.000 RTT cho mỗi path/run ở TC-01 và 500 RTT cho mỗi condition/run ở TC-03; giao thức Mode B nên tăng cỡ mẫu sau phân tích power/precision thay vì áp một ngưỡng 10.000 tùy ý.
- **Khoảng tin cậy cho P99 (Non-parametric Bootstrap)**:
  - Do phân vị đuôi P99 không tuân theo phân phối chuẩn, pipeline dùng **Hierarchical Bootstrap** hai tầng với $B = 10{,}000$: lấy mẫu lại run độc lập, sau đó observation trong run. Cách này phản ánh cấu trúc lồng, nhưng không bù được hạn chế chỉ có ba run.

### 4.5. Cơ Sở Toán Xác Suất Của Độ Trễ Đuôi Trong Kiến Trúc Microservices (Fan-Out RPC)
Tại sao trong sản xuất thực tế, các kỹ sư SRE và Cloud Architect luôn đặt trọng tâm vào **P95 và P99** thay vì P50 (Median) hay Mean?

Xét một kiến trúc phân tán gồm $M$ dịch vụ microservices độc lập được gọi song song phục vụ một yêu cầu từ người dùng (Fan-out RPC Pattern):
- Xác suất để một dịch vụ con có thời gian xử lý vượt ngưỡng P99 là $p = 0.01$ (1%).
- **Giả định toán học cơ sở**: Các nhánh RPC độc lập nhau về mặt thống kê.
- Xác suất để toàn bộ $M$ dịch vụ con **đều an toàn (không nhánh nào bị trễ P99)**:
  $$P(\text{Tất cả an toàn}) = (1 - p)^M = (0.99)^M$$
- Xác suất để người dùng cuối **bị ảnh hưởng bởi ít nhất một dịch vụ chạm ngưỡng trễ P99**:
  $$P(\text{Người dùng chịu trễ P99}) = 1 - (1 - 0.01)^M$$

#### Bảng xác suất thực tế theo số lượng Microservices ($M$):
| Số lượng Microservices ($M$) | $P(\text{Chịu trễ P95})$ | $P(\text{Chịu trễ P99})$ | Đánh giá Tác Động Người Dùng |
| :---: | :---: | :---: | :--- |
| $M = 1$ (Ứng dụng đơn khối Monolith) | 5.0% | 1.0% | Chỉ 1% người dùng cảm nhận chậm |
| $M = 10$ (Hệ thống Microservices nhỏ) | 40.1% | 9.6% | Gần 10% người dùng bị ảnh hưởng |
| $M = 50$ (Enterprise E-commerce) | 92.3% | **39.5%** | Gần 40% người dùng chịu độ trễ đuôi! |
| $M = 100$ (Fintech / Large-Scale Cloud) | 99.4% | **63.4%** | **Hơn 63% người dùng bị ảnh hưởng bởi P99!** |

> [!WARNING]
> **Giới hạn thực tế trong môi trường sản xuất:**
> 1. **Tương quan độ trễ (Correlated Latency)**: Trong thực tế, các vi dịch vụ thường không hoàn toàn độc lập; chúng có thể chịu ảnh hưởng tương quan (chẳng hạn dùng chung cụm database, nghẽn luồng I/O mạng, hoặc hiện tượng Stop-the-world của Java Garbage Collector).
> 2. **Chuỗi gọi tuần tự (Sequential Call Chain)**: Khi các microservices được gọi nối tiếp thay vì song song, độ trễ người dùng cuối là **tổng đại số của các độ trễ thành phần**, khiến việc tối ưu P95/P99 ở từng chặng mạng giữa các VPC trở thành điều kiện tiên quyết để giữ SLA hệ thống.
