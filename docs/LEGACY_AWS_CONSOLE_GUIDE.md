# HƯỚNG DẪN TRIỂN KHAI CHI TIẾT TRÊN GIAO DIỆN AWS CONSOLE

> **Legacy Mode A architecture guide — not an active Mode B deployment procedure.** It contains the former PrivateLink/placement-group design. Use Terraform plus `scripts/aws_controller.ps1` for the registered three-test experiment.

## REGION: N. VIRGINIA (`us-east-1`)

Tài liệu này hướng dẫn chi tiết từng cú nhấp chuột (click-by-click) trên giao diện đồ họa **AWS Management Console** tại Region **N. Virginia (`us-east-1`)** để thiết lập toàn bộ môi trường thực nghiệm đánh giá hiệu năng mạng đa kiến trúc.

---

## BƯỚC 1: XÁC THỰC VÀ CHUYỂN VÙNG VỀ N. VIRGINIA

1. Đăng nhập vào **AWS Management Console**.
2. Nhìn lên thanh điều hướng trên cùng (top navigation bar), góc bên phải cạnh tên tài khoản của bạn:
   - Nhấp vào menu đổ xuống chọn **Region**.
   - Tìm và chọn **Asia Pacific (N. Virginia) `us-east-1`**.
   - *Kiểm tra*: Đảm bảo thanh địa chỉ hiển thị mã vùng `us-east-1` trên URL (ví dụ: `https://us-east-1.console.aws.amazon.com/...`).

---

## BƯỚC 2: TẠO HẠ TẦNG 3 VPC THỰC NGHIỆM

### 2.1. Tạo VPC A (Client VPC - `10.1.0.0/16`)
1. Trên ô tìm kiếm trên cùng, gõ **VPC** và chọn dịch vụ **VPC**.
2. Ở thanh menu điều hướng bên trái (left sidebar), chọn **Your VPCs**.
3. Nhấp vào nút màu cam **Create VPC** (góc trên bên phải).
4. Trong form cấu hình VPC:
   - Mục **Resources to create**: Chọn radio button **VPC only**.
   - Trường **Name tag**: Nhập `VPC-A-Client`.
   - Trường **IPv4 CIDR block**: Chọn radio button **IPv4 CIDR manual input**.
   - Trường **IPv4 CIDR**: Nhập `10.1.0.0/16`.
   - Trường **Tenancy**: Giữ nguyên `Default`.
5. Nhấp nút màu cam **Create VPC** ở góc dưới cùng bên phải.

### 2.2. Tạo 2 Subnet cho VPC A
1. Tại menu bên trái, chọn mục **Subnets** -> Nhấp nút màu cam **Create subnet**.
2. Trường **VPC ID**: Chọn `VPC-A-Client` từ danh sách đổ xuống.
3. **Cấu hình Subnet 1 (AZ-a)**:
   - **Subnet name**: Nhập `Subnet-A1-AZ-a`.
   - **Availability Zone**: Chọn **us-east-1a**.
   - **IPv4 subnet CIDR block**: Nhập `10.1.1.0/24`.
4. Nhấp nút **Add new subnet** phía dưới để thêm Subnet 2:
   - **Subnet name**: Nhập `Subnet-A2-AZ-b`.
   - **Availability Zone**: Chọn **us-east-1b**.
   - **IPv4 subnet CIDR block**: Nhập `10.1.2.0/24`.
5. Nhấp nút màu cam **Create subnet**.

---

### 2.3. Tạo VPC B (Target Server VPC - `10.2.0.0/16`)
1. Quay lại **Your VPCs** -> Nhấp **Create VPC**:
   - **Resources to create**: **VPC only**.
   - **Name tag**: Nhập `VPC-B-Target`.
   - **IPv4 CIDR**: Nhập `10.2.0.0/16`.
2. Nhấp nút màu cam **Create VPC**.

### 2.4. Tạo 2 Subnet cho VPC B
1. Vào **Subnets** -> Nhấp **Create subnet**:
   - **VPC ID**: Chọn `VPC-B-Target`.
   - **Subnet 1**:
     - **Subnet name**: `Subnet-B1-AZ-a`.
     - **Availability Zone**: **us-east-1a**.
     - **IPv4 subnet CIDR block**: `10.2.1.0/24`.
   - Nhấp **Add new subnet**:
     - **Subnet name**: `Subnet-B2-AZ-b`.
     - **Availability Zone**: **us-east-1b**.
     - **IPv4 subnet CIDR block**: `10.2.2.0/24`.
