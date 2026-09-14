# BẬC THẦY THI CỬ MẠNG AWS (AWS NETWORKING EXAM MASTERY)
## 10 BÀI TOÁN THỰC TẾ & BẪY KỸ THUẬT TỪ KỲ THI ANS-C01 VÀ DOP-C02

Tài liệu này đúc kết 10 bài toán kiến trúc mạng kinh điển, thường xuyên xuất hiện trong kỳ thi chuyên gia mạng cao cấp **AWS Certified Advanced Networking - Specialty (ANS-C01)** và **AWS Certified DevOps Engineer - Professional (DOP-C02)**. Mỗi bài toán được phân tích theo mô hình: **Ngữ cảnh thực tế -> Vấn đề kỹ thuật -> Phân tích bẫy -> Giải pháp kiến trúc tối ưu**.

---

### Bài Toán 1: Bão Hòa Băng Thông VPN & Cơ Chế Mở Rộng Qua Transit Gateway (ANS-C01 Domain 1: Network Design - Hybrid Connectivity)

- **Đề bài thực tế**: Một tập đoàn bán lẻ mở rộng quy mô. Lưu lượng truyền dữ liệu giữa Data Center On-premises và các máy chủ Amazon EC2 trong nhiều VPC bị nghẽn do chạm trần thông lượng của kết nối AWS Site-to-Site VPN đơn lẻ nối tới AWS Transit Gateway (TGW). Yêu cầu kỹ sư mạng tăng băng thông kết nối lên trên 4 Gbps với chi phí thấp nhất và không làm gián đoạn hạ tầng hiện có.
- **Phân tích bẫy**:
  - *Bẫy 1*: Một đường hầm IPsec VPN tiêu chuẩn (Standard Tunnel) của AWS bị giới hạn ở mức **1.25 Gbps** do thông lượng xử lý mã hóa AES của phần cứng VPN endpoint. Tuy nhiên, trên AWS Transit Gateway và AWS Cloud WAN, AWS hiện đã hỗ trợ tùy chọn **Large Bandwidth VPN Tunnels** (lên tới **5 Gbps** mỗi tunnel tại các Region được hỗ trợ).
  - *Bẫy 2*: Đối với standard tunnel 1.25 Gbps hoặc khi router On-premises không hỗ trợ tunnel 5 Gbps, nếu chỉ sử dụng định tuyến tĩnh (Static Routing), lưu lượng chỉ đi qua một tunnel duy nhất (Active/Passive), không thể cân bằng tải.
- **Giải pháp tối ưu**:
  - Thiết lập **nhiều kết nối Site-to-Site VPN động (Dynamic BGP-based)** nối tới AWS Transit Gateway.
  - Kích hoạt tính năng **Equal-Cost Multi-Path (ECMP)** trên Transit Gateway.
  - BGP tự động quảng bá các dải mạng giống nhau với cùng chỉ số AS-Path qua 4 standard tunnels đồng thời, cho phép phân phối luồng lưu lượng cân bằng tải theo thuật toán băm (5-tuple hashing), nâng tổng băng thông khả dụng lên tới:
  $$\text{Throughput}_{\text{total}} = 4 \times 1.25\text{ Gbps} = 5.0\text{ Gbps}$$
  - *(Lựa chọn kiến trúc hiện đại)*: Hoặc bật Large Bandwidth VPN tunnel (5 Gbps) trực tiếp trên Transit Gateway nếu thiết bị On-premises hỗ trợ.

---

### Bài Toán 2: Asymmetric Routing Qua Stateful Firewall Trên Transit Gateway

- **Đề bài thực tế**: Doanh nghiệp triển khai kiến trúc Centralized Inspection VPC chứa cụm tường lửa thế hệ mới (Next-Generation Firewall - NGW) để kiểm tra toàn bộ lưu lượng giữa các VPC. Mặc dù cấu hình route table đã chính xác, người dùng liên tục phàn nàn về việc kết nối TCP bị ngắt quãng, timeout chập chờn (intermittent drops).
- **Phân tích bẫy**:
  - Mặc định, khi Transit Gateway chuyển tiếp gói tin qua một VPC Attachment có nhiều Availability Zone, TGW sử dụng thuật toán băm dựa trên địa chỉ IP để chọn một ENI attachment ngẫu nhiên trong một AZ bất kỳ.
  - Chiều đi (SYN packet) đi qua Firewall ở AZ-a -> Firewall ghi nhận vào bảng State Table (phiên hợp lệ).
  - Chiều về (SYN-ACK packet) do thuật toán băm của TGW lại bị đẩy qua ENI ở AZ-b và tới Firewall ở AZ-b -> Firewall ở AZ-b **drop ngay lập tức** vì chưa từng thấy gói tin SYN của phiên này!
