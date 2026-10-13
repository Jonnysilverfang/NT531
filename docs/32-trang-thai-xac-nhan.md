# Trạng thái xác nhận và công việc tiếp theo

**Phạm vi mới ngày 13/10:** bỏ lịch bốn ngày vì ngân sách; chỉ giữ phiên cuối, tối đa 5 RTT/3 slots. Không tính p-value xác nhận. [Quyết định và kết luận mô tả](35-pham-vi-rut-gon-va-ket-luan.md).
**Đã kết thúc thu dữ liệu:** 5 block RTT và 3 block slots hợp lệ. Không mở thêm phiên hoặc tự đo lại; phần còn lại là rà soát và bàn giao báo cáo.
Snapshot 13/10/2026 18:36 giờ Việt Nam, tái tạo từ hai `analysis.json`. Số block là số lần đo đạt kiểm tra raw; không phải phần trăm hoàn thành toàn đồ án.

| Nghiên cứu | Block hợp lệ | Ngày địa phương | So với trần ngân sách |
|---|---:|---:|---:|
| RTT khi rảnh | 5/5 | 2 | 0 block tối đa |
| Can thiệp slots | 3/3 | 1 | 0 block tối đa |

Thiết kế gốc 16 block/bốn ngày được rút ngắn vì ngân sách, giữ nguyên protocol để kiểm chứng; không coi xác nhận đã hoàn thành. Engineering/pilot giữ riêng.

## RTT từng block đã kiểm tra

| Block | Bắt đầu giờ Việt Nam | Thứ tự | Peering ms | TGW ms | Chênh ms | Missing replies |
|---|---|---|---:|---:|---:|---:|
| 1 | 12/10 16:41:00 | peering → tgw | 0.211333 | 0.441667 | +0.230333 | 0 |
| 2 | 12/10 21:26:56 | tgw → peering | 0.206667 | 0.446333 | +0.239667 | 0 |
| 3 | 13/10 11:10:24 | peering → tgw | 0.190000 | 0.615667 | +0.425667 | 0 |
| 4 | 13/10 15:58:29 | tgw → peering | 0.124333 | 0.430000 | +0.305667 | 0 |
| 5 | 13/10 18:04:03 | peering → tgw | 0.134333 | 0.492333 | +0.358000 | 0 |

## Slots từng block đã kiểm tra

| Block | Bắt đầu giờ Việt Nam | Tăng đúng hạn trung bình tại 800 rps | Vượt 10 điểm phần trăm |
|---|---|---:|---|
| 1 | 13/10 11:39:03 | 97.3167 điểm phần trăm | Có |
| 2 | 13/10 16:03:57 | 96.6625 điểm phần trăm | Có |
| 3 | 13/10 18:09:26 | 96.5458 điểm phần trăm | Có |

Các giá trị trên là mô tả các block đã có, không phải p-value tạm thời để quyết định dừng. Tăng đúng hạn là hiệu tỷ lệ với mẫu số mọi request theo lịch, trung bình qua hai mode.

## Lịch và vận hành đã được người dùng chấp thuận

Lịch đo tự động đã xóa sau phiên cuối và rà soát Word. Không mở thêm block hoặc RTT khi tải; người dùng tự dừng EC2.

Quy trình: kiểm tra protocol/cohort và phiên đang chạy → bật đúng bốn máy cũ → SSM Online, dừng workload cũ và đủ uptime → RTT rồi slots → phân tích raw → cập nhật báo cáo/GitHub → sao lưu ZIP riêng → dừng workload. Chỉ dẫn mới lúc 16:43 ngày 13/10: người dùng tự dừng EC2, runner dùng `--leave-ec2-running` và không ghi stopped_verified khi máy vẫn running. Chế độ mặc định vẫn tự stop nếu được chọn lại. Giữ EBS/EIP/TGW theo quyết định người dùng; các tài nguyên này vẫn có thể phát sinh phí.

`scripts/start-confirmation-session.py --check` chỉ kiểm tra điều kiện offline; không khởi động tài nguyên. Lệnh không có `--check` bật cohort đã xác minh, không thu kết quả. Script từ chối attempt chưa hoàn tất và lỗi chưa được phân xử của block sắp đo. Không tự retry phép đo. Người điều phối thực hiện lựa chọn cleanup hiện hành, kể cả khi chuẩn bị/đo lỗi; không tự stop EC2 trong chế độ dừng thủ công.

`scripts/run-confirmation-session.py` chạy một phiên trọn vẹn với khóa `tmp/confirmation-session.lock`: chuẩn bị → RTT → slots → kiểm chứng truyền file/raw → cập nhật trạng thái → sao lưu trong finally; mặc định stop EC2, còn `--leave-ec2-running` dừng workload và để người dùng tự dừng máy. `--wait-until-due --prewarm-before-due` giữ khóa khi chờ, bật cohort khoảng 31 phút trước eligibility và revalidate đầy đủ trước collect; không đo trước spacing. Khi một phiên còn chạy, heartbeat chỉ đọc tiến độ; không mở phiên khác hay stop giữa phép đo. Trong chế độ tự stop, nếu SSM không khả dụng, cleanup kiểm tra account, đúng bốn ID/tag trước khi stop qua EC2 API. Trong chế độ thủ công, sao lưu local trước cleanup AWS; lỗi cleanup được báo cần xử lý, không giả nhận đã dừng. Lỗi đăng nhập không được báo thành công giả. Phụ lục Word và GitHub vẫn cần bước rà soát của heartbeat sau khi raw đã hợp lệ.

Raw tải sau cửa sổ đo qua SCP nếu có khóa tạm bảo vệ ACL. Host key lấy qua SSM đã xác thực, bật kiểm tra nghiêm ngặt; size/SHA đối chiếu và `.transport.json` giữ bằng chứng. Mã ứng dụng và protocol giữ nguyên. Khóa tạm trong `tmp/` không nằm trong ZIP công bố/GitHub; xóa bản sao tạm khi cuối phiên không còn tải file.

## Việc để chốt kết luận và bàn giao

1. Phiên cuối đã kết thúc; giữ dữ liệu hợp lệ và mọi lỗi, không tự retry.
2. RTT khi tải được hoãn, không ghi là đã đo.
3. Công bố mean/median/range và số block thực; không dùng kiểm định 16 block cho mẫu rút ngắn.
4. Ghép kết quả mới vào báo cáo chung, kiến trúc, công thức, bài giảng và related work; rà soát slide/demo.
5. Khi mọi việc hoàn tất, xóa heartbeat và báo người dùng tự dừng máy theo lựa chọn hiện hành; không tiếp tục đo tự động vô hạn.

[Tiêu chí bằng chứng và kết luận](30-bang-chung-va-tieu-chi-hoan-thanh.md) · [Protocol slots và công thức](27-can-thiep-slots-va-hang-doi.md) · [Phụ lục Word](31-phu-luc-bang-chung-thong-ke.docx) · [Báo cáo tổng hợp](34-bao-cao-tong-hop.md)

## Dữ liệu nguồn

- `results/confirmation-rtt-v1/analysis.json` — SHA256 `40a68e1647a54511a6747151ffdd8d3ac84f377e752130321aece36884173e7c`
- `results/application-slots-confirmation-v1/analysis.json` — SHA256 `8598caa32e5df0d904ca4650f295069652de1ec8fe8da2a6b76efe238b0564e2`
- `results/study-scope-decision-20261013.json` — SHA256 `fcdeae7fb4ff237e34d8bb9485b09517a5439ecd4cef2bd914fe98a06479ef45`