2. Nhấp nút màu cam **Create subnet**.

---

### 2.5. Tạo VPC Shared (PrivateLink Provider VPC - `10.3.0.0/16`)
1. Vào **Your VPCs** -> Nhấp **Create VPC**:
   - **Resources to create**: **VPC only**.
   - **Name tag**: Nhập `VPC-Shared-Provider`.
   - **IPv4 CIDR**: Nhập `10.3.0.0/16`.
2. Nhấp **Create VPC**.
3. Tạo 1 Subnet cho VPC Shared:
   - **VPC ID**: Chọn `VPC-Shared-Provider`.
   - **Subnet name**: `Subnet-Shared-AZ-a`.
   - **Availability Zone**: **us-east-1a**.
   - **IPv4 CIDR block**: `10.3.1.0/24`.
4. Nhấp **Create subnet**.

---

## BƯỚC 3: CẤU HÌNH INTERNET GATEWAY & QUẢN TRỊ TỪ XA (SSM / BASTION)

Để tiện truy cập dòng lệnh vào các máy EC2 mà không cần mở IP public (tiết kiệm chi phí và tăng bảo mật):
1. Tại VPC Console, menu bên trái chọn **Internet Gateways** -> Nhấp **Create internet gateway**.
   - **Name tag**: `IGW-Lab-Performance`.
   - Nhấp **Create internet gateway**.
2. Nhấp nút **Actions** (góc trên bên phải) -> Chọn **Attach to VPC** -> Chọn `VPC-A-Client` -> Nhấp **Attach internet gateway**.
3. Cập nhật Route Table của Subnet-A1:
   - Tại menu bên trái, chọn **Route tables** -> Tìm route table gắn với VPC-A.
   - Nhấp tab **Routes** ở nửa dưới màn hình -> Nhấp **Edit routes**.
   - Nhấp nút **Add route**:
     - **Destination**: `0.0.0.0/0`.
     - **Target**: Chọn **Internet Gateway** -> Chọn `IGW-Lab-Performance`.
   - Nhấp nút màu xanh/cam **Save changes**.

---

## BƯỚC 4: THIẾT LẬP ĐƯỜNG TRUYỀN 1 - VPC PEERING (VPC A <-> VPC B)

1. Tại menu bên trái của VPC Console, cuộn xuống mục **Virtual private cloud (VPC)** -> Chọn **Peering connections**.
2. Nhấp nút màu cam **Create peering connection**:
   - **Name**: Nhập `Peering-VPC-A-to-VPC-B`.
   - **VPC ID (Requester)**: Chọn `VPC-A-Client`.
   - **Select another VPC to peer with**:
     - **Account**: Chọn radio button **My account**.
     - **Region**: Chọn radio button **This region (us-east-1)**.
   - **VPC ID (Accepter)**: Chọn `VPC-B-Target`.
3. Nhấp nút màu cam **Create peering connection**.
4. Chấp nhận kết nối Peering:
   - Chọn bản ghi `Peering-VPC-A-to-VPC-B` vừa tạo (đang ở trạng thái *Pending acceptance*).
   - Nhấp nút **Actions** -> Chọn **Accept request**.
   - Trong modal xác nhận, nhấp **Accept request**. Trạng thái chuyển sang màu xanh lá cây (*Active*).
5. **Cấu hình Định tuyến (Route Tables) cho Peering**:
   - Vào **Route tables** -> Chọn route table của `VPC-A-Client` -> Tab **Routes** -> **Edit routes**:
     - **Add route**: Destination = `10.2.0.0/16`, Target = Chọn **Peering Connection** -> `Peering-VPC-A-to-VPC-B`.
     - Nhấp **Save changes**.
   - Chọn route table của `VPC-B-Target` -> Tab **Routes** -> **Edit routes**:
     - **Add route**: Destination = `10.1.0.0/16`, Target = Chọn **Peering Connection** -> `Peering-VPC-A-to-VPC-B`.
     - Nhấp **Save changes**.

---

## BƯỚC 5: THIẾT LẬP ĐƯỜNG TRUYỀN 2 - AWS TRANSIT GATEWAY (TGW)

