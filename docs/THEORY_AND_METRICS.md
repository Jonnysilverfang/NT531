# CƠ SỞ LÝ THUYẾT & CHỈ SỐ ĐÁNH GIÁ HIỆU NĂNG MẠNG AWS

Tài liệu này cung cấp nền tảng lý thuyết chuyên sâu về kiến trúc mạng đám mây của AWS, cơ chế ảo hóa phần cứng AWS Nitro System, các chỉ số đo lường hiệu năng mạng và phân tích các bẫy câu hỏi trong các kỳ thi AWS Certified Advanced Networking - Specialty (ANS-C01) và AWS Certified DevOps Engineer - Professional (DOP-C02).

---

## 1. Cơ Chế Ảo Hóa Mạng AWS Nitro System & Enhanced Networking (ENA)

### 1.1. Sự phát triển từ PV (Paravirtual) sang SR-IOV & ENA
- **Thời kỳ Xen Hypervisor truyền thống**: Mọi thao tác I/O mạng từ máy ảo (DomU) đều phải thông qua Domain 0 (Dom0) của Hypervisor để chuyển tiếp tới card mạng vật lý. Điều này gây ra độ trễ cao, jitter lớn và tiêu tốn CPU của host để xử lý ngắt gói tin.
- **Enhanced Networking với SR-IOV (Single Root I/O Virtualization)**:
  - Cho phép phân chia một card mạng vật lý (PCIe physical function) thành nhiều card mạng ảo độc lập (**Virtual Functions - VF**).
  - EC2 instance truy cập trực tiếp vào phần cứng VF mà không cần qua Hypervisor trung gian, giảm đáng kể độ trễ và tăng gói tin trên giây (Packets Per Second - PPS).
- **AWS Elastic Network Adapter (ENA)**:
  - Được AWS thiết kế riêng cho kiến trúc phần cứng **AWS Nitro Card for Networking**.
  - Hỗ trợ đa hàng đợi phần cứng (Multi-queue), Receive Side Scaling (RSS), Checksum offload, TSO (TCP Segmentation Offload), và băng thông lên đến 100 Gbps - 400 Gbps (trên các họ `c5n`, `c6in`, `p4de`).

### 1.2. Cơ Chế Quản Lý Hạn Mức Mạng (Network Allowance & Throttling)
Mỗi kích thước máy chủ EC2 (Instance Type & Size) đều được AWS ấn định một mức trần hiệu năng mạng:
- **Baseline Bandwidth** (Băng thông cơ sở) vs **Burst Bandwidth** (Băng thông bùng nổ theo cơ chế I/O credits).
- **Packets Per Second (PPS) Allowance**: Giới hạn số lượng gói tin xử lý mỗi giây (thường nghẽn khi truyền nhiều gói tin nhỏ như DNS, microservices RPC).
- **Connection Tracking (Conntrack) Allowance**: Giới hạn số phiên kết nối đồng thời được ghi nhận bởi Security Group (stateful tracking). Khi vượt quá giới hạn này, các gói tin của kết nối mới sẽ bị drop âm thầm.

### 1.3. Các Chỉ Số Thanh Ghi Phần Cứng ENA (ENA Driver Metrics)
Trên hệ điều hành Linux (Amazon Linux 2 / 2023, Ubuntu), ta có thể đọc trực tiếp các thanh ghi phần cứng Nitro bằng lệnh:
```bash
ethtool -S eth0 | grep allowance
```

Bảng ý nghĩa các thanh ghi quan trọng:
| Thanh Ghi (Counter) | Ý nghĩa kỹ thuật | Biểu hiện & Hậu quả |
| :--- | :--- | :--- |
| `bw_in_allowance_exceeded` | Lưu lượng Inbound vượt quá giới hạn băng thông phân bổ cho instance type. | Gói tin đến bị drop tại Nitro Card, TCP throughput suy giảm đột ngột. |
| `bw_out_allowance_exceeded` | Lưu lượng Outbound vượt quá giới hạn băng thông phân bổ. | Gói tin đi bị Nitro Card bóp nghẽn (throttling), tăng thời gian xếp hàng. |
| `pps_allowance_exceeded` | Số lượng gói tin trên giây (PPS) vượt trần quy định của instance. | Rớt gói tin khi ứng dụng gửi quá nhiều gói tin kích thước nhỏ. |
| `conntrack_allowance_exceeded` | Số lượng phiên TCP/UDP tracking của Security Group vượt giới hạn phần cứng Nitro. | Kết nối mới bị từ chối (Connection Refused / Timeout), không thể mở thêm session. |
| `linklocal_allowance_exceeded` | Vượt quá hạn mức gửi tới các dịch vụ link-local nội bộ (như DNS Resolver `169.254.169.253`, Metadata `169.254.169.254`). | Lỗi phân giải tên miền DNS hoặc lỗi lấy credentials IAM Role. |

