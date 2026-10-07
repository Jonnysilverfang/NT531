# Đồ án NT531: bốn VPC, so sánh Peering và Transit Gateway

Code giữ môi trường A/B đã import và bổ sung C/D để đo hai cặp đồng thời.
Mạng kết nối đầy đủ dùng 6 Peering hoặc 1 TGW với 4 attachment.
Hạ tầng bốn VPC đã triển khai và cả hai mode đã dùng để đo ngày 05–06/10/2026.
Default trong variables.tf vẫn tắt TGW; mode vận hành phụ thuộc file biến thật
và route AWS tại thời điểm kiểm tra. Repo không lưu file biến cá nhân hoặc state.
Trên GitHub, thiết kế thí nghiệm cũ ở `legacy/pre-four-vpc/terraform/`, dùng state
và topology khác. Không chạy thay thế cho `infra/terraform/` này.

Trình tự bật máy, lấy IP và chuẩn bị công cụ được ghi trong
[hướng dẫn vận hành EC2](../../docs/02-van-hanh-ec2.md).
Phạm vi mới và cách chuyển hai phương án nằm trong
[hướng dẫn bốn VPC](../../docs/03-bon-vpc.md). Sơ đồ ảnh trước đó là bản
tổng quan ban đầu, không phải bằng chứng trạng thái triển khai hiện tại.

## Môi trường

- AWS profile: `nt533-lab`; account: `620306387033`.
- Region: `us-east-1`; cả bốn subnet: `us-east-1a`.
- Terraform: `>= 1.6, < 2.0`; AWS provider: `~> 6.0`, dùng lock file đã commit.
- State local: `infra/terraform/nt531.tfstate`.

| Thành phần | A | B |
|---|---|---|
| VPC CIDR | 10.10.0.0/16 | 10.20.0.0/16 |
| Subnet CIDR | 10.10.10.0/24 | 10.20.10.0/24 |
| EC2 private IP | 10.10.10.212 | 10.20.10.155 |
| EC2 type | c6i.large | c6i.large |
| Root volume | 8 GiB gp3, 3000 IOPS, 125 MiB/s | 8 GiB gp3, 3000 IOPS, 125 MiB/s |

C/D dùng VPC 10.30.0.0/16 và 10.40.0.0/16; private IP 10.30.10.212
và 10.40.10.155, cùng loại máy và disk với A/B.

Luồng đo: EC2 A → bảng A → Peering hoặc TGW theo mode → EC2 B;
có route ngược ở bảng B.
Mỗi subnet được liên kết tường minh với bảng tương ứng. Mỗi VPC có IGW
và route mặc định riêng. IGW không phải đường truyền của bài đo bằng private IP.

## Các file và trách nhiệm

| File | Nội dung |
|---|---|
| `versions.tf` | Provider và backend local |
| `main.tf` | Profile, Region, account guard, default tags và VPC |
| `subnets.tf` | Hai subnet |
| `internet-gateways.tf` | Hai IGW |
| `peering.tf` | Peering A–B |
| `route-tables.tf`, `routes.tf` | Bảng định tuyến và từng route |
| `aws_route_table_association.tf` | Liên kết subnet–bảng định tuyến |
| `security-groups.tf` | Hai Security Group |
| `security-group-rules.tf` | Năm ingress rule và hai egress rule |
| `instances.tf` | Hai EC2 và cấu hình root volume |
| `elastic-ips.tf` | Hai Elastic IP và hai association để giữ địa chỉ SSH |
| `expansion.tf` | VPC, subnet, mạng, EC2, EIP C/D và Peering CD |
| `transit-gateway.tf` | TGW và bốn attachment tùy chọn |
| `full-mesh.tf` | Bốn Peering bổ sung, tám route còn thiếu, ICMP/TCP giữa các máy |
| `variables.tf` | IP được phép SSH |
| `outputs.tf` | Thông tin VPC, EC2 và định tuyến |

`routing_mode` chọn Peering hoặc TGW cho tất cả 12 chiều liên VPC. `enable_transit_gateway`
quyết định có cấp TGW/attachment hay không. Giữ enable=true khi chuyển qua
lại để không xóa rồi tạo lại TGW. Đã có cấu hình full mesh giữa bốn VPC.

## Chạy từ đúng thư mục

Thư mục vận hành hiện tại là `D:\NT531-DanhGiaHieuNang`. Bản sao Git tại
`D:\NT531-GitHub` dùng để lưu code; chưa chuyển state sang đó.

```powershell
cd D:\NT531-DanhGiaHieuNang
aws sts get-caller-identity --profile nt533-lab
terraform '-chdir=infra/terraform' fmt -check
terraform '-chdir=infra/terraform' validate
terraform '-chdir=infra/terraform' plan '-out=reviewed.tfplan'
```

Nếu hết phiên đăng nhập, chạy `aws login --profile nt533-lab` rồi thử lại.
Đọc thay đổi trong plan trước khi áp dụng đúng file vừa lưu:

```powershell
terraform '-chdir=infra/terraform' apply 'reviewed.tfplan'
terraform '-chdir=infra/terraform' plan
terraform '-chdir=infra/terraform' output -json instances
```

