# Phạm vi rút gọn và cách chốt kết luận

Ngày 13/10/2026, người dùng yêu cầu giảm credit và không tiếp tục yêu cầu
bốn ngày. Đây là quyết định ngân sách sau khi đã quan sát các block đầu;
không phải dừng vì p-value. Lịch thu 16 block được hủy, chỉ giữ một phiên
cuối đã xếp, tối đa RTT block 5 và slots block 3. Nếu phiên đó lỗi, giữ lỗi
và dữ liệu hợp lệ hiện có; không tự đo lại hoặc mở phiên mới.

Protocol gốc, mã ứng dụng và raw giữ nguyên để kiểm chứng. Không sửa
16 thành 5/3 hay bốn ngày thành một ngày để biến dữ liệu thành xác nhận
đạt chuẩn. Đợt xác nhận gốc được ghi là **rút ngắn vì ngân sách, chưa hoàn
thành thiết kế**; kết luận mới chỉ mô tả các block đã quan sát.

## Dữ liệu hiện có

Snapshot 2026-10-13T18:36:02.008715+07:00. Trạng thái: `closed_for_budget`; phiên cuối: `validated_report_review_passed`.

| Nghiên cứu | Block đã kiểm tra | Mean hiệu ứng | Median | Khoảng từng block |
|---|---:|---:|---:|---:|
| RTT | 5 | 0.311867 ms | 0.305667 | 0.230333–0.425667 ms |
| Slots | 3 | 96.841667 percentage points | 96.662500 | 96.545833–97.316667 percentage points |

RTT: mỗi hiệu ứng là trung bình RTT TGW trừ trung bình RTT Peering trong
cùng block, đơn vị ms. Slots: hiệu tỷ lệ đúng hạn 16 trừ 8 slots tại
800 rps, trung bình qua hai mode, rồi nhân 100 để ra điểm phần trăm.
Mean/median/range tổng hợp các block; request hoặc probe không biến thành
block độc lập. Với rất ít block, không công bố p-value xác nhận hay CI
liên block có vẻ chính xác giả; mean và range không chứng minh hiệu ứng
đúng trong mọi ngày, mọi cấu hình hoặc mọi hệ thống AWS.

## Thống kê mô tả toàn bộ request đã đo

| Mạng | Slots | rps | Request theo lịch | Đúng hạn % | Khoảng P95 từng block ms |
|---|---:|---:|---:|---:|---:|
| PEERING | 8 | 600 | 27000 | 100.0000 | 12.109–12.684 |
| PEERING | 16 | 600 | 27000 | 100.0000 | 12.085–12.699 |
| TGW | 8 | 600 | 27000 | 100.0000 | 12.879–13.146 |
| TGW | 16 | 600 | 27000 | 100.0000 | 12.981–13.243 |
| PEERING | 8 | 800 | 36000 | 3.0444 | 1350.096–1499.226 |
| PEERING | 16 | 800 | 36000 | 100.0000 | 12.651–12.698 |
| TGW | 8 | 800 | 36000 | 3.2722 | 1225.784–1327.874 |
| TGW | 16 | 800 | 36000 | 100.0000 | 12.875–13.248 |

Tỷ lệ đúng hạn bằng tổng request đúng hạn chia tổng request theo lịch. Đây là tần suất thực nghiệm trong dữ liệu đã thu, không coi mọi request độc lập. Cột P95 là min–max của P95 từng block; không phải P95 gộp hoặc trung bình P95.

## Đồ án vẫn đóng góp gì?

- So sánh RTT và TCP trên cùng topology/cohort trong các phiên đã đo;
  tách dữ liệu lịch sử với đợt mới, giữ routes và điều kiện thí nghiệm.
- Can thiệp 8 → 16 slots cho thấy cải thiện deadline trong các phiên
  quan sát; queue/service logs, CPU/ENA hỗ trợ giải thích cơ chế.
- Kiểm tra định luật Little bằng sample path hữu hạn từ raw, có ký hiệu
  và đơn vị; đây là nhất quán toán học của log, không kiểm định độc lập.
- Giữ kiến trúc, code, raw, công thức, related work và giới hạn diễn giải
  để nhóm tái tạo và bảo vệ kết quả thực đã làm.

## Việc còn lại trong phạm vi mới

Phiên đo cuối đã kết thúc; không mở phiên mới. Kiểm chứng raw và tổng hợp báo cáo,
biểu đồ và Word **một lần**, rồi kiểm tra trực quan và công bố bản bàn giao. Báo cáo và Word đã qua rà soát; lịch đo tự động đã xóa sau phiên cuối. Không mở nghiên cứu mới. RTT khi tải được
hoãn và không ghi là đã đo. Không thêm tool hoặc đổi workload để làm đồ án
trông lớn hơn. Người dùng tự dừng EC2; runner sao lưu và dừng workload.

Các mục 16 block/bốn ngày trong tài liệu cũ là **kế hoạch gốc đã được thay
thế**, không còn là danh sách bắt buộc phải đo tiếp. Phương pháp kiểm định
ở đó là phương pháp đã thiết kế, không phải kết quả kiểm định đạt được.

[Quyết định phạm vi](../results/study-scope-decision-20261013.json) ·
[Snapshot mô tả](../results/analysis/reduced-study-summary.json) ·
[Báo cáo tổng hợp](34-bao-cao-tong-hop.md)