- **Giải pháp tối ưu**:
  - Kích hoạt **Appliance Mode** trên Transit Gateway VPC Attachment gắn với Inspection VPC:
    ```bash
    aws ec2 modify-transit-gateway-vpc-attachment \
      --transit-gateway-attachment-id tgw-attach-xxxxxx \
      --options ApplianceModeSupport=enable
    ```
  - *Cơ chế*: Khi Appliance Mode được bật, TGW đảm bảo cả chiều đi (request) và chiều về (response) của cùng một phiên TCP đối xứng 100% qua cùng một Availability Zone trong suốt vòng đời kết nối.

---

### Bài Toán 3: Ngắt Kết Nối Database Nhàn Rỗi Sau Đúng 350 Giây (NAT Gateway Idle Timeout)

- **Đề bài thực tế**: Ứng dụng Backend chạy trên EC2 trong Private Subnet thực hiện các câu truy vấn cơ sở dữ liệu phân tích nặng (Batch ETL Query) ra một database bên thứ ba trên Internet qua NAT Gateway. Các truy vấn chạy trên 6 phút luôn bị ngắt đột ngột với lỗi `Connection reset by peer` hoặc `Socket closed unexpectedly`.
- **Phân tích bẫy**:
  - AWS NAT Gateway có một giới hạn cứng không thể thay đổi: **Idle Connection Timeout = 350 giây**.
  - Nếu một kết nối TCP không có bất kỳ gói tin dữ liệu nào đi qua trong 350s (trong khi máy chủ database vẫn đang tính toán query ngầm), NAT Gateway sẽ xóa trạng thái phiên NAT khỏi bảng theo dõi. Khi database gửi kết quả về, NAT Gateway sẽ gửi gói TCP RST để đóng phiên!
- **Giải pháp tối ưu**:
  - Cấu hình **TCP Keepalive** trên hệ điều hành của máy chủ EC2 với chu kỳ thăm dò nhỏ hơn 300 giây:
    ```bash
    sudo sysctl -w net.ipv4.tcp_keepalive_time=120
    sudo sysctl -w net.ipv4.tcp_keepalive_intvl=30
    sudo sysctl -w net.ipv4.tcp_keepalive_probes=5
    ```
  - Định kỳ mỗi 120 giây, hệ điều hành sẽ gửi 1 gói tin TCP Keepalive nhỏ (1 byte ack probe) để thông báo cho NAT Gateway rằng phiên kết nối vẫn đang hoạt động, ngăn chặn NAT Gateway đóng phiên sớm.

---

### Bài Toán 4: Tối Ưu Chi Phí Truyền Hàng Chục Terabyte Dữ Liệu (VPC Peering vs TGW vs PrivateLink)

- **Đề bài thực tế**: Một ứng dụng Data Lake cần truyền tải 50 Terabyte (50,000 GB) dữ liệu mỗi tháng từ VPC nguồn sang VPC đích trong cùng Region N. Virginia. Kiến trúc sư cần lựa chọn giải pháp có chi phí thấp nhất và độ trễ thấp nhất.
- **Phân tích so sánh chi phí dữ liệu**:
  1. **Phương án Transit Gateway**:
     - Phí xử lý dữ liệu: $50,000\text{ GB} \times \$0.02/\text{GB} = \mathbf{\$1,000 / \text{tháng}}$ (Chưa kể phí attachment $0.05/giờ).
  2. **Phương án AWS PrivateLink**:
     - Phí xử lý dữ liệu: $50,000\text{ GB} \times \$0.01/\text{GB} = \mathbf{\$500 / \text{tháng}}$ (Chưa kể phí NLB và endpoint).
  3. **Phương án VPC Peering**:
     - Phí xử lý dữ liệu trong cùng một Availability Zone (Same-AZ): **\$0.00 / GB**!
     - Chi phí truyền 50 TB = **\$0.00**!
- **Giải pháp tối ưu**:
  - Thiết lập **VPC Peering** trực tiếp giữa hai VPC.
  - Sử dụng **Zonal DNS Hostname** để đảm bảo traffic client ở AZ-a kết nối trực tiếp tới server ở AZ-a, triệt tiêu 100% chi phí truyền dữ liệu và đạt độ trễ thấp nhất (~0.18ms).

---

### Bài Toán 5: Tối Ưu Độ Trễ Dưới Miligiây Cho Cụm Máy Chủ Tính Toán (HPC & AI Training)