Output mới chỉ được lưu vào state sau apply. Output public IP lấy từ
Elastic IP đã gắn vào EC2. Địa chỉ giữ nguyên qua stop/start khi vẫn giữ
allocation; máy stopped vẫn không thể SSH. Sau lần gắn đầu tiên, cập nhật
Address trong Termius sang Elastic IP thay cho public IP tự cấp trước đó.

Bốn Elastic IP có giá niêm yết tổng cộng 0.02 USD/giờ, khoảng 0.48 USD/ngày
hay 14.40 USD/30 ngày, kể cả khi EC2 stopped (chưa tính EC2, EBS, TGW, lưu lượng,
thuế hoặc ưu đãi). Release IP sẽ ngừng giữ địa chỉ; lần cấp sau không bảo
đảm lấy lại IP cũ. Nguồn: [AWS VPC Pricing](https://aws.amazon.com/vpc/pricing/).
EIP chỉ phục vụ truy cập quản trị; bài đo dùng private IP.
EIP không cố định IP mạng nhà bạn. Nếu giới hạn SSH bằng `/32`, cần cập nhật
khi IP nguồn thay đổi; cấu hình demo `0.0.0.0/0` cho phép mọi IPv4 kết nối cổng 22.

## IP quản trị SSH

Bốn rule SSH sử dụng cùng biến `ssh_admin_cidr`, chấp nhận IPv4 `/32` hoặc
`0.0.0.0/0`. Theo yêu cầu demo trên nhiều mạng, hiện chọn `0.0.0.0/0` cho TCP 22.
Đăng nhập vẫn cần khóa SSH; các cổng đo không được mở ra Internet bởi thay đổi này.
Giá trị thật nằm trong `admin.auto.tfvars`, được Git bỏ qua. File
`admin.auto.tfvars.example` có thể commit, nhưng chứa địa chỉ minh họa.
Không ghi đè file biến thật bằng bản mẫu khi đã có cấu hình hợp lệ.

Nếu muốn quay lại giới hạn một IP, lấy IP công cộng từ PowerShell của máy dùng Termius:

```powershell
$labPublicIp = (Invoke-RestMethod 'https://checkip.amazonaws.com' -ErrorAction Stop).Trim()
('ssh_admin_cidr = "{0}/32"' -f $labPublicIp) |
  Set-Content -LiteralPath '.\infra\terraform\admin.auto.tfvars' -Encoding ascii
terraform '-chdir=infra/terraform' plan '-out=ssh-access.tfplan'
```

Chỉ sửa file chưa thay đổi AWS; cần review và apply plan mới.
Các rule ICMP, iperf3 và outbound được quản lý độc lập với SSH.

## State và key pair

- Code mô tả cấu hình; state ánh xạ code với ID tài nguyên thật. Clone Git
  không phục hồi state và không tự nhận diện tài nguyên đang có.
- Giữ bản sao state ở nơi riêng được bảo vệ, ngoài repo. Không commit state,
  plan, `.terraform/`, `admin.auto.tfvars` hoặc private key `.pem`.
- `nt531-key` hiện là key pair có sẵn được tham chiếu bằng tên, chưa được
  resource Terraform quản lý. Máy mới cần key pair này tồn tại trong Region.
- Không đưa nội dung private key vào Terraform. Nếu bổ sung quản lý key pair,
  sử dụng public key; người đăng nhập giữ private key riêng.
- `prevent_destroy = true` ở EC2 chặn kế hoạch xóa/thay thế khi còn khai báo
  này. Nó không thay thế bản sao lưu và không bảo vệ khỏi thao tác xóa qua Console.

## Phụ thuộc khi dựng lại và phạm vi đã kiểm chứng

1. Chốt cơ chế key pair: phụ thuộc bên ngoài hay quản lý public key bằng Terraform.
2. SSH qua bốn Elastic IP đã được dùng trong các phiên đo. Subnet giữ
   `map_public_ip_on_launch = false`; EIP được gắn riêng bằng association.
   Chưa kiểm chứng dựng lại toàn bộ từ tài khoản trống và state trống.
3. Chuẩn bị công cụ và MTU bằng các script Initialize-Experiment hoặc
   Initialize-ExperimentSSM trong `scripts/`. Terraform không tự chạy chúng
   trên các EC2 đã import; cần kiểm tra MTU lại sau reboot.
4. C/D và TGW đã triển khai, connectivity và sáu bộ benchmark chính đã có
   bằng chứng. Chuyển route bằng Terraform không nguyên tử; chưa phải kịch bản
   di chuyển không gián đoạn đã được kiểm chứng. Các bài đo bổ sung vẫn ở kế hoạch.

## Kiểm tra offline

Với Terraform >= 1.7, chạy `terraform '-chdir=infra/terraform' test`.
Các test dùng mock AWS để kiểm tra hai chế độ route và cấu hình TGW sai;
không tạo tài nguyên thật và không chứng minh đường truyền hoạt động.

`No changes` chỉ xác nhận tài nguyên đã khai báo khớp sau refresh, không xác
nhận ping/iperf3 hoạt động hay toàn đồ án hoàn tất. Sau thay đổi kết nối,
cần kiểm tra đường truyền khi chủ động bật EC2 để đo.
