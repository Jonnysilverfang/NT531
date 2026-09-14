# ĐỀ CƯƠNG KHÓA LUẬN TỐT NGHIỆP & KỊCH BẢN BẢO VỆ ĐỀ TÀI
## CHUYÊN NGÀNH: MẠNG MÁY TÍNH & HỆ THỐNG ĐIỆN TOÁN ĐÁM MÂY (CLOUD COMPUTING)

Tài liệu này cung cấp khung cấu trúc chuẩn của một cuốn **Khóa luận tốt nghiệp Đại học / Luận văn Thạc sĩ** hoặc **Báo cáo Chuyên ngành Doanh nghiệp**, kèm theo **kịch bản trình chiếu Slide bảo vệ (Slide Deck & Defense Script)** chi tiết từ 15 đến 20 phút trước hội đồng phản biện, đồng bộ với nguồn dữ liệu Mode A [`results/summary_statistics.json`](../results/summary_statistics.json).

---

# PHẦN I: KHUNG CẤU TRÚC KHÓA LUẬN TỐT NGHIỆP CHUẨN

## TÊN ĐỀ TÀI:
**NGHIÊN CỨU, THIẾT KẾ VÀ XÂY DỰNG NGUYÊN MẪU MÔ HÌNH THAM CHIẾU HIỆU NĂNG MẠNG ĐA TẦNG TRÊN AWS KẾT HỢP TỐI ƯU HÓA TẦNG NHÂN BẰNG eBPF/XDP**  
*(Calibrated Reference Benchmark & Architecture Prototype: Cloud Networking Performance and Linux Kernel-Bypass Optimization using eBPF/XDP on AWS Nitro ENA Architecture – Methodology Prototype)*

---

### MỤC LỤC CHI TIẾT CỦA LUẬN VĂN (TABLE OF CONTENTS)

