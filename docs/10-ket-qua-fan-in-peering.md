# Bài 6 — TCP fan-in qua Peering, phiên 1791293390

Đã kiểm tra trực tiếp log trên bốn EC2 qua SSM ngày 06/10/2026.
Phiên bắt đầu theo lịch lúc 13:29:50 UTC, tức 20:29:50 Việt Nam.
Đây là phiên đo lại sau khi người dùng yêu cầu khởi động lại phép đo.

## Điều kiện và tính đầy đủ

A→B:5201, C→B:5202, D→B:5203 chạy đồng thời. Mỗi nguồn một luồng
TCP, bỏ 5 giây đầu, đo 30 giây, 5 lượt cách nhau 45 giây theo lịch.
Bốn máy có MTU1500, NTP đồng bộ, iperf3 3.19.1, TCP cubic.
Snapshot trước và sau phép đo đều có 12 route liên VPC Peering active,
không có route liên VPC dùng TGW.

- A/C/D mỗi máy có 47 file, đủ 5 JSON và 5 dòng kết quả CSV.
- Cả 15 lượt có exit code 0, stderr trống, không có lỗi iperf3 hoặc schedule-error.
- Các giá trị receiver throughput và retransmission trong CSV khớp JSON.
- B có đủ 5 file: metadata, CPU, ENA trước/sau, thời điểm kết thúc.
- CPU phía gửi có 30 mẫu trong mỗi cửa sổ đo xấp xỉ.

Tổng cộng 146 file gốc trên EC2. Đã sao lưu đầy đủ về A/, B/, C/, D/
dưới `results/formal/peering/tcp-fanin/` ngày 06/10/2026 qua SSM,
kiểm tra SHA256 của bốn archive, số file sau giải nén, metadata và
15 JSON so với bản audit. Thư mục `audit-1791293390/` chứa bản trích
kiểm tra, bảng tổng hợp và `full-backup-manifest.json` ghi vị trí bản sao.

## Kết quả

| Nguồn → B | Receiver throughput trung bình 5 lượt (Gbps) | CPU nguồn trung bình (%) | Retransmission mỗi lượt (min–max) |
|---|---:|---:|---:|
| A | 3.9583 | 15.07 | 24,993–26,323 |
| C | 3.7799 | 15.62 | 22,739–25,682 |
| D | 3.8728 | 11.48 | 25,302–30,529 |

Tổng các throughput trung bình phía nhận là **11.6110 Gbps**.
Đây là tổng xấp xỉ của các cửa sổ đo gần trùng nhau, không phải tổng
được tính lại từ interval trên một cửa sổ chung chính xác.

| Lượt | Tổng receiver throughput (Gbps) | Độ lệch thời điểm khởi chạy wrapper giữa ba nguồn (s) | Khoảng đo chung xấp xỉ (s) |
|---|---:|---:|---:|
| 1 | 11.6022 | 0.2981 | 29.7089 |
| 2 | 11.6019 | 0.3015 | 29.7049 |
| 3 | 11.6381 | 0.9590 | 29.0476 |
| 4 | 11.6072 | 0.7355 | 29.2712 |
| 5 | 11.6056 | 0.7341 | 29.2726 |

Khoảng chung trên dùng thời điểm wrapper bắt đầu +5 giây đến thời điểm
wrapper kết thúc; chỉ là phép kiểm tra gần đúng vì không dùng đồng hồ
nội bộ của iperf. Các nguồn cùng tạo tải trong phần lớn khoảng đo,
nhưng không bắt đầu đồng thời tuyệt đối. Cần giữ giới hạn này trong báo cáo.

CPU tổng hợp của B trong năm cửa sổ 30 giây theo lịch đạt trung bình
**59.18%**; mỗi cửa sổ có 29–30 mẫu. CPU busy được tính bằng 100−%idle
cho dòng all của mpstat. Đây không phải CPU từng lõi và cũng không phải
thống kê chính xác trên cửa sổ chung của cả ba nguồn.

Delta ENA trên B trong toàn khoảng ghi log:

| Bộ đếm | Delta |
|---|---:|
| bw_in_allowance_exceeded | 1,434,501 |
| pps_allowance_exceeded | 160,457,411 |
| bw_out_allowance_exceeded | 0 |
| conntrack_allowance_exceeded | 0 |
| linklocal_allowance_exceeded | 0 |

Năm bộ đếm allowance này không tăng ở các máy gửi trong từng lượt.
Theo [tài liệu ENA của AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html),
các bộ đếm bandwidth/PPS đếm gói bị xếp hàng hoặc loại bỏ khi vượt
giới hạn của instance. Delta trên B cho thấy giới hạn endpoint đã tác
động trong khoảng ghi log; không được coi toàn bộ delta là số gói mất,
chuyển thành phần trăm loss, hay quy trực tiếp cho Peering.
Delta B bao phủ cả phiên, không gán riêng cho từng nguồn hoặc lượt.

## Đoạn nhận xét để đưa vào báo cáo

> Với ba nguồn A, C, D cùng gửi TCP một luồng tới B qua VPC Peering,
> MTU1500, 5 lượt đo, throughput phía nhận trung bình lần lượt đạt
> 3.958, 3.780 và 3.873 Gbps; tổng xấp xỉ 11.611 Gbps. Các nguồn có
> khoảng đo chồng nhau gần 29–30 giây trong mỗi lượt. CPU tổng hợp B
> đạt khoảng 59.18% trong các cửa sổ theo lịch. Bộ đếm ENA về giới hạn
> băng thông nhận và PPS trên B tăng, cho thấy giới hạn máy nhận ảnh
> hưởng tới hiệu năng. Kết quả phản ánh toàn hệ thống thử nghiệm và
> chưa đủ để kết luận giới hạn thông lượng của Peering.

## Sao lưu và bước tiếp theo

Đã sao lưu nguyên bốn thư mục chứa `1791293390` vào A/, B/, C/, D/;
không cần tải lại bộ này qua SFTP. Giữ nguyên tên và mọi file,
kể cả stderr rỗng. Phiên cũ giữ riêng, không gộp vào 5 lượt phiên này.

Sau khi sao lưu, bước đo tiếp theo là fan-in qua TGW với cùng endpoint,
MTU, số luồng, thời lượng và script. Cần đổi và xác nhận route trước;
tham số `tgw` của script chỉ đặt nhãn, không tự chuyển đường mạng.
Khi so sánh phải đối chiếu CPU/ENA của B ở cả hai phương án.

Bằng chứng máy đọc được: `remote-a.json`, `remote-b.json`,
`remote-c.json`, `remote-d.json`, `remote-audit.json`,
`validated-summary.json`, `routes-after-measurement.json` trong thư mục audit.
