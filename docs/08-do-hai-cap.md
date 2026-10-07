# Bài 5: TCP hai cặp đồng thời qua Peering

## Vai trò trong phạm vi báo cáo — cập nhật 06/10/2026

Bài hai cặp là phần bổ sung. Bốn endpoint riêng không tạo cạnh tranh
CPU/NIC trên cùng EC2, nên không dùng bài này để khẳng định có nghẽn hay
không có nghẽn TGW. Kết quả gần giống bài một cặp là kết quả hợp lý,
nhưng không chứng minh hệ thống không giới hạn khi tăng quy mô/tải.

Người dùng đã hoàn tất Peering trên cả bốn máy (ảnh có DONE).
Giữ kết quả và kiểm tra log sau khi tải về. Tạm thời không ưu tiên chạy
bản TGW hai cặp; phần tiếp theo tập trung fan-in A/C/D→B trên hai mode.
Nếu bỏ bản TGW hai cặp, trình bày Peering như quan sát bổ sung,
không trình bày nó thành so sánh Peering/TGW của kịch bản hai cặp.

Fan-in có máy nhận B dùng chung. CPU/ENA B phải được đối chiếu trước
khi quy chênh lệch thông lượng cho mạng hoặc TGW.

Mục tiêu: A→B và C→D truyền cùng lúc. Mỗi cặp một luồng TCP,
5 lượt, bỏ 5 giây đầu, đo 30 giây; giờ bắt đầu các lượt cách nhau 45 giây.
Thu thập receiver throughput, retransmission, CPU và ENA cả bốn máy.
EIP chỉ để truy cập Termius; bài đo dùng IP riêng.

Script `scripts/measure-tcp-pairs.sh` đã được cài tại
`/home/ec2-user/measure-tcp-pairs.sh` trên cả bốn máy qua SSM.
Script được kiểm tra cú pháp bằng bash -n trên cả bốn máy. Nó tự nhận diện
host theo IP riêng và chờ cùng Unix timestamp người dùng nhập.
Nó không tự kiểm tra AWS route; snapshot route cần được lưu trước phiên đo.

Trên A tạo giờ bắt đầu cách hiện tại 3 phút:

```bash
T=$(date -u -d '+3 minutes' +%s)
echo "GIO BAT DAU CHUNG: $T"
```

Giữ tab A. Trên B, D, C lần lượt chạy cùng khối dưới đây; mỗi lần nhập
đúng số T do A in ra rồi Enter:

```bash
read -rp 'Nhap so T tu may A: ' T
bash ~/measure-tcp-pairs.sh peering "$T"
```

Sau đó quay lại A, trước khi đến giờ T:

```bash
bash ~/measure-tcp-pairs.sh peering "$T"
```

B/D ghi CPU rồi tự kết thúc; A/C in kết quả sau từng lượt. Đợi cả bốn
hiện DONE, tải đúng bốn thư mục RESULTS từ ~/nt531-results vào:
`results/formal/peering/tcp-two-pairs/A/`, B/, C/, D/.
Không chạy tải khác hoặc SFTP trong khoảng đo.

Nếu báo thời điểm đã qua, chọn một T mới trên A và dùng cùng T mới cho
cả bốn máy. Nếu có lỗi iperf hoặc missed shared start, giữ log để kiểm tra.

Phân tích: đối chiếu thời gian thực tế và JSON của A/C để kiểm tra khoảng
đo chồng nhau. Chỉ tổng hợp throughput trên khoảng thời gian chung;
không cộng hai lượt xảy ra ở thời điểm khác nhau.
Sau Peering, áp dụng cùng bài qua TGW với cùng máy và thông số.

