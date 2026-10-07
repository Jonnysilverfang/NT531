# Bước 1: Hai mạng riêng A và B

> Tài liệu lịch sử của bước học đầu tiên. Cấu hình hiện đã mở rộng tới subnet,
> route, Security Group và EC2. Xem `infra/terraform/README.md` cho hiện trạng;
> dự kiến “2 to add” bên dưới chỉ áp dụng ở bước khởi đầu.

## Mục đích

Chuẩn bị hai mạng độc lập trước khi đặt EC2 vào chúng. Chưa có subnet,
EC2, Peering, Transit Gateway hay đường Internet trong cấu hình này.

VPC A dùng 10.10.0.0/16; VPC B dùng 10.20.0.0/16.
IPv4 có 32 bit. /16 nghĩa là 16 bit đầu xác định mạng, còn 16 bit
dành cho phần địa chỉ bên trong: A có phạm vi 10.10.0.0–10.10.255.255.
Đây là không gian địa chỉ, không phải số máy có thể dùng ngay.
Sau này ta chia subnet và AWS có địa chỉ dành riêng trong mỗi subnet.
Hai dải không trùng nhau giúp định tuyến phân biệt được mạng đích.

## Đọc code

- versions.tf: phiên bản Terraform, AWS provider và nơi lưu state riêng.
- main.tf: tài khoản được phép, profile, region và hai resource aws_vpc.
- outputs.tf: thông tin Terraform sẽ hiển thị sau khi tạo.
- aws_vpc.a: địa chỉ logic trong Terraform; nt531-vpc-a là nhãn trên AWS;
  vpc-... là ID thật do AWS cấp sau khi tạo.
- DNS support/hostnames chuẩn bị chức năng DNS; không tự tạo đường Internet.

## Kiểm tra, chưa triển khai

Chạy từ thư mục gốc project trong PowerShell:

```powershell
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
terraform '-chdir=infra/terraform' plan '-out=nt531.tfplan'
```

init tải provider và khởi tạo backend; validate kiểm tra cấu hình;
plan đọc trạng thái và xem trước thay đổi, chưa tạo tài nguyên AWS.
Kế hoạch đầu tiên mong đợi: 2 to add, 0 to change, 0 to destroy.
AWS tự tạo các thành phần mặc định đi kèm VPC; số 2 là số resource
Terraform quản lý trực tiếp trong cấu hình hiện tại.

## Giữ phạm vi quản lý

Profile nt533-lab chỉ cung cấp đăng nhập, không phân chia tài nguyên.
State riêng infra/terraform/nt531.tfstate ghi các tài nguyên của NT531.
Không import VPC mặc định hoặc tài nguyên bài khác vào state này.
Không xóa hay đưa state lên Git; giữ state và backup để quản lý/dọn lab.
Giữ .terraform.lock.hcl trong Git để tái sử dụng đúng phiên bản provider.
allowed_account_ids chặn dùng sai tài khoản, nhưng không thay thế việc
kiểm tra kế hoạch. Tag Project=NT531 chỉ là nhãn, không phải quyền bảo vệ.

Hiện chưa thiết lập tự động dọn. Không chạy apply/destroy trong bước học này.