1. Tại VPC Console, menu bên trái cuộn xuống mục **Transit gateways** -> Chọn **Transit gateways**.
2. Nhấp nút màu cam **Create transit gateway**:
   - **Name tag**: Nhập `TGW-Performance-Lab`.
   - **Amazon side Autonomous System Number (ASN)**: Giữ mặc định `64512`.
   - **DNS support**: Tích chọn (Checked).
   - **VPN ECMP support**: Tích chọn (Checked).
   - **Default route table association**: **Enable** (Checked).
   - **Default route table propagation**: **Enable** (Checked).
3. Nhấp nút màu cam **Create transit gateway**. (Chờ khoảng 1-2 phút để chuyển sang trạng thái *Available*).

4. **Tạo Transit Gateway Attachment cho VPC A**:
   - Tại menu bên trái, chọn **Transit gateway attachments** -> Nhấp **Create transit gateway attachment**:
     - **Transit gateway ID**: Chọn `TGW-Performance-Lab`.
     - **Attachment type**: Chọn radio button **VPC**.
     - **Attachment name tag**: Nhập `TGW-Attach-VPC-A`.
     - **VPC ID**: Chọn `VPC-A-Client`.
     - **Subnet IDs**: Chọn cả 2 subnets `Subnet-A1-AZ-a` và `Subnet-A2-AZ-b`.
   - Nhấp **Create transit gateway attachment**.

5. **Tạo Transit Gateway Attachment cho VPC B**:
   - Nhấp tiếp **Create transit gateway attachment**:
     - **Transit gateway ID**: Chọn `TGW-Performance-Lab`.
     - **Attachment type**: **VPC**.
     - **Attachment name tag**: Nhập `TGW-Attach-VPC-B`.
     - **VPC ID**: Chọn `VPC-B-Target`.
     - **Subnet IDs**: Chọn cả 2 subnets `Subnet-B1-AZ-a` và `Subnet-B2-AZ-b`.
   - Nhấp **Create transit gateway attachment**.

6. **Cập nhật Route Table để kiểm thử qua TGW**:
   - Khi muốn đo đạc qua TGW, route table của VPC A sẽ trỏ tới TGW attachment thay vì Peering (được tự động chuyển đổi qua file cấu hình hoặc script).

---

## BƯỚC 6: THIẾT LẬP ĐƯỜNG TRUYỀN 3 - AWS PRIVATELINK (VPC ENDPOINT SERVICE)

### 6.1. Tạo Network Load Balancer (NLB) trong VPC Shared
1. Trên ô tìm kiếm, gõ **EC2** -> Chọn **Load Balancers** (ở menu bên trái dưới mục Load Balancing).
2. Nhấp nút màu cam **Create load balancer**.
3. Tại ô **Network Load Balancer**, nhấp nút **Create**:
   - **Load balancer name**: `NLB-PrivateLink-Benchmark`.
   - **Scheme**: Chọn radio button **Internal** (cực kỳ quan trọng!).
   - **IP address type**: **IPv4**.
   - **VPC**: Chọn `VPC-Shared-Provider`.
   - **Mappings**: Tích chọn Availability Zone **us-east-1a** và chọn subnet `Subnet-Shared-AZ-a`.
4. **Listeners and routing**:
   - **Protocol**: Chọn **TCP**, **Port**: `5201` (Cổng mặc định của iperf3).
   - Tạo Target Group: Nhấp liên kết **Create target group**:
     - **Target type**: **IP addresses** (hoặc Instances).
     - **Target group name**: `TG-iperf3-5201`.
     - **Protocol**: **TCP**, **Port**: `5201`.
     - **VPC**: Chọn `VPC-Shared-Provider`.
     - Nhấp **Next** -> Nhập IP hoặc chọn EC2 iperf3 server của VPC Shared -> Nhấp **Include as pending below** -> **Create target group**.
5. Quay lại tab tạo NLB, chọn target group `TG-iperf3-5201` vừa tạo.
6. Nhấp nút màu cam **Create load balancer**.

### 6.2. Tạo Endpoint Service (PrivateLink)
1. Quay lại dịch vụ **VPC** Console.
2. Tại menu bên trái, chọn **Endpoint services** -> Nhấp **Create endpoint service**:
   - **Name**: `Service-iperf3-Benchmark`.
   - **Load balancer type**: Chọn **Network**.
   - **Available load balancers**: Chọn `NLB-PrivateLink-Benchmark`.
   - **Require acceptance for endpoint**: Bỏ tích (Uncheck để tự động chấp thuận kết nối).
3. Nhấp **Create**. Sau khi tạo xong, sao chép giá trị **Service name** (dạng `com.amazonaws.vpce.us-east-1.vpce-svc-xxxxxxxxxxxxxxxxx`).