---

## 2. Kích Thước Gói Tin: MTU 1500 vs Jumbo Frames MTU 9001

### 2.1. Maximum Transmission Unit (MTU) là gì?
MTU là kích thước gói tin lớn nhất (tính bằng bytes) mà một giao diện mạng có thể truyền tải mà không cần phải phân mảnh (fragmentation).
- **Standard Ethernet MTU**: `1500 bytes` (chuẩn toàn cầu trên mạng Internet).
- **Jumbo Frames**: `9001 bytes` (được AWS hỗ trợ nguyên bản trong nội bộ VPC).

### 2.2. Cơ Chế Giảm Tải Cho CPU & Tối Ưu Băng Thông
Giả sử cần truyền tải một tệp dữ liệu dung lượng **1 GB** qua kết nối TCP:
- **Với MTU 1500**: Cần truyền khoảng **~700,000 gói tin**. CPU của cả máy gửi và máy nhận phải xử lý 700,000 lần ngắt phần cứng (Hardware Interrupt / SoftIRQ) và xử lý header IP/TCP.
- **Với MTU 9001**: Chỉ cần truyền khoảng **~115,000 gói tin** (giảm tới **83%** số lượng gói tin!).
- *Giả thuyết cần kiểm chứng*: Jumbo Frames có thể giảm số packet cho cùng lượng payload và nhờ đó giảm chi phí xử lý mỗi byte. Mức cải thiện CPU/throughput phụ thuộc workload, offload, MTU end-to-end và phải được đo ở Mode B.

