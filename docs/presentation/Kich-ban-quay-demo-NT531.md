# Kịch bản quay demo NT531

Mục tiêu: video khoảng 5 phút đi cùng bộ slide 10–12 phút. Video thể hiện kiến trúc, cách đọc dữ liệu và trace. Bộ dữ liệu nghiên cứu đã chốt nên không cần chạy lại toàn bộ block để quay. Các lệnh dưới đây là hướng dẫn chuẩn bị và thao tác, chưa được thực thi trong lúc tạo slide.

## Chuẩn bị

1. Mở [PowerPoint](NT531-thuyet-trinh.pptx), [lời thoại](Loi-thoai-NT531.md) và dashboard Grafana. Tập nói một lượt trước khi quay.
2. Dùng cửa sổ 16:9, chữ terminal đủ lớn, đóng thông báo. Đăng nhập trước khi bấm quay. Giữ mật khẩu và khóa riêng ngoài khung hình.
3. Chọn quay dữ liệu đã lưu, hoặc bổ sung đoạn kiểm tra trực tiếp 4 EC2 nếu các máy đang chạy. Không cần bật AWS chỉ để mở dashboard local.
4. Chuẩn bị nhãn trên video: **“Kết quả đã đo ngày 12–13/10/2026”**, **“Trace smoke thật đã lưu, replay”**, hoặc **“Kiểm tra trực tiếp tại thời điểm quay”** theo đúng cảnh.

Trong PowerShell tại thư mục dự án, mở bộ local bằng:

```powershell
docker compose -f monitoring/compose.yaml up -d
& 'C:/Users/MSI/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 monitoring/prepare-demo.py --replay
```

Mở URL dashboard do script in ra. Chỉ quay sau khi script xác nhận `runtime_verified: true`. Đây là pipeline local, không đo lại AWS. Nếu dùng máy khác, thay đường dẫn Python bằng môi trường đã cài các thư viện theo [hướng dẫn monitoring](../../monitoring/README.md).

## Cảnh quay và lời nói

### 0:00–0:45 · Kiến trúc

**Màn hình:** slide 3, rồi slide 4.

**Lời nói:** “Nhóm dùng bốn VPC, mỗi VPC một EC2. Peering full mesh cần sáu kết nối cặp, còn Transit Gateway dùng một hub và bốn attachment. Các phép đo dùng IP private, Elastic IP phục vụ SSH. Với ứng dụng, A tạo tải đến B, B gọi hai worker C và D song song rồi trả kết quả. Nhóm giữ nguyên máy khi đổi đường mạng để so sánh.”

### 0:45–1:30 · Kết quả RTT

**Màn hình:** slide 7 hoặc bảng RTT trên dashboard. Chỉ từng cặp cột, đơn vị ms và số block.

**Lời nói:** “Đây là kết quả đã đo trong năm block. Mỗi block chứa cả Peering và TGW. Nhóm lấy RTT TGW trừ Peering trong cùng block, trung bình khoảng 0,312 ms. Cả năm chênh lệch đều dương. Peering có RTT thấp hơn trong cấu hình này. Ba nghìn probe không thiếu phản hồi. RTT là toàn bộ hành trình đi và về, nên chưa thể gọi chênh lệch này là thời gian xử lý nội bộ TGW.”

### 1:30–2:25 · Can thiệp khả năng phục vụ

**Màn hình:** slide 8–9 hoặc bảng 800 rps trên dashboard.

**Lời nói:** “Ở 800 yêu cầu mỗi giây và tám slots, cả hai đường mạng chỉ có khoảng ba phần trăm yêu cầu hoàn thành trong deadline 50 ms. Tăng lên mười sáu slots thì cả hai đạt 100% trong các cửa sổ đã đo. Hiệu ứng tăng slots trung bình qua ba block là 96,84 điểm phần trăm. P95 giảm từ khoảng 1,2–1,5 giây về khoảng 13 ms. Đổi đường mạng vẫn không khắc phục được thiếu khả năng phục vụ trong workload này.”

### 2:25–3:10 · Little và hàng đợi

**Màn hình:** slide 10, rồi mục Little trên dashboard nếu muốn.

