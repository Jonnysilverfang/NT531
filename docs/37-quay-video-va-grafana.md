# Demo NT531: quay gì và mở Grafana như thế nào?

Mục tiêu video 4–5 phút: cho thấy mô hình chạy được, kết quả trả lời câu hỏi và nhóm hiểu cơ chế. Đây là gợi ý nội dung; chưa xác nhận giảng viên bắt buộc thời lượng hay định dạng video này.

## Trạng thái hiện tại

Bộ local riêng tên `nt531-observability`: Collector → Tempo → Grafana cho traces, Collector → Prometheus → Grafana cho metrics. Docker Desktop có thể chạy thêm bộ OpenTelemetry Astronomy hoặc project khác; dashboard NT531 là **localhost:3000**, không dùng số liệu của project khác để trình bày đồ án AWS này.

Trace có sẵn từ hai phiên smoke trên AWS: **12 trace, 120 span**, mỗi trace có 10 span qua A/B/C/D. Nhập lại giữ nguyên trace ID, span ID và thời gian gốc. Smoke có tải nhẹ để kiểm tra truyền context; không phải trace của điều kiện 800 rps trong ba block chính. Vì vậy nó minh họa luồng gọi, không chứng minh backlog lớn khi tải. Số liệu backlog lấy từ log hàng đợi của phiên so sánh.

Hostmetrics agent trên EC2 chưa triển khai. Dashboard CPU/network có thể không có dữ liệu; không đọc thành CPU/network bằng 0. CPU trong báo cáo lấy từ mpstat, ENA lấy từ ethtool. Chưa cần thêm một phiên AWS để quay phần kết quả và trace đã lưu.

## Mở lại bộ demo

Tại thư mục dự án, dùng PowerShell:

```powershell
docker compose -f monitoring/compose.yaml up -d
& 'C:/Users/MSI/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 monitoring/prepare-demo.py --replay
```

Python chỉ phân tích file và nhập trace vào Collector local; không bật EC2, đổi route hay thu block mới. Script tạo dashboard từ dữ liệu đã chốt, kiểm tra source SHA, cây parent/child, đủ bốn service instance, 12 trace và 10 span duy nhất mỗi trace qua Grafana proxy. Bằng chứng mới ghi riêng trong [current-demo.json](../results/observability-demo/current-demo.json), không ghi đè raw hoặc bằng chứng smoke gốc.

Mở [dashboard kết quả và công thức](http://localhost:3000/d/nt531-study-demo). Đăng nhập user `nt531`; mật khẩu riêng nằm trong `monitoring/.env` trên máy. Không quay mật khẩu/file `.env` và không đưa chúng lên GitHub.

Dashboard đã đặt **khoảng thời gian tuyệt đối của trace gốc**, không mặc định “15 phút vừa qua”. Nếu sửa bộ lọc về hiện tại, trace cũ sẽ biến mất khỏi danh sách dù vẫn truy vấn được bằng ID. Không đổi timestamp cũ sang giờ hiện tại để làm như dữ liệu live. Tempo local giữ 30 ngày (720 giờ), đủ để giữ timestamp ngày 12/10 tới buổi báo cáo 26/10. Nếu dữ liệu local bị mất trong khoảng này, chạy lại lệnh replay. Sau thời hạn retention, cần điều chỉnh retention cho phiên lưu trữ thay vì đổi timestamp gốc.

Kết quả script in URL có thời gian cụ thể, cũng lưu trong current-demo.json. Collector chờ batch/index vài giây trước khi truy vấn. Chỉ tuyên bố demo hoạt động sau khi `runtime_verified` là true.

## Kịch bản quay 4–5 phút

| Thời lượng | Cảnh quay | Nói điều gì? |
|---|---|---|
| 0:00–0:40 | Sơ đồ bốn VPC Peering và TGW | Cùng bốn EC2, sáu Peering hoặc một TGW/bốn attachment; tải dùng IP private |
| 0:40–1:20 | Bảng RTT và topology/route proof đã lưu | Trong 5 block, TGW trừ Peering trung bình +0,3119 ms; đây là kết quả đo có phạm vi |
| 1:20–2:20 | Dashboard bảng 800 rps, 8/16 slots | Hai mode ở 8 slots chỉ khoảng 3% đúng hạn; 16 slots đạt 100% trong các cửa sổ đã đo |
| 2:20–3:05 | Hàng đợi/Little trên dashboard và đồ thị block 3 | Giải thích tốc độ × thời gian chờ = số lời gọi chờ trung bình; thế ví dụ 732 × 0,701 ≈ 513 |
| 3:05–4:05 | Chọn một Trace ID, mở chi tiết trên Grafana | A → B → C/D; hai lời gọi song song; worker.queue và worker.service; phân biệt trace, span và RTT mạng |
| 4:05–4:40 | Bảng kết luận và file raw | Network và khả năng phục vụ đều quan trọng; cho thấy file kết quả có nguồn và phép tính tái tạo |

Những cảnh dùng dữ liệu cũ ghi **“Kết quả đã đo”** hoặc **“Trace thật đã lưu — replay”**. Có thể cắt đoạn chờ/nghỉ; không chỉnh số liệu hoặc dựng màn hình như một phiên live. Nếu giảng viên yêu cầu thao tác trực tiếp AWS, mới chuẩn bị phiên demo riêng có giới hạn thời gian; không đưa request demo vào dataset đã chốt.

## Đọc trace sao cho đúng

- Trace: toàn bộ hành trình của **một yêu cầu**; các span dùng chung trace ID.
- Span: một đoạn công việc có mốc bắt đầu/kết thúc và parent. A là `nt531-load`, B là `nt531-gateway`; C/D đều là `nt531-worker`, phân biệt bằng `service.instance.id`.
- B gọi C và D song song: không cộng thời gian hai nhánh như chúng chạy nối tiếp. Tổng thời gian chịu ảnh hưởng nhánh kết thúc muộn và overhead gateway/đường đi.
- Span RPC gồm truyền thông và xử lý ở phía kia, không phải phép đo độ trễ mạng thuần. Không dùng trace để phân rã hàng đợi nội bộ TGW.
- `worker.queue` là chờ lấy slot ở ứng dụng; `worker.service` là phần phục vụ mô phỏng. Trace smoke tải nhẹ có thể chờ rất ít; dùng log của block chính để trình bày hàng đợi ở tải 800 rps.

Liên hệ trực tiếp slide Internet Performance, trang 31/34/39: metrics cho cái nhìn tổng hợp, logs cho sự kiện cụ thể, traces nối hành trình qua dịch vụ. Nhóm đã dùng raw logs, trace và dashboard; chưa triển khai Loki hoặc hostmetrics EC2, nên không ghi đã triển khai toàn bộ mọi thành phần trên slide.

## Công thức cần học trước khi quay

Đọc [công thức bám bài giảng](36-cong-thuc-bam-bai-giang.md): mỗi công thức có câu hỏi, ký hiệu, đơn vị và ví dụ từ số liệu thật. Dùng Little, P95, SLI và chênh lệch; để phần tích phân và kế hoạch kiểm định 16 block trong phụ lục.

Tài liệu vận hành chi tiết: [monitoring README](../monitoring/README.md). Dừng bộ local khi không dùng:

```powershell
docker compose -f monitoring/compose.yaml down
```

Lệnh này chỉ dừng bộ NT531 local, giữ volumes và không dừng EC2. Không dùng `down -v` khi còn muốn giữ dữ liệu. Bật/tắt bộ demo local không làm phát sinh thêm EC2/TGW; trạng thái AWS cần kiểm tra riêng nếu muốn dừng phí AWS.