> [!WARNING]
> **Bẫy thi cử ANS-C01 & Quy tắc định tuyến AWS:**
> - MTU 9001 (Jumbo Frames) được hỗ trợ đầy đủ trong nội bộ một VPC, giữa các VPC qua **VPC Peering**, hoặc qua **Direct Connect (Private VIF hỗ trợ MTU 9001; Transit VIF hỗ trợ MTU 8500)** và **Transit Gateway (hỗ trợ MTU lên tới 8500)**.
> - Khi lưu lượng đi ra **Internet Gateway (IGW)**, MTU bắt buộc bị giới hạn ở mức chuẩn **1500 bytes**.
> - Với **AWS Site-to-Site VPN**, đường hầm IPsec tiêu chuẩn giới hạn MTU ở mức ~1400 - 1446 bytes do trừ hao encapsulation overhead (trừ khi sử dụng giải pháp nâng cao với Large Bandwidth VPN tunnels lên tới 5 Gbps cho AWS Transit Gateway / Cloud WAN).
> - Nếu gửi gói tin MTU 9001 với cờ `DF` (Don't Fragment) ra ngoài internet, gói tin sẽ bị drop (Path MTU Discovery - PMTUD failure) nếu ICMP Type 3 Code 4 (Fragmentation Needed) bị chặn bởi Security Group / NACL!

---

## 3. Cơ Chế Vị Trí Vật Lý: Cluster Placement Groups

AWS Data Center được tổ chức theo cấu trúc phân tầng vật lý: **Regions -> Availability Zones -> Data Center Facilities -> Network Spine-Leaf Fabric -> Server Racks -> Physical Hosts**.
- Mặc định, các EC2 instance được AWS tự động phân tán ngẫu nhiên trên các phần cứng khác nhau để tối đa hóa tính sẵn sàng và khả năng chịu lỗi (Fault Tolerance).
- **Cluster Placement Group**:
  - AWS gom các EC2 instance được chỉ định vào **cùng một Availability Zone và cùng một phân vùng mạng có băng thông lưỡng phân cao (high-bisection-bandwidth network fabric segment)**.
  - *Lưu ý kỹ thuật chính thức từ AWS*: Cluster Placement Group giúp rút ngắn khoảng cách cáp quang và tối ưu hóa chuyển mạch giữa các máy chủ, nhưng **không cam kết các máy chủ nằm trên cùng một rack vật lý đơn lẻ**.
  - Cho phép đạt độ trễ mạng thấp nhất (**Sub-millisecond RTT < 100 - 200 microsecond**) và khai thác tối đa băng thông 100 Gbps single-flow trên các dòng máy chủ chuyên dụng (HPC, Machine Learning, Financial Trading).

---

## 4. Phân Tích So Sánh Chuyên Sâu: Peering vs Transit Gateway vs PrivateLink

| Đặc tính Kỹ thuật | VPC Peering | AWS Transit Gateway (TGW) | AWS PrivateLink (VPC Endpoint Service) |
| :--- | :--- | :--- | :--- |
| **Mô hình kiến trúc** | Điểm - Điểm (Point-to-Point Mesh) | Hub-and-Spoke tập trung | Client - Server (Dịch vụ một chiều) |
| **Tầng hoạt động (OSI)** | Layer 3 (IP Routing) | Layer 3 (IP Routing) | Layer 4 (TCP/TLS qua NLB) |
| **Băng thông tối đa** | **Không giới hạn** (Bằng tốc độ vật lý của EC2 ENA) | Băng thông cơ sở **50 Gbps** / attachment / AZ, có thể burst lên đến **100 Gbps** | **Không giới hạn** (Tự động scale theo NLB IP) |
| **Độ trễ trung bình (RTT)** | **Thấp nhất** (~0.1ms - 0.2ms Same-AZ) | **Trung bình** (~0.8ms - 1.2ms, thêm 1 hop TGW) | **Thấp - Trung bình** (~0.5ms qua Proxy NLB) |
| **Hỗ trợ Overlapping CIDR** | **KHÔNG** (Chặn hoàn toàn nếu trùng IP) | **KHÔNG** (Trừ khi dùng phức tạp NAT/VRF) | **CÓ** (Hoàn toàn miễn nhiễm trùng IP) |
| **Định tuyến bắc cầu (Transitive)**| **KHÔNG** (A-B và B-C thì A không thấy C) | **CÓ** (Quản lý qua TGW Route Tables) | Không áp dụng (Mô hình dịch vụ đóng) |
| **Bảo mật & Kiểm soát** | Security Group & NACL 2 chiều | TGW Route Table segmentation | Endpoint Policy + IAM + SG một chiều |
| **Chi phí cố định** | **$0.00** (Hoàn toàn miễn phí) | ~$36/tháng/attachment (~$0.05/giờ) | ~$7.2/tháng/endpoint (~$0.01/giờ) |
| **Chi phí dữ liệu (Data Transfer)**| **$0.00 / GB** (trong cùng 1 AZ) | **$0.02 / GB** dữ liệu xử lý | **$0.01 / GB** dữ liệu xử lý |

---

## 5. Bẫy Thi Cử Cốt Lõi trong ANS-C01 & DOP-C02 Liên Quan Đến Đề Tài

1. **Bẫy Asymmetric Routing qua Stateful Firewall trên Transit Gateway**:
   - Khi luồng traffic đi giữa các AZ qua TGW tới một Inspection VPC chứa tường lửa stateful, TGW mặc định dùng thuật toán băm có thể gửi chiều về qua AZ khác -> Firewall drop gói tin vì chưa thấy SYN!
   - *Khắc phục*: Bắt buộc phải kích hoạt **Transit Gateway Appliance Mode** trên VPC attachment của Inspection/Shared VPC (Câu hỏi 211, 212 ANS-C01).
2. **Bẫy NAT Gateway Idle Connection Timeout (350 giây)**:
   - Các kết nối nhàn rỗi quá 350s (như long-running database query) bị NAT Gateway đóng phiên, làm tăng chỉ số `IdleTimeoutCount`.
   - *Khắc phục*: Bật **TCP keepalive** trên máy trạm với chu kỳ `< 300 giây` (Câu hỏi 227, 269 ANS-C01).
3. **Bẫy Băng Thông VPN vs Transit Gateway Connect**:
   - Kết nối Site-to-Site VPN tiêu chuẩn chỉ đạt tối đa **1.25 Gbps** mỗi tunnel.
   - Để đạt băng thông lớn hơn (5 Gbps - 20 Gbps) tới các thiết bị SD-WAN ảo, bắt buộc phải dùng **Transit Gateway Connect Attachment** chạy trên giao thức GRE (Câu hỏi 206 ANS-C01).
4. **Bẫy Chi Phí Dữ liệu Liên VPC (Lowest Cost)**:
   - Khi truyền hàng chục TB dữ liệu giữa các VPC trong cùng 1 Region, **VPC Peering kết hợp Zonal DNS Name** của NLB mang lại chi phí $0.00 data transfer (Same-AZ), rẻ hơn rất nhiều so với Transit Gateway ($0.02/GB) hoặc PrivateLink ($0.01/GB) (Câu hỏi 210 ANS-C01).