**Lời nói:** “Little liên hệ số lời gọi chờ trung bình với tốc độ và thời gian chờ trung bình. L q bằng lambda nhân W q. Với worker C, Peering, tám slots, block ba: khoảng 732 lời gọi mỗi giây nhân 0,701 giây cho khoảng 513 lời gọi chờ. Tốc độ này tính trên toàn bộ nhóm lời gọi và đuôi xử lý. Đây là kiểm tra tính nhất quán của log, không phải một kiểm định thống kê độc lập. Với mười sáu slots, thời gian chờ trung bình của trường hợp này chỉ khoảng 0,00524 ms.”

### 3:10–4:20 · Trace thật trên Grafana

**Màn hình:** dashboard `nt531-study-demo`, bấm một Trace ID để mở timeline. Mở hai nhánh C/D và các span `worker.queue`, `worker.process`.

**Lời nói:** “Nhóm có mười hai trace smoke thật đã lưu, tổng một trăm hai mươi span. Collector nhận trace, Tempo lưu và Grafana hiển thị. Một trace là hành trình của một yêu cầu. Các span là từng đoạn công việc có quan hệ cha con. Hai nhánh gọi worker chồng nhau về thời gian, thể hiện chạy song song. Yêu cầu này hoàn thành khoảng 12,31 ms. Đây là tải nhẹ được replay giữ nguyên ID và thời gian, không phải trace của điều kiện 800 rps. Log hàng đợi của phiên chính mới cung cấp bằng chứng backlog khi tải.”

Trace minh họa đã kiểm tra: `2d6ab3013099ca64a169b001dbc70081`. Khoảng tìm kiếm dùng thời gian gốc ngày 12/10. Hướng dẫn chi tiết và ảnh dự phòng tại [tài liệu Grafana](../37-quay-video-va-grafana.md). Nếu dashboard CPU trống, giải thích hostmetrics EC2 chưa bật. CPU nghiên cứu lấy từ mpstat.

### 4:20–5:00 · Kết luận và nguồn

**Màn hình:** slide 13–14, rồi thư mục kết quả hoặc repository ở nhánh `minh-work`.

**Lời nói:** “Kết quả cho thấy Peering có lợi thế RTT trong cấu hình đã đo. TGW có topology hub và định tuyến tập trung theo tài liệu AWS. Với ứng dụng gần công suất, tăng slots cải thiện deadline rõ ở cả hai mode. Nhóm lưu raw, giao thức đo, phép tính và log để kiểm chứng. Phạm vi là năm block RTT và ba block ứng dụng. Đây là thống kê mô tả, không kết luận một phương án thắng mọi hệ thống.”

## Đoạn trực tiếp tùy chọn, khoảng 30–45 giây

Có thể thay một phần cảnh kiến trúc bằng Termius bốn ô. Trong từng máy, chạy:

```bash
hostname
ip -br addr
cat /sys/class/net/ens5/mtu
```

Trên A, thử kết nối private đến B và lưu riêng kết quả demo:

```bash
mkdir -p ~/nt531-demo
demo_dir=$(mktemp -d ~/nt531-demo/connectivity-XXXXXX)
ping -n -c 20 -i 0.2 10.20.10.155 | tee "$demo_dir/ping.txt"
echo "Demo saved: $demo_dir"
```

**Lời nói:** “Đây là kiểm tra kết nối trực tiếp tại thời điểm quay, không bổ sung vào năm block nghiên cứu.” Không gọi tên đường mạng chỉ dựa vào terminal hoặc ping. Đối chiếu route đang hoạt động trước khi nói Peering/TGW. Terraform output là thông tin state, muốn chứng minh hiện trạng cần kiểm tra route trên AWS.

Không đổi route hoặc chạy hai script tạo tải đồng thời chỉ để có hình chuyển động. Nếu có yêu cầu demo chuyển mode, chuẩn bị một phiên riêng và kiểm tra trước khi quay.

## Sau khi quay

- Xem lại từ đầu tới cuối, kiểm tra chữ, âm thanh, nhãn dữ liệu lịch sử và đoạn trace. Chưa đánh dấu đã quay khi mới có kịch bản.
- Giữ video gốc và bản nộp trong hai nơi. Nếu muốn giảm phí, kiểm tra backup rồi stop hoặc dọn hạ tầng AWS theo quyết định riêng. Bộ slide không tự dừng hay xóa EC2.
- Dừng bộ Docker NT531 khi không dùng bằng `docker compose -f monitoring/compose.yaml down`. Lệnh này giữ volumes, không dừng AWS.
- Mở PowerPoint ở Presenter View. Notes có lời thoại của 18 trang, trong đó 14 trang chính khoảng 11 phút và 4 trang phụ lục cho câu hỏi.
