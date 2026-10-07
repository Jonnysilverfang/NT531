# Bài 6: TCP fan-in qua Peering

## Câu hỏi và điều kiện

Ba nguồn A/C/D đồng thời gửi TCP tới B. Đo throughput từng nguồn, tổng
throughput trên khoảng thời gian chung, retransmission phía gửi, CPU từng
lõi và toàn máy, bộ đếm ENA hai đầu. Máy nhận B là endpoint dùng chung.
Giảm throughput không tự chứng minh có nghẽn TGW; cần đối chiếu CPU/ENA
và so sánh hai mode cùng điều kiện. Bài kế tiếp dùng cùng script qua TGW.

| Nguồn | Đích | Cổng trên B |
|---|---|---:|
| A: 10.10.10.212 | 10.20.10.155 | 5201 |
| C: 10.30.10.212 | 10.20.10.155 | 5202 |
| D: 10.40.10.155 | 10.20.10.155 | 5203 |

Mỗi cổng thuộc một iperf3 server riêng. Mỗi nguồn P1, bỏ 5 giây đầu,
đo 30 giây, 5 lượt với giờ bắt đầu cách nhau 45 giây. MTU1500,
iperf3 3.19.1, bốn c6i.large cùng AZ. Không chạy thêm tải/SFTP lúc đo.
Thứ tự các mode và burst credits có thể ảnh hưởng kết quả; ghi rõ thứ tự
Peering trước, TGW sau và không khái quát từ một đợt so sánh.

## Chạy qua Termius

`measure-tcp-fanin.sh` đã cài trong home ec2-user cả bốn máy.
Script tự chọn vai trò và cổng theo IP riêng. Label mode không đổi AWS
route; phải xác nhận route đã apply trước khi chạy. Script được kiểm tra
cú pháp với bash -n; tải benchmark chỉ bắt đầu khi người dùng chạy.

Trên A tạo T mới:

```bash
T=$(date -u -d '+3 minutes' +%s)
echo "COPY SO NAY: $T"
```

Copy toàn bộ số. Trên B, C, D lần lượt chạy lệnh read, dán số khi được
hỏi, Enter, rồi mới chạy bash:

```bash
read -rp 'Dan nguyen so tu may A roi Enter: ' T
```

```bash
bash ~/measure-tcp-fanin.sh peering "$T"
```

Trên A chạy trước giờ T:

```bash
bash ~/measure-tcp-fanin.sh peering "$T"
```

Bốn máy cần hiện READY cùng giờ. A/C/D in 5 kết quả; B ghi CPU nền và
tự kết thúc 220 giây sau T. Cả bốn tự hiện DONE, không cần kill riêng.
Nếu T đã qua, hủy các script còn chạy bằng Ctrl+C, tạo T mới và dùng
cùng mốc mới cho cả bốn; giữ log phiên bị hủy tách khỏi lượt hợp lệ.

Tải đúng thư mục RESULTS của mỗi máy vào
`results/formal/peering/tcp-fanin/A/`, B/, C/, D/.
Sender A/C/D mỗi máy có 47 file nếu đủ 5 lượt; B có 5 file.

## Kiểm tra và báo cáo

Kiểm tra JSON, exit code, metadata và giờ khởi chạy thực tế có độ phân
giải nano giây. Lấy khoảng giao nhau của các cửa sổ đo; không cộng số
liệu từ các thời điểm không chồng nhau. Nếu lệch giờ đáng kể, tính từ
interval JSON trên khoảng chung và trình bày độ lệch, hoặc lặp lại phiên.
CPU B cần lọc theo khoảng đo, tránh lấy cả thời gian chờ/nghỉ.
ENA B trước/sau cả phiên không thể gán riêng cho mỗi nguồn/lượt.

Ghi chú mở đầu để đưa vào báo cáo:

> Bài 6 đo TCP fan-in: A, C và D cùng gửi tới B qua VPC Peering bằng
> ba listener TCP riêng (5201, 5202, 5203). Mỗi nguồn dùng một luồng,
> MTU1500; thực hiện 5 lượt, bỏ 5 giây đầu và đo 30 giây. Thu thập
> throughput phía nhận của từng nguồn, retransmission, CPU và ENA để
> đánh giá hiệu năng khi dùng chung máy nhận. Kết luận sẽ dựa trên log
> thực tế và phép đối chiếu với TGW cùng điều kiện.

