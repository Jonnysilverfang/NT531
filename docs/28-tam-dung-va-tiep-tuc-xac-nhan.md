# Tạm dừng EC2 và tiếp tục đợt xác nhận

Quyết định của người dùng cuối phiên 12/10: **stop bốn EC2, giữ hạ tầng**.
Thu và kiểm tra raw trước khi stop. Không terminate EC2, không destroy
Terraform, không xóa EIP/TGW. File bằng chứng thao tác nằm trong
`results/session-lifecycle/`; chỉ khi ghi `stopped_verified` mới tính đã dừng.

Phiên 12/10 đã có [bằng chứng stopped_verified](../results/session-lifecycle/20261012T163804Z-stop.json)
cho cả bốn ID, kèm SHA256 của ZIP riêng 17.336.911 bytes / 1.019 file.
ZIP được tạo trước khi gửi lệnh stop; bằng chứng trạng thái được ghi sau đó.

## Những gì được lưu

Mỗi phiên ứng dụng lưu mọi yêu cầu, trạng thái thất bại, thông số generator,
log hàng đợi C/D có request ID, CPU/ENA, route, package và mã nguồn thực chạy.
Engineering được giữ ở `results/application-slots-engineering-v1/`;
xác nhận ở `results/application-slots-confirmation-v1/`. Hai phần không gộp.
Các block RTT có thư mục và protocol riêng.

`scripts/save-session-backup.py` tạo ZIP **riêng tư** trong `backups/`, gồm
kết quả, tài liệu, mã thí nghiệm và Terraform state hiện tại. Mỗi file được
đọc lại từ ZIP để đối chiếu byte/SHA256. Không đưa ZIP/state lên GitHub.
Không chứa AWS credentials, SSH keys, tfvars hay mật khẩu Grafana. GitHub
lưu code, protocol và raw đã rà soát. ZIP cùng ổ đĩa chưa bảo vệ khỏi hỏng
ổ; nên giữ thêm một bản riêng trên thiết bị/lưu trữ của nhóm.

`scripts/pause-ec2.py` kiểm tra tài khoản, bốn ID/IP/tag dự án, dừng app và
monitor, tạo backup, stop đúng bốn EC2 rồi đọc lại trạng thái. Không có
lệnh terminate/destroy/delete. Giữ mạng giúp tiếp tục cùng cohort EC2/TGW.

## Phí khi dừng

EC2 stopped không tính compute như running; EBS và địa chỉ IPv4 public
còn cấp phát vẫn có thể tính phí. Các TGW attachment giữ lại vẫn có phí
theo giờ. Vì vậy stop tiết kiệm compute, không đưa hóa đơn về 0.
Nguồn: [EC2 lifecycle](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html),
[VPC IPv4 pricing](https://aws.amazon.com/vpc/pricing/),
[TGW pricing](https://aws.amazon.com/transit-gateway/pricing/).

## Mở lại phiên sau

Chạy từ PowerShell trong thư mục dự án; chỉ start khi đã sẵn sàng tiếp tục.
Đăng nhập profile trước nếu đã hết hạn:

```powershell
aws login --profile nt533-lab
aws ec2 start-instances --profile nt533-lab --region us-east-1 --instance-ids i-089bae0de9ec6bc4e i-0484f42b82795f765 i-0a3f3e2e9d7185970 i-0abcc8853cee750e7
aws ec2 wait instance-status-ok --profile nt533-lab --region us-east-1 --instance-ids i-089bae0de9ec6bc4e i-0484f42b82795f765 i-0a3f3e2e9d7185970 i-0abcc8853cee750e7
py scripts/application-qos.py setup
```

Chờ SSM cả bốn máy Online trước setup; setup sẽ từ chối nếu chưa đủ.
Setup đặt lại MTU 1500 (thiết lập MTU trước reboot không được giả định vẫn
còn), kiểm tra môi trường và cài đúng mã đã khóa. Chờ uptime ít nhất 30 phút
trước block slots. Đọc trạng thái raw để chọn **block kế tiếp**, không đo
lại block hợp lệ. Không chạy app và RTT đồng thời.

```powershell
tmp/application-venv/Scripts/python.exe experiments/application-qos/analyze_slots.py --study
py scripts/rtt-confirmation.py --analyze
```

RTT và slots đều cần 16 block hợp lệ, trên ít nhất bốn ngày; các block trong
cùng nghiên cứu cách nhau ít nhất hai giờ. Có thể bố trí bốn block/ngày
trong bốn ngày, nhưng phải kiểm tra khoảng cách, thời lượng và chất lượng
thực tế. Ngày 13/10 người dùng đã cho phép heartbeat tiếp tục trong chat
lúc 08:00, 11:00, 14:00, 17:00, 20:00 và 23:00 giờ Việt Nam theo yêu cầu
đẩy nhanh sau khi tiếp tục, stop bốn máy cuối mỗi phiên. Bộ lập kế hoạch
giữ đủ block cho ít nhất bốn ngày; không dùng hết block cuối ở ngày thứ ba.
Lịch phụ thuộc ứng dụng/máy đang hoạt động và phiên đăng nhập AWS còn hạn;
không phải tác vụ chạy độc lập trên AWS. Xem [trạng thái và lịch](32-trang-thai-xac-nhan.md).

Phiên có thể dùng `py scripts/start-confirmation-session.py` để kiểm tra
protocol, cohort/tag, khoảng cách và attempt đang chạy trước khi bật đúng
bốn máy cũ, chờ Online, đặt MTU 1500 và đủ uptime. `--check` chỉ đọc dữ liệu
offline, không gọi AWS. Helper không tự đo hay retry; người điều phối phải
stop máy bằng `scripts/pause-ec2.py` ở cuối phiên, kể cả khi đo lỗi.
Khóa tải raw tạm được bảo vệ ACL và xóa sau khi máy đã stop; khóa gốc giữ nguyên.

Wrapper `py scripts/run-confirmation-session.py` thực hiện cả chuẩn bị, đo,
kiểm chứng raw, cập nhật trạng thái, sao lưu và stop trong finally. Trước khi
gọi, kiểm tra `tmp/confirmation-session.lock` và PID: không chạy phiên khác
hay stop giữa phép đo đang hoạt động. Khi runner kết thúc, heartbeat rà soát
raw, phụ lục Word và công bố GitHub. Lỗi đo không tự retry. Lỗi cleanup không
được ghi nhận thành `stopped`; nếu SSM không dùng được, fallback chỉ stop
qua EC2 sau khi xác minh account và đúng bốn ID/tag.

Stop/start giữ instance ID và EIP, nhưng có thể đổi host vật lý. Boot ID,
uptime và môi trường được lưu; không tuyên bố mọi phiên cùng host vật lý.
Nếu xóa/dựng lại làm đổi EC2/TGW IDs, mở nghiên cứu/cohort mới thay vì nhập
dữ liệu vào cohort hiện tại. Không thay protocol hoặc ứng dụng giữa đợt.
