# Bài 7 — Đo fan-in qua Transit Gateway

Mục tiêu: đối chiếu với bài fan-in Peering, giữ nguyên A/C/D→B,
MTU1500, TCP một luồng mỗi nguồn, bỏ 5 giây đầu và đo 30 giây.
Thực hiện 5 lượt đồng thời, các mốc bắt đầu cách nhau 45 giây.
B thu thập CPU/ENA; A/C/D thu thập JSON, CPU/ENA và summary.csv.

Script và endpoint giữ nguyên. A→B:5201, C→B:5202, D→B:5203.
Tham số `tgw` chỉ đặt nhãn kết quả: phải kiểm tra route AWS trước khi chạy.
Không chạy song song một bài benchmark khác.

## Chuẩn bị hạ tầng

Ngày 06/10/2026 đã apply plan `fanin-tgw-20261006.tfplan`: 0 thêm,
12 cập nhật route, 0 xóa. JSON plan xác nhận chỉ hai thuộc tính target
Peering/TGW thay đổi. AWS xác nhận 12 route TGW active, 0 route Peering.
Cả bốn máy health OK, MTU1500, NTP yes, ba listener active và script
bash -n thành công. A→B:5201, C→B:5202, D→B:5203 kết nối TCP thành công.
Bằng chứng tại `results/formal/tgw/tcp-fanin/`.
Đã hoàn tất và kiểm tra phiên 1791296141, sao lưu đủ 146 file gốc.
Xem [kết quả TGW và đối chiếu Peering](12-ket-qua-fan-in-tgw-va-so-sanh.md).
Các lệnh bên dưới dùng để tái lập; không cần chạy thêm ngay.

Đổi `routing_mode="tgw"` trong `infra/terraform/experiment.auto.tfvars`.
Tạo plan mới, kiểm tra JSON plan chỉ cập nhật 12 route liên VPC từ
Peering sang TGW, rồi apply chính plan đó. Snapshot route AWS sau apply
phải có 12 route TGW active và 0 route liên VPC trỏ Peering.
Lưu bằng chứng vào `results/formal/tgw/tcp-fanin/`.

EC2 phải running, health OK, MTU1500 và NTP đồng bộ. Trên B ba
listener systemd nt531-iperf@5201/5202/5203 phải active. Không cần
reboot hoặc tạo máy mới. Ba nguồn đều có script ~/measure-tcp-fanin.sh.

## Chạy trong Termius

Trên **A**, dán khối sau. A in số T rồi chờ giờ bắt đầu:

```bash
T=$(date -u -d '+3 minutes' +%s)
echo "COPY SO T NAY: $T"
bash ~/measure-tcp-fanin.sh tgw "$T"
```

Copy nguyên số T A vừa in. Trên **B**, rồi **C**, rồi **D**, chạy
dòng sau trên từng máy. Khi được hỏi, dán cùng số T rồi Enter:

```bash
read -rp 'Dan so T tu A, roi Enter: ' T; bash ~/measure-tcp-fanin.sh tgw "$T"
```

Dòng read và bash được đặt trên cùng một dòng để không vô tình đọc
lệnh bash của lần dán nhiều dòng làm giá trị T. Không nhập số lượt
vào prompt T và không tự tạo mốc mới ở B/C/D.

Cả bốn phải hiện READY cùng giờ UTC trước khi tới T. Đây là giờ hẹn
chạy, không phải cơ chế tự đợi tất cả máy xác nhận. Nếu một máy báo
mốc quá gần/đã qua, hủy các script đang chờ và tạo một mốc mới trên A.
Giữ folder phiên bị hủy riêng, không gộp vào số liệu hợp lệ.

Từ mốc T, cả phiên mất khoảng 220 giây. A/C/D in 5 lượt kết quả;
B ghi CPU nền và có thể không in thêm gì cho đến DONE. B nhận dữ liệu
qua ba service iperf3 đang chạy, không cần mở server thủ công lần nữa.

## Sao lưu và nhận xét

Giữ nguyên các folder `tgw-tcp-fanin-{node}-{T}-...` trong
~/nt531-results. Sao lưu đầy đủ về A/, B/, C/, D/ dưới
`results/formal/tgw/tcp-fanin/`. Mỗi sender có 47 file, B có 5 file.
Kiểm tra JSON, exit0, stderr, CSV, CPU/ENA và thời điểm thực tế.

Đối chiếu throughput từng nguồn, tổng xấp xỉ trên các khoảng chồng nhau,
CPU B và delta ENA với phiên Peering 1791293390. Hai phương án đo nối
tiếp nên còn sai lệch theo thời điểm/burst credits. Nếu B chạm giới hạn
instance, không quy toàn bộ giảm tốc cho TGW hoặc Peering. Không chọn
riêng lượt nhanh nhất và không coi retransmission là tỷ lệ packet loss.

Phần đo chính hiện tại kết thúc sau khi bộ TGW này được kiểm tra hợp lệ;
các bước tiếp theo là bảng/biểu đồ, phân tích hạn chế, báo cáo, slide
và bản code/kết quả đã rà soát trên GitHub.
