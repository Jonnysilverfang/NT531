# Bài 7 — Kết quả fan-in TGW và đối chiếu Peering

Đã kiểm tra trực tiếp log phiên TGW **1791296141** trên bốn EC2,
bắt đầu theo lịch 06/10/2026 14:15:41 UTC (21:15:41 Việt Nam).
Không dùng phiên A 1791296096 đã bị hủy để tổng hợp.

## Điều kiện và kiểm chứng

A→B:5201, C→B:5202, D→B:5203 cùng tạo tải. Mỗi nguồn một luồng TCP,
MTU1500, iperf3 3.19.1, TCP cubic, bỏ 5 giây đầu, đo 30 giây,
5 lượt bắt đầu cách nhau 45 giây theo lịch. Bốn EC2 c6i.large cùng
AZ us-east-1a; NTP yes trong metadata.

Cả 15 JSON hợp lệ, exit0, stderr trống, CSV khớp JSON, không có
schedule-error. A/C/D mỗi máy 47 file; B đủ 5 file CPU/ENA/metadata/end.
Đã sao lưu **146 file gốc** vào A/, B/, C/, D/ dưới
`results/formal/tgw/tcp-fanin/`, kiểm tra SHA256 bốn archive,
số file, metadata và 15 JSON so với bản audit. Log trên EC2 vẫn giữ nguyên.

Snapshot AWS trước/sau phép đo đều có 12 route TGW active,
0 route liên VPC qua Peering. Cả bốn đã kết thúc; không có client
iperf hoặc mpstat cũ khi thu thập bản sao.

## Kết quả TGW

| Nguồn → B | Receiver throughput trung bình 5 lượt (Gbps) | Min–max từng lượt (Gbps) | CPU nguồn trung bình (%) | Retransmission mỗi lượt (min–max) |
|---|---:|---:|---:|---:|
| A | 3.7966 | 3.1136–4.6087 | 14.84 | 1,017–75,103 |
| C | 3.7943 | 2.8006–4.6060 | 17.08 | 1,602–84,048 |
| D | 3.9996 | 3.6228–4.1920 | 14.23 | 21,649–63,560 |

Tổng xấp xỉ của các throughput phía nhận trung bình: **11.5905 Gbps**.

| Lượt | Tổng receiver throughput xấp xỉ (Gbps) | Độ lệch khởi chạy wrapper (s) | Khoảng đo chung xấp xỉ (s) |
|---|---:|---:|---:|
| 1 | 11.5902 | 0.8231 | 29.1886 |
| 2 | 11.5507 | 0.7800 | 29.2288 |
| 3 | 11.6023 | 0.7800 | 29.2281 |
| 4 | 11.6082 | 0.8073 | 29.2010 |
| 5 | 11.6012 | 0.8082 | 29.2023 |

Khoảng đo chung dùng wrapper start+5 giây đến wrapper end, chưa phải
cửa sổ đo nội bộ iperf chính xác. Các nguồn cùng tạo tải gần 29.2 giây
trong mỗi lượt, không bắt đầu đồng thời tuyệt đối. Tổng throughput trên
được cộng từ trung bình toàn cửa sổ từng nguồn; chưa tính lại từ các
interval trên cửa sổ chung.

CPU tổng hợp B trong năm cửa sổ 30 giây theo lịch đạt **56.88%**,
30 mẫu mỗi cửa sổ. CPU nguồn dùng wrapper start+5/end, 30 mẫu mỗi lượt.
Đây là busy=100−%idle trên dòng all của mpstat, không phải CPU từng lõi.

## Đối chiếu với Peering