- **Đề bài thực tế**: Một hệ thống tính toán xử lý mô hình Deep Learning phân tán (Distributed Training) yêu cầu giao tiếp giữa các node tính toán qua giao thức NCCL với độ trễ cực thấp (Sub-millisecond RTT) và thông lượng mạng tối đa.
- **Giải pháp tối ưu**:
  - Khởi tạo cụm EC2 instance trong cùng một **Cluster Placement Group** trong một Availability Zone duy nhất.
  - Sử dụng các dòng máy chủ chuyên dụng hỗ trợ **Enhanced Networking Adapter (ENA)** như `c6i`, `c6in` hoặc `p4de`.
  - Kích hoạt **Jumbo Frames (MTU 9001)** trên hệ điều hành để giảm thiểu số lượng ngắt CPU xuống 83%.
  - Kết quả: Độ trễ RTT giữa các máy chủ giảm xuống mức **< 100 microsecond (0.1ms)**, thông lượng luồng đơn đạt tối đa băng thông phần cứng.

---

### Bài Toán 6: Lỗi Black Hole Do Kích Thước Gói Tin (ANS-C01 Domain 4: Network Security & Troubleshooting - PMTUD Failure)

- **Đề bài thực tế**: Kỹ sư mạng bật MTU 9001 trên các máy chủ EC2 để tối ưu hóa truyền file trong nội bộ VPC. Tuy nhiên, khi một máy chủ EC2 cố gắng tải một file lớn lên máy chủ On-premises qua đường truyền hybrid kết nối router biên MTU 1500 (hoặc VPN tunnel), kết nối bị treo vô tận sau khi hoàn tất TCP 3-way handshake.
- **Phân tích bẫy**:
  - *Lưu ý về Direct Connect MTU*: AWS Direct Connect thực tế có hỗ trợ Jumbo Frames (**MTU 9001** cho Private VIF và **MTU 8500** cho Transit VIF). Lỗi Black Hole chỉ xảy ra khi một đoạn mạng trên đường đi (router On-premises, router biên trung gian, hoặc IPsec VPN tunnel) chỉ hỗ trợ MTU 1500 mà PMTUD bị vô hiệu hóa.
  - Gói SYN/ACK ban đầu có kích thước nhỏ (<100 bytes) nên đi qua bình thường.
  - Khi bắt đầu truyền khối dữ liệu lớn, EC2 gửi gói tin kích thước 9001 bytes kèm cờ `DF = 1` (Don't Fragment).
  - Khi gói tin tới router có MTU 1500, router buộc phải drop gói tin và gửi lại gói thông báo lỗi **ICMP Type 3 Code 4 (Destination Unreachable: Fragmentation Needed)** để yêu cầu EC2 giảm kích thước gói tin.
  - Tuy nhiên, Security Group hoặc Firewall phía EC2 đã cấu hình chặn mọi lưu lượng ICMP!
  - EC2 không bao giờ nhận được thông báo ICMP, tiếp tục retry gửi lại gói tin 9001 bytes -> Kết nối bị treo hoàn toàn (Hiện tượng **Black Hole PMTUD**).
- **Giải pháp tối ưu**:
  - Luôn mở luật Inbound trong Security Group cho gói tin **ICMP Type 3 Code 4** từ mọi hướng.
  - Hoặc cấu hình **TCP MSS Clamping** trên router biên để tự động ép giá trị MSS của gói tin SYN xuống tối đa 1460 bytes.

---

### Bài Toán 7: Giải Quyết Xung Đột Trùng Lặp Dải Mạng IP (Overlapping CIDRs)

- **Đề bài thực tế**: Doanh nghiệp A tiến hành mua lại doanh nghiệp B. Thật không may, cả hai doanh nghiệp đều đang sử dụng cùng một dải mạng `10.0.0.0/16` cho VPC sản xuất của mình. Cần cho phép ứng dụng bên A gọi API sang service bên B mà không được phép thay đổi CIDR của bất kỳ VPC nào.
- **Phân tích bẫy**:
  - *VPC Peering*: Hoàn toàn không thể tạo được kết nối peering nếu hai VPC có CIDR trùng lặp hoặc chồng lấn (Overlapping).
  - *Transit Gateway*: Không thể định tuyến thông thường vì bảng định tuyến không thể phân biệt được `10.0.0.0/16` là của VPC nào.
- **Giải pháp tối ưu**:
  - Sử dụng **AWS PrivateLink (VPC Endpoint Service)**.
  - Phía VPC nhà cung cấp dịch vụ (Doanh nghiệp B): Đặt ứng dụng đằng sau một **Internal Network Load Balancer (NLB)** và tạo một **VPC Endpoint Service**.
  - Phía VPC người dùng (Doanh nghiệp A): Tạo một **Interface VPC Endpoint** gắn vào subnet của mình.
  - PrivateLink chỉ hoạt động ở tầng 4 (TCP) thông qua địa chỉ IP riêng của ENI Endpoint, hoàn toàn độc lập và miễn nhiễm với xung đột dải mạng ở tầng 3!

---

### Bài Toán 8: Tăng Tốc Đường Truyền Cho SD-WAN Virtual Appliances (TGW Connect)

- **Đề bài thực tế**: Doanh nghiệp triển khai thiết bị định tuyến ảo của bên thứ ba (Cisco SD-WAN / Fortinet) trên EC2 để quản lý mạng toàn cầu. Khi kết nối thiết bị này vào Transit Gateway qua IPsec VPN, băng thông bị giới hạn ở 1.25 Gbps và tiêu tốn nhiều CPU để mã hóa IPsec.
- **Giải pháp tối ưu**:
  - Sử dụng **Transit Gateway Connect Attachment**.
  - Transit Gateway Connect sử dụng giao thức **Generic Routing Encapsulation (GRE)** thay vì IPsec, chạy trực tiếp trên kết nối VPC Attachment chuẩn.
  - Hỗ trợ thông lượng lên tới **5 Gbps mỗi GRE tunnel** (gấp 4 lần IPsec) và hỗ trợ BGP dynamic routing đầy đủ với chi phí xử lý CPU cực thấp.

---

### Bài Toán 9: Cảnh Báo Sớm Hiện Tượng Drop Gói Âm Thầm Bằng ENA Metrics

- **Đề bài thực tế**: Khách hàng báo cáo thỉnh thoảng một số API request tới cụm microservices bị chậm đột xuất (độ trễ tăng từ 20ms lên 3000ms), nhưng CPU và RAM của EC2 chỉ mới sử dụng 50%. Bảng điều khiển CloudWatch EC2 mặc định không có bất kỳ cảnh báo nào.
- **Phân tích bẫy**:
  - CloudWatch mặc định chỉ đo lường ở mức Hypervisor bên ngoài: `NetworkIn`, `NetworkOut`, `NetworkPacketsIn`, `NetworkPacketsOut`. Các chỉ số này không thể hiện số gói tin bị drop bên trong chip Nitro!
  - Khi microservices gửi hàng triệu request RPC nhỏ, chỉ số `pps_allowance_exceeded` hoặc `conntrack_allowance_exceeded` tăng cao làm chip Nitro âm thầm drop gói tin, buộc TCP phải retransmission nhiều lần gây tăng độ trễ đột biến.
- **Giải pháp tối ưu**:
  - Cài đặt CloudWatch Agent hoặc kịch bản thu thập metric đọc định kỳ từ lệnh `ethtool -S eth0`.
  - Thiết lập CloudWatch Alarm cho các metric:
    - `bw_out_allowance_exceeded > 0`
    - `pps_allowance_exceeded > 0`
    - `conntrack_allowance_exceeded > 0`
  - Tự động kích hoạt thông báo qua Amazon SNS khi có dấu hiệu bóp nghẽn phần cứng.

---

### Bài Toán 10: Tối Thiểu Hóa Thời Gian Hội Tụ BGP Khi Đứt Tuyến Cáp Quang Direct Connect

- **Đề bài thực tế**: Doanh nghiệp có 2 đường cáp quang AWS Direct Connect chạy cơ chế Active/Standby. Khi đường cáp chính bị đứt ngầm vật lý, hệ thống mất từ **90 giây đến 3 phút** để chuyển hoàn toàn lưu lượng sang đường dự phòng, gây gián đoạn dịch vụ nghiêm trọng.
- **Phân tích nguyên nhân**:
  - Mặc định, giao thức BGP sử dụng bộ đếm thời gian: **BGP Keepalive Timer = 30 giây** và **BGP Hold Timer = 90 giây**.
  - Khi cáp quang bị gián đoạn, BGP router phải chờ đủ 90 giây không nhận được gói Keepalive thì mới tuyên bố tuyến đường chết (Dead Route) và bắt đầu tính toán định tuyến lại.
- **Giải pháp tối ưu**:
  - Kích hoạt **Bidirectional Forwarding Detection (BFD)** trên các phiên BGP của AWS Direct Connect và thiết bị định tuyến On-premises.
  - BFD gửi các gói tin thăm dò siêu nhỏ ở tầng liên kết dữ liệu với tần số **300 millisecond** (hỗ trợ phát hiện đứt tuyến chỉ sau 3 lần mất gói, tức là **dưới 1 giây**!).
  - BFD thông báo ngay lập tức cho tiến trình BGP để chuyển đổi luồng traffic sang tuyến đường dự phòng gần như tức thời (Sub-second Failover).