```
LỜI CAM ĐOAN
LỜI CẢM ƠN
TÓM TẮT KHÓA LUẬN (ABSTRACT - TIẾNG VIỆT & TIẾNG ANH)
DANH MỤC THUẬT NGỮ & TỪ VIẾT TẮT (ACRONYMS: eBPF, XDP, ENA, TGW, BDP, MTU, SR-IOV, NLB, RTT, PPS)
DANH MỤC CÁC BẢNG BIỂU
DANH MỤC CÁC HÌNH ẢNH & SƠ ĐỒ

CHƯƠNG 1: TỔNG QUAN VÀ ĐẶT VẤN ĐỀ
  1.1. Bối cảnh điện toán đám mây và sự phát triển của kiến trúc Multi-VPC / Multi-Account
  1.2. Thách thức trong việc tối ưu hóa hiệu năng mạng và chi phí truyền dữ liệu
  1.3. Vấn đề nghẽn CPU SoftIRQ của Linux Network Stack truyền thống ở tốc độ cao
  1.4. Mục tiêu và phạm vi nghiên cứu của đề tài
  1.5. Phương pháp nghiên cứu thực nghiệm và Chế độ Dữ liệu Tham chiếu Đối chứng Chuẩn
  1.6. Bố cục của khóa luận

CHƯƠNG 2: CƠ SỞ LÝ THUYẾT & NỀN TẢNG CÔNG NGHỆ
  2.1. Kiến trúc ảo hóa phần cứng AWS Nitro System & Thẻ mạng ENA (Elastic Network Adapter)
  2.2. Cơ chế phân mảnh và kích thước gói tin: MTU 1500 vs Jumbo Frames MTU 9001
  2.3. Các mô hình kết nối liên VPC trên AWS:
       2.3.1. VPC Peering: Cơ chế định tuyến mạng trục (Line-rate AWS Backbone)
       2.3.2. AWS Transit Gateway: Kiến trúc Hub-and-Spoke và cơ chế xử lý gói tin
       2.3.3. AWS PrivateLink: Mô hình dịch vụ một chiều dựa trên Network Load Balancer
  2.4. Vị trí vật lý và độ trễ: Khái niệm Cluster Placement Group và cấu trúc ToR Switch
  2.5. Các mô hình toán học hiệu năng mạng: BDP (Bandwidth-Delay Product) và công thức Mathis
  2.6. Công nghệ đột phá eBPF (Extended Berkeley Packet Filter) & XDP (eXpress Data Path)
  2.7. Cơ sở lý thuyết Thống kê: Pseudoreplication, Run-level Analysis, và Hierarchical Bootstrap

CHƯƠNG 3: THIẾT KẾ NGUYÊN MẪU KIẾN TRÚC VÀ PHƯƠNG PHÁP ĐO
  3.1. Thiết kế topo mạng thực nghiệm tại Region N. Virginia (us-east-1)
  3.2. Quy hoạch dải địa chỉ IP (CIDR Blocks) và phân bổ Subnet
  3.3. Xây dựng mã nguồn tự động hóa hạ tầng (Infrastructure as Code) bằng Terraform
  3.4. Lập trình chương trình eBPF/XDP lọc gói tin ở cấp độ driver ENA (BTF Maps, Direct Packet Access)
  3.5. Thiết lập quy trình đo kiểm chuẩn (Standard Operating Procedure - SOP):
       - Kịch bản TC-01: So sánh VPC Peering và Transit Gateway (Fan-out RPC)
       - Kịch bản TC-02A: Thiết kế vị trí vật lý (Cluster Placement Group vs Non-Placement)
       - Kịch bản TC-02B: Đánh giá tác động của MTU 9001 lên PPS và tải SoftIRQ CPU
       - Kịch bản TC-03: Đánh giá độ trễ PrivateLink và giải quyết trùng dải IP CIDR
       - Kịch bản TC-04: Đo đạc đối chứng eBPF/XDP Native Hook vs Linux iptables tại DUT Ingress

CHƯƠNG 4: KẾT QUẢ MÔ HÌNH THAM CHIẾU VÀ PHÂN TÍCH CHUYÊN SÂU
  4.1. Phân tích định lượng Thông lượng (Throughput) và số gói tin mỗi giây (PPS)
  4.2. Phân tích phân bố độ trễ khứ hồi (RTT Latency Distribution P50, P95, P99)
  4.3. Đánh giá mức tiêu thụ tải CPU SoftIRQ giữa MTU 1500 và MTU 9001
  4.4. Đánh giá mô hình tham chiếu eBPF/XDP: giảm 80.34 điểm % SoftIRQ, xử lý 4.95 triệu PPS tại RX ring
  4.5. Phân tích thống kê: Khoảng tin cậy 95% bằng Hierarchical Bootstrap và Kiểm định Welch
  4.6. Phân tích tương quan Hiệu năng / Chi phí (Cost-to-Performance Analysis)
  4.7. Rủi ro hiệu lực (Threats to Validity) và Các giới hạn của đề tài (Limitations)

CHƯƠNG 5: KHUYẾN NGHỊ KIẾN TRÚC VÀ KẾT LUẬN
  5.1. Khung khuyến nghị ra quyết định kiến trúc mạng cho doanh nghiệp (Decision Tree)
  5.2. Cẩm nang xử lý sự cố mạng AWS (Troubleshooting Runbook)
  5.3. Các đóng góp chính của đề tài (Khoa học & Thực tiễn)
  5.4. Hướng phát triển tiếp theo (eBPF Service Mesh Cilium trên EKS)

TÀI LIỆU THAM KHẢO (THEO CHUẨN IEEE)
PHỤ LỤC: MÃ NGUỒN TERRAFORM, MÃ NGUỒN eBPF/C VÀ PIPELINE KIỂM THỬ
```

---

# PHẦN II: KỊCH BẢN THUYẾT TRÌNH BẢO VỆ ĐỀ TÀI (DEFENSE SLIDE DECK)
*(Thời lượng: 15 - 20 phút | 12 Slides trọng tâm, đồng bộ tuyệt đối với `results/summary_statistics.json`)*

