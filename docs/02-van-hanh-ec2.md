# Vận hành môi trường thực nghiệm của đồ án NT531

## Trình tự hiện tại

1. Review và áp dụng thay đổi SSH cùng Elastic IP bằng Terraform.
2. Khi sẵn sàng kiểm tra, bật hai EC2 đang có, đợi status checks đạt.
3. Lấy public IP hiện tại, kết nối Termius và chuẩn bị công cụ đo.
4. Kiểm tra ping hai chiều, đo thử TCP qua private IP.
5. Lưu bằng chứng và cấu hình trước khi triển khai phương án Transit Gateway.

Không cần đợi toàn bộ đồ án hoàn thành mới đăng nhập EC2. Kiểm tra từng
giai đoạn giúp biết lỗi đến từ cấu hình mạng hay công cụ đo.

## Bước 1: cấu hình SSH

Từ PowerShell ở `D:\NT531-DanhGiaHieuNang`:

```powershell
terraform '-chdir=infra/terraform' plan '-out=ec2-access.tfplan'
```

Với thay đổi hiện tại, dự kiến tạo hai EIP và hai association; hai rule SSH
chuyển sang IP `/32` trong `admin.auto.tfvars` nếu chưa apply, cùng các
output mới. Không dự kiến tạo lại EC2. Xem toàn bộ plan;
nếu đúng phạm vi, áp dụng đúng file vừa tạo:

```powershell
terraform '-chdir=infra/terraform' apply 'ec2-access.tfplan'
```

## Bước 2: bật máy và lấy địa chỉ

Trong EC2 Console, Region `us-east-1`, chọn `nt531-ec2-a` và `nt531-ec2-b`,
dùng **Start instance**. Đây là bật lại máy đã có, không phải tạo thêm máy.
Đợi máy running và status checks đạt rồi chạy:

```powershell
.\scripts\Get-ExperimentInstances.ps1 | Format-Table -AutoSize
```

Script chỉ đọc state để lấy ID và hỏi AWS lấy trạng thái/IP hiện tại;
không bật, tắt hoặc thay đổi tài nguyên. Nếu phiên AWS hết hạn, chạy
`aws login --profile nt533-lab` rồi thử lại.

Cập nhật Address trong hai host Termius theo cột PublicIP; username
`ec2-user`, port `22`, key `nt531-key`. Nếu không có public IP sau khi
máy running, cần kiểm tra cấu hình địa chỉ mạng trước khi SSH.

Sau khi gắn Elastic IP, địa chỉ giữ nguyên khi stop/start miễn là vẫn giữ
allocation. Lần gắn đầu tiên thay địa chỉ public tự cấp trước đó, cần sửa
Address trong Termius. EIP vẫn tính phí khi stopped; máy phải running mới
SSH được. [Tài liệu EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html).
Địa chỉ public dùng quản trị; bài đo giữa hai máy dùng private IP.
SSH còn phụ thuộc IP nguồn trong `ssh_admin_cidr`: khi đổi mạng/VPN, cần
cập nhật biến và apply dù Elastic IP của EC2 không đổi.

## Bước 3: chuẩn bị công cụ

Dùng SFTP của Termius chép `scripts/prepare-measurement.sh` vào
`/home/ec2-user/` trên cả A và B. Trong terminal của mỗi máy chạy:

```bash
bash ~/prepare-measurement.sh
```

Script cài các công cụ còn thiếu (`iperf3`, `sysstat`, `jq`) và lưu một
bản ghi môi trường có thời gian trong `~/nt531-results`. Script không
đổi MTU, không tự chạy tải và không ghi đè kết quả cũ. Các phiên bản đã
cài được giữ lại; cần so sánh phiên bản hai máy trước khi đo chính thức.

Đây là chuẩn bị máy hiện có qua SSH, chưa phải bootstrap tự động khi tạo
EC2 mới. User data mặc định chạy lúc khởi tạo lần đầu; thêm vào máy đã
import không bảo đảm chạy lại:
[tài liệu user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html).

## Bước 4: kiểm tra kết nối

Trên A: `ping -c 5 10.20.10.155`.
Trên B: `ping -c 5 10.10.10.212`.

SG hiện cho TCP 5201 từ A tới B, vì vậy dùng B làm iperf3 server.
Chưa chạy nhiều bài đồng thời. Xác nhận MTU hiện tại trong snapshot,
không suy ra MTU từ lần đo trước. Cần thống nhất thời gian, số lần lặp,
chiều truyền và MTU trước đợt thu thập số liệu chính thức.