### 6.3. Tạo Interface VPC Endpoint trong VPC A
1. Tại menu bên trái của VPC Console, chọn **Endpoints** -> Nhấp **Create endpoint**:
   - **Name**: `VPCE-Client-to-iperf3`.
   - **Service category**: Chọn radio button **Other endpoint services**.
   - **Service name**: Dán chuỗi Service name vừa sao chép ở trên vào -> Nhấp nút **Verify service**. (Hiện dòng chữ màu xanh lá cây xác thực thành công).
   - **VPC**: Chọn `VPC-A-Client`.
   - **Subnets**: Chọn Availability Zone **us-east-1a** và subnet `Subnet-A1-AZ-a`.
   - **Security groups**: Chọn security group cho phép port 5201 inbound.
2. Nhấp nút màu cam **Create endpoint**. Lúc này endpoint sẽ nhận được một địa chỉ IP nội bộ thuộc dải `10.1.1.0/24`.

---

## BƯỚC 7: TẠO CLUSTER PLACEMENT GROUP & KHỞI TẠO EC2 INSTANCES

### 7.1. Tạo Cluster Placement Group
1. Vào dịch vụ **EC2 Console** tại N. Virginia (`us-east-1`).
2. Tại menu bên trái, cuộn xuống mục **Network & Security** -> Chọn **Placement Groups**.
3. Nhấp nút màu cam **Create placement group**:
   - **Name**: `PG-Cluster-LowLatency`.
   - **Placement strategy**: Chọn radio button **Cluster**.
4. Nhấp **Create group**.

### 7.2. Khởi tạo EC2 Client (VPC A) & EC2 Target (VPC B)
1. Vào mục **Instances** -> Nhấp nút màu cam **Launch instances**:
2. **Cấu hình chung**:
   - **Name**: `EC2-Client-VPC-A`.
   - **AMI**: Chọn **Amazon Linux 2023 AMI** (mặc định hỗ trợ driver ENA mới nhất).
   - **Instance type**: Chọn **c6i.large** (hoặc `c5n.large` nếu cần test tốc độ 25 Gbps, hoặc `t3.medium` cho bài test tối ưu chi phí).
3. **Network settings** (Nhấp nút **Edit**):
   - **VPC**: Chọn `VPC-A-Client`.
   - **Subnet**: Chọn `Subnet-A1-AZ-a`.
   - **Auto-assign public IP**: **Enable** (để dễ dàng SSH/SSM).
   - **Security group**: Tạo mới hoặc chọn SG cho phép Inbound:
     - `SSH (22)` từ IP của bạn.
     - `All Traffic` hoặc `TCP 5201`, `UDP 50000-53000`, `ICMP` từ dải `10.0.0.0/8`.
4. **Advanced network configuration**:
   - Mở rộng mục **Advanced details**:
     - **Placement group**: Tích chọn **Add instance to placement group** -> Chọn `PG-Cluster-LowLatency`.
5. **User Data script** (dán vào ô User data để tự động cài đặt công cụ đo):
```bash
#!/bin/bash
dnf update -y
dnf install -y iperf3 ethtool git gcc make bmon jq
# Cài đặt sockperf phục vụ đo độ trễ micro-second
cd /tmp
git clone https://github.com/Mellanox/sockperf.git
cd sockperf
./autogen.sh
./configure --enable-test
make -j$(nproc)
make install
```
6. Nhấp nút màu cam **Launch instance**.
7. Lặp lại thao tác trên để tạo `EC2-Target-VPC-B` (đặt trong `VPC-B-Target`, subnet `Subnet-B1-AZ-a`).

---

## BƯỚC 8: KIỂM TRA & XÁC NHẬN SẴN SÀNG

1. SSH vào `EC2-Client-VPC-A` và `EC2-Target-VPC-B`.
2. Kiểm tra driver ENA trên cả 2 máy:
   ```bash
   modinfo ena
   ethtool -i eth0
   ```
3. Kiểm tra MTU hiện tại:
   ```bash
   ip link show eth0
   # Mặc định Amazon Linux trên AWS VPC là mtu 9001 (Jumbo Frame)
   ```
4. Kiểm tra các bộ đếm ENA trước khi đo:
   ```bash
   ethtool -S eth0 | grep allowance
   ```
5. Môi trường đã sẵn sàng 100% để thực thi các kịch bản đo đạc tự động!
