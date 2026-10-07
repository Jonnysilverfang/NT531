# Quản trị EC2 bằng Systems Manager

SSH cần đường TCP 22 từ máy cá nhân và đúng IP nguồn trong Security Group.
SSM Agent trên EC2 chủ động kết nối tới dịch vụ AWS để nhận lệnh quản trị.
Đường đo vẫn dùng private IP qua Peering/TGW; SSM không thay thế đường đo.

`management.tf` gồm role cho dịch vụ EC2, policy `AmazonSSMManagedInstanceCore`
và instance profile đưa role vào bốn máy. Role này không phải Administrator.
Người vận hành vẫn cần quyền IAM dùng Session Manager/Run Command. Agent phải
hoạt động và có outbound tới endpoint SSM; gắn role chưa chứng minh kết nối thành công.

Nguồn: [AWS — quyền instance cho Systems Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-instance-permissions.html).

## Chuẩn bị sau khi apply

Chạy PowerShell tại thư mục dự án:

```powershell
aws ssm describe-instance-information --profile nt533-lab --region us-east-1 --query 'InstanceInformationList[].{ID:InstanceId,Status:PingStatus}' --output table
./scripts/Initialize-ExperimentSSM.ps1 -Mode peering
```

Script yêu cầu cả bốn máy Online. Script tải ba file Bash, cài công cụ còn thiếu,
lưu môi trường và bật listener iperf3 TCP 5201–5203 trên private IP.
Không đổi MTU, không chạy benchmark bão hòa. Kiểm tra gồm ping, ba cổng TCP và
iperf3 giới hạn 1 Mbit/s trong 2 giây mỗi chiều, thực hiện tuần tự tránh tranh server.
Kết quả Run Command lưu ở `tmp/`; bằng chứng trên EC2 ở `/home/ec2-user/nt531-results/`.

Sau khi đổi route bằng Terraform:

```powershell
./scripts/Initialize-ExperimentSSM.ps1 -Mode tgw -CheckOnly
```

Mode phải khớp output Terraform. Nhãn mode trong log không tự chứng minh đường đi:
cần lưu route AWS cùng bằng chứng kết nối của lượt đo.

## Terminal để tự đo

AWS Console → region us-east-1 → EC2 → chọn máy → Connect → Session Manager.
Trong terminal chuyển sang tài khoản chứa script và kết quả:

```bash
sudo -iu ec2-user
```

Tiếp tục theo `04-do-va-giai-thich.md`. CLI `aws ssm start-session` cần thêm
Session Manager plugin trên máy cá nhân; dùng Console không cần plugin đó.

Đọc `05-trang-thai-trien-khai.md` để biết phần nào đã chạy thực tế.