```
[SLIDE 1: TRANG TIÊU ĐỀ]
- Tiêu đề: Calibrated Reference Benchmark & Architecture Prototype cho Hiệu năng Mạng AWS
- Học viên / Người thực hiện: [Tên học viên]
- Giảng viên hướng dẫn: [Tên GVHD]
- Đơn vị: Khoa Công nghệ Thông tin / Mạng máy tính & Điện toán đám mây

[SLIDE 2: ĐẶT VẤN ĐỀ & BỐI CẢNH DOANH NGHIỆP]
- Vấn đề: Doanh nghiệp di chuyển lên AWS đối mặt với bài toán kết nối Multi-VPC:
  + Chọn VPC Peering: Nhanh nhất, rẻ nhất nhưng khó scale khi số lượng VPC lớn.
  + Chọn Transit Gateway: Quản lý tập trung nhưng trễ hơn và phát sinh chi phí truyền dữ liệu.
  + Chọn PrivateLink: Bảo mật Zero-Trust, giải quyết trùng IP nhưng chỉ hỗ trợ L4 qua NLB.
- Thách thức tại máy chủ đích: Các cuộc tấn công UDP Flood bão hòa mạng làm nghẽn CPU ngắt mềm (SoftIRQ) của nhân Linux truyền thống (iptables).
- Câu hỏi nghiên cứu: Trade-offs định lượng chính xác là bao nhiêu và eBPF/XDP giải quyết nghẽn SoftIRQ như thế nào?

[SLIDE 3: NỀN TẢNG CÔNG NGHỆ (AWS NITRO, ENA & eBPF/XDP)]
- Card mạng AWS Nitro ENA: Công nghệ ảo hóa SR-IOV phần cứng, bypass hypervisor.
- Jumbo Frames MTU 9001: Giảm 74.3% số gói tin truyền tải cho cùng dung lượng dữ liệu.
- eBPF/XDP (eXpress Data Path): Nạp bytecode an toàn vào nhân Linux, thực thi ngay tại RX hook của driver ENA trước khi nhân Linux cấp phát sk_buff.

[SLIDE 4: MÔ HÌNH TOÁN HỌC TRUYỀN THÔNG & PHƯƠNG PHÁP THỐNG KÊ]
- BDP (Bandwidth-Delay Product) & Công thức Mathis chứng minh sự suy giảm thông lượng khi có độ trễ đuôi và mất gói tin.
- Phương pháp thống kê đa tầng (Hierarchical Methodology):
  + Đơn vị phân tích độc lập là Run (N = 3 runs trong phiên Pilot đối chứng).
  + Hierarchical Bootstrap (10,000 resamples): Lấy mẫu ngẫu nhiên lại các Run, sau đó lấy mẫu lại các gói tin/interval để xây dựng khoảng tin cậy 95% không phụ thuộc phân phối chuẩn.
  + Định dạng p-value chuẩn xác: Sử dụng p < 1e-300 thay vì hiển thị p = 0.0 do underflow số học.

[SLIDE 5: NGUYÊN MẪU KIẾN TRÚC MẠNG TẠI N. VIRGINIA (us-east-1)]
- Topo 3 VPC: VPC A (Client), VPC B (Target Server B1 và Server B2), VPC Shared (PrivateLink Endpoint).
- Khử Confounding: Cả Server B1 (Peering target) và B2 (TGW target) đều đặt cùng AZ-a (us-east-1a), cùng instance c6i.large, không gắn Placement Group.
- Quản trị tự động không phụ thuộc SSH: Điều khiển DUT từ xa thông qua AWS Systems Manager Run Command (run_on_dut).

[SLIDE 6: MA TRẬN 4 KỊCH BẢN ĐỐI CHỨNG THAM CHIẾU]
- TC-01: Giao tiếp Microservices & Backend API (VPC Peering vs Transit Gateway).
- TC-02A: Thiết kế vị trí vật lý (Cluster Placement Group - Mô hình kiến trúc).
- TC-02B: Đồng bộ Cơ sở dữ liệu & Big Data ETL (MTU 1500 vs Jumbo Frames MTU 9001).
- TC-03: Tích hợp Đối tác B2B Trùng Dải IP (AWS PrivateLink vs VPC Peering).
- TC-04: Chống bão hòa lưu lượng UDP Flood tại DUT Ingress (Linux iptables vs eBPF/XDP Native Hook).

[SLIDE 7: KẾT QUẢ TC-01 - ĐỘ TRỄ MICROSERVICES & PHÂN TÍCH RUN-LEVEL]
- Dữ liệu đối chứng chuẩn (6,000 observations):
  + VPC Peering: Mean = 0.173 ms | P50 = 0.173 ms | P95 = 0.195 ms | P99 = 0.204 ms.
  + Transit Gateway: Mean = 0.810 ms | P50 = 0.810 ms | P95 = 0.925 ms | P99 = 0.975 ms.
- Phân tích chênh lệch theo Run (Run-level Deltas):
  + Run 1 Delta: +0.823 ms | Run 2 Delta: +0.851 ms | Run 3 Delta: +0.852 ms.
  + Mean Delta = +0.842 ms.
- Hierarchical Bootstrap 95% CI (10,000 resamples): Delta P99 = +0.773 ms [0.757, 0.792] ms.
- Welch exploratory: t = -477.15, df = 3224.6, p < 1e-300, Cohen's d = -12.32.
- Ý nghĩa: Chuyển mạch TGW làm tăng ~0.84 ms độ trễ P99. Fan-out RPC 20 services sẽ bị cộng dồn đáng kể!

[SLIDE 8: KẾT QUẢ TC-02B & TC-03 - JUMBO FRAMES & ZERO-TRUST PRIVATELINK]
- TC-02B (Big Data): 
  + MTU 1500: Throughput 3.20 Gbps | SoftIRQ 67.94% | 261,618 PPS.
  + MTU 9001: Throughput 4.85 Gbps | SoftIRQ 22.08% | 67,256 PPS.
  + $\Delta$ SoftIRQ = -46.30 điểm % (Hierarchical CI: [-46.67, -45.93]); $\Delta$ throughput = +1.637 Gbps (CI: [1.609, 1.669]).
- TC-03 (B2B SaaS): 
  + PrivateLink giải quyết 100% xung đột trùng dải IP CIDR (10.0.0.0/16).
  + Độ trễ P99 là 0.604 ms (Peering 0.210 ms); $\Delta$P99 run-aware = +0.395 ms (CI: [0.386, 0.405]).

[SLIDE 9: KẾT QUẢ TC-04 - ĐỘT PHÁ CÔNG NGHỆ eBPF/XDP KERNEL-BYPASS]
- Thử thách 5 triệu gói tin UDP Flood 64 bytes tại DUT Ingress:
  + Linux iptables: CPU SoftIRQ 84.57%, Drop rate 1.149M PPS, interval-P99 14.505 ms trong mô hình.
  + eBPF Native XDP: CPU SoftIRQ 4.23%; $\Delta$ SoftIRQ = -80.34 điểm % (CI: [-80.66, -79.98]); drop-rate tăng 3.805M PPS và interval-P99 giảm 14.156 ms (CI: [-14.478, -13.820]).
- Cơ chế: Loại bỏ gói rác tại RX ring của driver ENA trước khi nhân Linux cấp phát sk_buff.

[SLIDE 10: PHÂN TÍCH HIỆU QUẢ KINH TẾ (COST-TO-PERFORMANCE)]
- So sánh bài toán chi phí truyền tải 50 TB dữ liệu hàng tháng (N. Virginia):
  + VPC Peering (Same AZ): $0.00 / tháng (Chi phí tối ưu nhất).
  + AWS PrivateLink: $500.00 / tháng ($0.01/GB chi phí xử lý dữ liệu qua NLB).
  + AWS Transit Gateway: $1,000.00 / tháng ($0.02/GB chi phí xử lý dữ liệu qua TGW).
- Đánh đổi: Doanh nghiệp chi trả thêm chi phí để đổi lấy khả năng mở rộng kiến trúc và quản trị tập trung.

[SLIDE 11: CÂY QUYẾT ĐỊNH THIẾT KẾ KIẾN TRÚC MẠNG (DECISION TREE)]
- Cây quyết định chuẩn xác theo 4 bài toán:
  + Microservices nhạy cảm trễ (< 1 ms): Bắt buộc dùng VPC Peering.
  + Kết nối diện rộng hàng chục VPC: Dùng Transit Gateway, chèn Inspection VPC.
  + Tích hợp đối tác bên ngoài trùng IP: Dùng AWS PrivateLink.
  + Hệ thống dữ liệu lớn & lưu lượng cao: Bật MTU 9001 kết hợp eBPF/XDP tại Ingress.

[SLIDE 12: TỔNG KẾT & HỎI ĐÁP (Q&A)]
- Tóm tắt các đóng góp khoa học và thực tiễn của đề tài.
- Trả lời câu hỏi của Hội đồng phản biện.
```

