# Bước xác nhận tiếp theo — bản thiết kế, chưa chạy

Cập nhật 12/10: đã khóa protocol riêng **16 block** theo kiểm định exact
một phía và margin 10 điểm phần trăm. Đây là thiết kế chính thay cho đề xuất
12 phiên dưới đây; xem [tài liệu 27](../../docs/27-can-thiep-slots-va-hang-doi.md)
và [protocol](../../results/application-slots-confirmation-v1/protocol.json).
Phần dưới giữ như lịch sử thiết kế; không coi đề xuất 12 phiên/margin
tương đương mạng là tiêu chí đang dùng. Engineering không phải block xác nhận.

Pilot và calibration ngày 12/10 đã tìm vùng tải ứng dụng bắt đầu trễ,
không dùng lại chúng như dữ liệu xác nhận. Xem [báo cáo](../../docs/26-ket-qua-pilot-ung-dung.md).

## Hai câu hỏi tách biệt

1. Giữ workload cố định: đổi đường mạng làm thay đổi tỷ lệ đúng hạn bao
   nhiêu ở tải hữu ích và gần bão hòa?
2. Giữ tải/đường mạng cố định: tăng slots worker có cải thiện đúng hạn
   và giảm thời gian chờ hay không? Can thiệp này kiểm tra giả thuyết
   nghẽn ứng dụng, thay vì đo lặp để chỉ nhìn lại cùng số.

## Thiết kế dự kiến để đóng băng trước dữ liệu mới

- Factor mạng: Peering/TGW; slots mỗi worker: 8/16; tải: 600/800 yêu cầu/s.
  Hai worker luôn cùng số slots; giữ delay 10 ms, payload 4096, MTU 1500,
  deadline 50 ms, timeout 2 s, in-flight/FD thống nhất mọi điều kiện.
- 8 tổ hợp/phiên. Đề xuất 12 phiên trên ít nhất 4 ngày, cách nhau ≥2 giờ.
  Đây là ngân sách thiết kế, chưa có tính công suất thống kê; cần chốt
  số phiên từ độ chính xác effect size mong muốn và ngân sách thực tế.
- Ngẫu nhiên có cân bằng thứ tự mạng và thứ tự tải/slots trong phiên.
  Khởi động lại ứng dụng giữa điều kiện, kiểm tra hết backlog, warm-up
  nhất quán; không cho thời điểm trước ảnh hưởng điều kiện sau.
- Dự kiến warm-up 5 s + đo 15 s mỗi tổ hợp. Phải kiểm tra drain, ổn định
  và giới hạn generator trước khi khóa protocol; quá tải vẫn là phép đo
  cửa sổ hữu hạn, không tuyên bố trạng thái dừng.
- Đơn vị độc lập để suy luận là **phiên**, không phải từng request.
  Trong mỗi phiên, Δp_network = p_TGW − p_Peering ở cùng tải/slots;
  Δp_slots = p_16 − p_8 ở cùng tải/mạng. Đơn vị điểm phần trăm khi nhân 100.
- Outcome chính: tỷ lệ phản hồi đúng hạn trên mọi yêu cầu đã lập lịch.
  P95 thành công, failure fraction, dispatch lag, CPU từng lõi và ENA
  là outcome phụ/chẩn đoán; giữ lỗi và timeout trong mẫu số.

## Phân tích và quy tắc kết luận

Tính trung bình chênh lệch qua phiên và CI 95% bằng resampling nguyên phiên,
giữ tất cả tổ hợp của một phiên cùng nhau. Bootstrap ít phiên vẫn có hạn
chế: công bố toàn bộ chênh lệch từng phiên và độ nhạy phương pháp; không
dùng hàng nghìn request trong một phiên làm tăng giả số mẫu độc lập.
Nếu kiểm định nhiều tương phản phải khóa primary contrast hoặc quy tắc
hiệu chỉnh trước. Chưa tạo p-value từ pilot.

Một margin dự kiến để thảo luận là ±1 điểm phần trăm đúng hạn ở 600 rps,
và cải thiện ≥10 điểm phần trăm khi tăng slots ở 800 rps. Đây là tiêu chí
nghiệp vụ **đề xuất**, phải giải thích/chốt trước dữ liệu xác nhận; không
đổi sau khi biết CI. Muốn kết luận tương đương mạng, CI phải nằm trọn
trong margin đã chọn; p>0,05 không đủ. CI của Δp_slots vượt ngưỡng cải
thiện đặt trước mới hỗ trợ lợi ích có ý nghĩa thực tế của can thiệp.

Ghi thêm queue-enter/service-start/service-end dạng counter/timestamp nhẹ
tại worker trong mọi tổ hợp để kiểm tra chờ và thời gian phục vụ. Định
nghĩa overhead và xác minh logger không nghẽn trước protocol; không so
một mode tracing-on với mode kia tracing-off. Tracing đầy đủ vẫn chạy
riêng cho demo; chưa dùng trace tải thấp hiện có như bằng chứng overload.

Phương án rollback: generator mất lịch, route sai hoặc cleanup lỗi thì giữ
attempt, ghi lý do, không âm thầm bỏ các kết quả xấu. Hỏng generator là
lỗi đo; ứng dụng timeout với generator hợp lệ là outcome cần giữ.

## Quan hệ với kế hoạch RTT

Protocol RTT đã khóa giữ nguyên, hiện 2/16 blocks. App/monitor phải tắt trước
block RTT. Nghiên cứu ứng dụng là câu hỏi khác, có protocol riêng; không
gộp HTTP latency vào mẫu ICMP. Loaded RTT giữ tùy chọn, không mở thêm một
loạt phép đo khi chưa hoàn thành câu hỏi chính này.
