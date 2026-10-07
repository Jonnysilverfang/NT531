# TCP một cặp A → B: kết quả đã kiểm tra

Ngày kiểm tra: 06/10/2026. Dữ liệu đo thật trong `results/formal/`.

| Chỉ số | Peering | TGW |
|---|---:|---:|
| Số lượt hợp lệ | 5 | 5 |
| Throughput receiver trung bình (Gbps) | 4,782804 | 4,608265 |
| Retransmission mỗi lượt, min–max | 48.253–57.185 | 0–671 |
| CPU A busy trung bình, toàn máy (%) | 20,951 | 17,809 |
| CPU B busy trung bình, toàn máy (%) | 18,665 | 20,507 |

Thông số chung: c6i.large, cùng AZ us-east-1a, MTU1500, iperf3 3.19.1,
TCP P1, bỏ 5 giây đầu, đo 30 giây, nghỉ 10 giây. CSV khớp JSON,
exit code cả 10 lượt bằng 0 và stderr trống. A có 42 file mỗi mode,
B có 5 file mỗi mode; log B bao phủ đủ thời gian các lượt A.

CPU lấy từ dòng `all` của mpstat, tính busy = 100 − %idle. Chỉ lấy mẫu
có thời gian lớn hơn start+5 giây và không vượt end của từng lượt, rồi lấy
trung bình các lượt. Thời điểm start/end là dấu thời gian bên ngoài iperf,
có độ phân giải giây; cửa sổ CPU xấp xỉ khoảng đo 30 giây. Đây là CPU
trung bình toàn máy, chưa chứng minh từng lõi hoặc ứng dụng không bị giới hạn.

Năm bộ đếm ENA được kiểm tra: bw_in_allowance_exceeded,
bw_out_allowance_exceeded, pps_allowance_exceeded,
conntrack_allowance_exceeded và linklocal_allowance_exceeded.
Chênh lệch tất cả bằng 0 ở cả hai mode. A có snapshot trước/sau từng lượt;
B có snapshot trước/sau cả phiên. Không ghi nhận tăng ở các bộ đếm này;
không suy ra nguyên nhân retransmission từ kết quả đó.

Peering cao hơn TGW khoảng 3,79% trong hai đợt đo. Retransmission Peering
cao hơn rõ rệt; không đổi số lần retransmission thành tỷ lệ mất gói.
Hai đợt đo ngày 05/10 và 06/10, không xen kẽ. Chưa thể quy chênh lệch
thông lượng hoặc truyền lại hoàn toàn cho Peering/TGW.

Chi tiết từng lượt: `results/formal/tcp-single-comparison-audit.json`.