| Chỉ số | Peering 1791293390 | TGW 1791296141 |
|---|---:|---:|
| A→B, mean receiver Gbps | 3.9583 | 3.7966 |
| C→B, mean receiver Gbps | 3.7799 | 3.7943 |
| D→B, mean receiver Gbps | 3.8728 | 3.9996 |
| Tổng xấp xỉ, mean Gbps | 11.6110 | 11.5905 |
| CPU B theo cửa sổ lịch, mean % | 59.18 | 56.88 |
| Delta bw_in_allowance_exceeded trên B | 1,434,501 | 6,608,210 |
| Delta pps_allowance_exceeded trên B | 160,457,411 | 77,094,456 |

Tổng xấp xỉ TGW thấp hơn Peering **0.1765%**, làm tròn 0.18%.
Đây là chênh lệch quan sát giữa hai phiên, không phải bằng chứng có
ý nghĩa thống kê hoặc hai công nghệ tương đương. TGW có dao động
throughput từng nguồn giữa các lượt, trong khi tổng xấp xỉ thay đổi ít.
Chưa xác định nguyên nhân dao động/phân chia throughput từ số trung bình.

Cả hai phiên đều có delta bandwidth/PPS allowance trên B tăng.
Năm bộ đếm allowance của các nguồn không tăng trong từng lượt TGW;
delta B về bw_out, conntrack và linklocal cũng bằng 0.
Theo [tài liệu ENA của AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html),
delta bandwidth/PPS đếm gói bị xếp hàng hoặc loại bỏ khi vượt giới hạn
instance. Không coi tất cả delta là mất gói, không cộng hai bộ đếm làm
số gói mất, không dùng giá trị nhỏ hơn để tự kết luận công nghệ tốt hơn.
ENA B được chụp trước/sau cả khoảng ghi log, không phân bổ cho từng lượt.

## Nhận xét để đưa vào DOCX

> Trong kịch bản ba nguồn A, C và D đồng thời gửi TCP một luồng tới B
> qua Transit Gateway, với MTU1500 và 5 lượt đo, throughput phía nhận
> trung bình lần lượt đạt 3.797, 3.794 và 4.000 Gbps; tổng xấp xỉ
> 11.591 Gbps. CPU tổng hợp B đạt khoảng 56.88% trong các cửa sổ theo
> lịch. Tổng throughput xấp xỉ gần mức 11.611 Gbps của Peering,
> chênh lệch quan sát khoảng 0.18%. Tuy nhiên, cả hai phiên đều ghi
> nhận bộ đếm ENA về giới hạn băng thông nhận và PPS trên B tăng,
> cho thấy giới hạn máy nhận tác động tới phép đo. Hai phương án đo
> nối tiếp và các cửa sổ không trùng nhau hoàn toàn; chưa đủ cơ sở
> kết luận Peering tốt hơn TGW, hai phương án tương đương, hoặc
> xác định năng lực tối đa của dịch vụ từ kết quả này.

## Phạm vi đã hoàn tất và phần còn lại

Đủ 6/6 bộ chính đã kiểm tra: RTT khi rảnh Peering/TGW,
TCP một cặp Peering/TGW và TCP fan-in Peering/TGW. Đây là hoàn tất
thu thập bộ đo trong phạm vi tối thiểu hiện tại, không phải hoàn tất
toàn đồ án hoặc đáp ứng mọi yêu cầu chưa được đối chiếu của giảng viên.
Hai cặp Peering giữ làm bổ sung; chưa được kiểm tra đầy đủ file gốc.

Không cần chạy thêm benchmark ngay. Tiếp theo: tổng hợp bảng/biểu đồ,
giải thích RTT/throughput/retransmission/CPU/ENA và hạn chế về burst,
thứ tự/thời điểm đo, số đợt lặp và cửa sổ thời gian; hoàn thiện báo cáo,
slide và bản code/kết quả đã rà soát trên GitHub. Chỉ đo thêm nếu phát
hiện lỗi hoặc một kết luận cần thêm thí nghiệm để kiểm chứng.

Audit: `results/formal/tgw/tcp-fanin/audit-1791296141/`.
Đối chiếu máy đọc được: `results/formal/fanin-comparison-audit.json`.