---

# PHẦN III: TÀI LIỆU THAM KHẢO CHUẨN IEEE

1. AWS Documentation, *"Elastic Network Adapter (ENA) performance monitoring on Linux instances"*, Amazon Web Services Inc., 2024.
2. AWS Whitepaper, *"Building a Scalable and Secure Multi-VPC AWS Network Infrastructure"*, AWS Prescriptive Guidance, 2023.
3. M. Mathis, J. Semke, and J. Mahdavi, *"The macroscopic behavior of the TCP congestion avoidance algorithm"*, ACM SIGCOMM Computer Communication Review, vol. 27, no. 3, pp. 67-82, 1997.
4. N. Cardwell, Y. Cheng, C. S. Gunn, S. H. Yeganeh, and V. Jacobson, *"BBR: Congestion-Based Congestion Control"*, Communications of the ACM, vol. 60, no. 2, pp. 58-66, 2017.
5. AWS Documentation, *"Transit Gateway quotas and performance limits"*, Amazon Web Services Inc., 2024.
6. RFC 1323, *"TCP Extensions for High Performance"*, Internet Engineering Task Force (IETF), 1992.
7. RFC 793, *"Transmission Control Protocol Specification"*, Defense Advanced Research Projects Agency (DARPA), 1981.

---

# PHẦN IV: CHIẾN LƯỢC TRẢ LỜI 7 CÂU HỎI HÓA GIẢI HỘI ĐỒNG PHẢN BIỆN (MASTER-LEVEL DEFENSE Q&A)

