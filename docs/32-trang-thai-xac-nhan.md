# Trạng thái xác nhận và công việc tiếp theo

Snapshot 13/10/2026 16:13 giờ Việt Nam, tái tạo từ hai `analysis.json`. Số block là số lần đo đạt kiểm tra raw; không phải phần trăm hoàn thành toàn đồ án.

| Nghiên cứu | Block hợp lệ | Ngày địa phương | Còn thiếu |
|---|---:|---:|---:|
| RTT khi rảnh | 4/16 | 2 | 12 block |
| Can thiệp slots | 1/16 | 1 | 15 block |

Mỗi nghiên cứu cần ít nhất bốn ngày. Chỉ công bố kiểm định chính sau đủ 16 block và các tiêu chí chất lượng. Engineering 84.000 requests và pilot/calibration 62.200 requests không nhập vào số block này.

## RTT từng block đã kiểm tra

| Block | Bắt đầu giờ Việt Nam | Thứ tự | Peering ms | TGW ms | Chênh ms | Missing replies |
|---|---|---|---:|---:|---:|---:|
| 1 | 12/10 16:41:00 | peering → tgw | 0.211333 | 0.441667 | +0.230333 | 0 |
| 2 | 12/10 21:26:56 | tgw → peering | 0.206667 | 0.446333 | +0.239667 | 0 |
| 3 | 13/10 11:10:24 | peering → tgw | 0.190000 | 0.615667 | +0.425667 | 0 |
| 4 | 13/10 15:58:29 | tgw → peering | 0.124333 | 0.430000 | +0.305667 | 0 |

## Slots từng block đã kiểm tra

| Block | Bắt đầu giờ Việt Nam | Tăng đúng hạn trung bình tại 800 rps | Vượt 10 điểm phần trăm |
|---|---|---:|---|
| 1 | 13/10 11:39:03 | 97.3167 điểm phần trăm | Có |

Các giá trị trên là mô tả các block đã có, không phải p-value tạm thời để quyết định dừng. Tăng đúng hạn là hiệu tỷ lệ với mẫu số mọi request theo lịch, trung bình qua hai mode.

## Lịch và vận hành đã được người dùng chấp thuận

Người dùng yêu cầu tiếp tục và đẩy nhanh ngày 13/10. Heartbeat trong chat chạy lúc **08:00, 11:00, 14:00, 17:00, 20:00 và 23:00** giờ Việt Nam; ID `ho-n-t-t-x-c-nh-n-nt531`. Mỗi phiên thu tối đa một block kế tiếp của từng nghiên cứu, tuần tự; giữ start cách nhau ít nhất hai giờ và uptime slots ít nhất 30 phút. Bộ lập kế hoạch giữ đủ block cho ít nhất bốn ngày, không thu block cuối quá sớm. Nếu vận hành thông suốt, slots có thể đủ sớm nhất 16/10; đây không phải cam kết ngày hoàn tất toàn đồ án. Lịch có thể bị gián đoạn nếu ứng dụng/máy người dùng không hoạt động hoặc đăng nhập AWS hết hạn.

Quy trình: kiểm tra protocol/cohort và phiên đang chạy → bật đúng bốn máy cũ → SSM Online, dừng workload cũ và đủ uptime → RTT rồi slots → phân tích raw → cập nhật báo cáo/GitHub → sao lưu ZIP riêng → stop bốn EC2, xác nhận `stopped`. Giữ EBS/EIP/TGW theo quyết định người dùng; các tài nguyên này vẫn có thể phát sinh phí.

`scripts/start-confirmation-session.py --check` chỉ kiểm tra điều kiện offline; không khởi động tài nguyên. Lệnh không có `--check` bật cohort đã xác minh, không thu kết quả. Script từ chối attempt chưa hoàn tất và lỗi chưa được phân xử của block sắp đo. Không tự retry phép đo. Người điều phối chịu trách nhiệm stop máy kể cả khi bước chuẩn bị/đo lỗi.

`scripts/run-confirmation-session.py` chạy một phiên trọn vẹn với khóa `tmp/confirmation-session.lock`: chuẩn bị → RTT → slots → kiểm chứng truyền file/raw → cập nhật trạng thái → sao lưu và stop trong finally. Khi một phiên còn chạy, heartbeat chỉ đọc tiến độ; không mở phiên khác hay stop giữa phép đo. Nếu SSM không khả dụng, cleanup kiểm tra account, đúng bốn ID/tag trước khi stop qua EC2 API. Lỗi đăng nhập không được báo thành công giả. Phụ lục Word và GitHub vẫn cần bước rà soát của heartbeat sau khi raw đã hợp lệ.

Raw tải sau cửa sổ đo qua SCP nếu có khóa tạm bảo vệ ACL. Host key lấy qua SSM đã xác thực, bật kiểm tra nghiêm ngặt; size/SHA đối chiếu và `.transport.json` giữ bằng chứng. Mã ứng dụng và protocol giữ nguyên. Khóa tạm trong `tmp/` không nằm trong ZIP công bố/GitHub; xóa bản sao tạm khi cuối phiên không còn tải file.

## Việc để chốt kết luận và bàn giao

1. Thu các block còn thiếu qua đủ ngày; giữ mọi block/lỗi, không chọn dữ liệu thuận lợi.
2. Sau đủ RTT, đo RTT khi tải theo phần thăm dò đã định; không nhập vào kiểm định RTT idle.
3. Công bố độ lớn hiệu ứng, CI/cận xác suất và kiểm định đã chốt, kể cả nếu không đạt giả thuyết.
4. Ghép kết quả mới vào báo cáo chung, kiến trúc, công thức, bài giảng và related work; rà soát slide/demo.
5. Khi mọi việc hoàn tất, stop máy và xóa heartbeat; không tiếp tục đo tự động vô hạn.

[Tiêu chí bằng chứng và kết luận](30-bang-chung-va-tieu-chi-hoan-thanh.md) · [Protocol slots và công thức](27-can-thiep-slots-va-hang-doi.md) · [Phụ lục Word](31-phu-luc-bang-chung-thong-ke.docx) · [Báo cáo tổng hợp](34-bao-cao-tong-hop.md)

## Dữ liệu nguồn

- `results/confirmation-rtt-v1/analysis.json` — SHA256 `ad3de2850636fd117832a9508768ae89bf971354ecd3b5c03c91e8d729309b66`
- `results/application-slots-confirmation-v1/analysis.json` — SHA256 `829c9b30c39607b3554c1ae13844f8cb372ba59657f58ca5f9f8400f43ac30e0`