### Câu 1: “6.000 packet trong TC-01 có nghĩa là N=6.000 đơn vị thực nghiệm độc lập không? Có bị Pseudoreplication không?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, hoàn toàn không. Về mặt phương pháp luận thống kê, đơn vị thực nghiệm độc lập (Experimental Unit) trong đề tài là **Independent Run ($N = 3$)**, còn các packet là những quan sát lồng ghép (Nested Observations) bên trong từng run. Do các packet trong cùng một run cùng chia sẻ hàng đợi NIC, tài nguyên CPU và trạng thái môi trường, chúng không độc lập hoàn toàn.  
  > Để giảm lỗi Pseudoreplication:  
  > 1. Nhóm đã thực hiện phân tích chênh lệch theo từng run riêng biệt: $\Delta \text{P99}_{\text{run 1}} = +0.823\text{ ms}$, $\Delta \text{P99}_{\text{run 2}} = +0.851\text{ ms}$, $\Delta \text{P99}_{\text{run 3}} = +0.852\text{ ms}$ (Trung bình: $+0.842\text{ ms}$).  
  > 2. Áp dụng **Hierarchical Bootstrap (10,000 resamples)** hai tầng: lấy mẫu lại run, sau đó observation trong run để ước lượng $CI_{95\%}$ cho $\Delta \text{P99}$ là $[0.757, 0.792]$ ms. Cách này giảm pseudoreplication nhưng không xóa giới hạn lực thống kê do chỉ có $N=3$ run."*

### Câu 2: “Dữ liệu này có thực sự được đo trên AWS hay là dữ liệu Synthetic?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, bộ số liệu hiện tại là **Chế độ A - Calibrated Synthetic Reference Model**. Các tham số tham chiếu kiến trúc Nitro/ENA và mô hình N. Virginia, nhưng không chứng minh phân phối hiệu năng thực tế của AWS.
  > Mục đích của bộ dữ liệu này là để **kiểm chứng pipeline đo lường tự động, mô hình toán thống kê và hệ thống dashboard giám sát** mà không làm phát sinh chi phí AWS trong giai đoạn thẩm định ($0.00). Nhóm không trình bày số liệu này như là đo lường production trực tiếp. Toàn bộ mã nguồn tự động hóa hạ tầng (Terraform), script thu thập telemetry và pipeline phân tích đã sẵn sàng để chuyển sang Chế độ B (Empirical AWS Benchmark) ngay khi có hạ tầng trực tiếp."*

### Câu 3: “Làm sao chứng minh chương trình eBPF/XDP thực sự chạy trên Native Mode của driver ENA mà không phải Generic/SKB Mode?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, chương trình XDP của đề tài được nạp trực tiếp qua hook của driver ENA bằng cờ `xdpdrv` (hoặc `ip link set dev eth0 xdp obj ...`).  
  > Nhóm đã tích hợp mã xác minh tự động ngay trong script điều khiển DUT (`dut_server_setup.sh`):  
  > 1. Sử dụng `ip -details link show dev eth0` để kiểm tra cờ trạng thái `prog/xdp id ... mode native/driver`. Nếu phát hiện chạy ở chế độ generic (skb), hệ thống sẽ fail-fast báo lỗi.  
  > 2. Sử dụng `bpftool net show dev eth0` như một điều kiện bắt buộc để xác nhận program đang gắn tại RX hook; lỗi lệnh hoặc thiếu attachment đều làm phép đo thất bại.  
  > 3. Kiểm tra bắt buộc hai BPF map thực có trong mã nguồn là `xdp_config_map` và `xdp_stats_map`; thiếu bất kỳ map nào đều fail-fast. `xdp_stats_map` cung cấp bộ đếm pass/drop/bytes để đối chứng với telemetry ENA."*

### Câu 4: “Tại sao trong một số kết quả kiểm định thống kê lại xuất hiện p-value = 0?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, trong lý thuyết xác suất và thống kê máy tính, p-value không bao giờ bằng 0 tuyệt đối. Giá trị `0.0` xuất hiện ở các công cụ phân tích cơ bản là do hiện tượng **tràn số dưới (Floating-point Numeric Underflow)** khi $p$-value quá nhỏ (nhỏ hơn giới hạn số thực kép IEEE 754 là xấp xỉ $10^{-308}$).  
  > Trong pipeline phân tích của đề tài (`analyze_results.py`), nhóm đã xử lý chuẩn xác bằng cách:  
  > 1. Gắn cờ `numeric_underflow: true` và xuất kết quả dưới dạng chuỗi toán học chuẩn: $p < 1 \times 10^{-300}$.  
  > 2. Không dựa đơn thuần vào $p$-value mà tập trung vào **Kích thước hiệu ứng (Effect Size Cohen's $d = -12.21$)** và **Khoảng tin cậy Bootstrap 95%** để chứng minh ý nghĩa thực tiễn (Practical Significance) của kết quả."*

### Câu 5: “Tại sao lại dùng Welch's t-Test khi hai điều kiện (Peering và TGW) được đo trong cùng một run?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, phép kiểm định Welch's t-Test ban đầu chỉ được sử dụng như một **phân tích thăm dò sơ bộ (Exploratory Data Analysis)** trên phân phối gộp.  
  > Vì hai cấu hình được ghép theo run, phân tích chính của cả bốn TC dùng **Run-level Paired Deltas** kết hợp **Hierarchical Bootstrap**. Welch trên observation gộp chỉ là exploratory và được gắn nhãn như vậy trong JSON. Với $N=3$, kết quả vẫn là bằng chứng prototype, chưa đủ để khái quát production."*

### Câu 6: “XDP có thực sự bypass hoàn toàn nhân Linux không?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, nhóm xin làm rõ chính xác thuật ngữ học thuật:  
  > XDP **không hoàn toàn bypass nhân Linux** giống như DPDK (chuyển toàn bộ quyền điều khiển card mạng lên Userspace). XDP là một công nghệ **Kernel-integrated Packet Processing**:  
  > 1. Mã bytecode eBPF vẫn được nạp và kiểm tra tính an toàn bởi Linux BPF Verifier, và thực thi trong ngữ cảnh ngắt của nhân (NAPI poll context).  
  > 2. Điều XDP “bypass” là **conventional network stack** trước cấp phát `sk_buff`, Netfilter và conntrack. Mức giảm 80.34 điểm % là đầu ra Chế độ A; chỉ được gọi là kết quả empirical sau khi Mode B lưu bằng chứng native-driver hook và raw telemetry trên ENA."*

### Câu 7: “Con số 4.95 Mpps trong kịch bản TC-04 có phải là Wire-rate không?”
- **Chiến lược trả lời chuẩn mực**:
  > *"Kính thưa Hội đồng, con số 4.95 Mpps là **giá trị mô hình Chế độ A** dùng để kiểm chứng pipeline, không phải packet rate quan sát trên `eth0`.  
  > Nó cũng không phải wire-rate. Với frame Ethernet tối thiểu, phép tính 10 GbE xấp xỉ 14.88 Mpps chỉ là mốc lý thuyết bao gồm framing/IFG. Nguyên nhân giới hạn thực tế chỉ được kết luận sau Mode B có raw counter, offered load và bằng chứng hook."*
