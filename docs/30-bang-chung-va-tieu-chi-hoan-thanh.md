# Bằng chứng, kết luận và tiêu chí hoàn thành

Đồ án có hai câu hỏi xác nhận riêng: đường mạng ảnh hưởng RTT khi rảnh
thế nào, và tăng khả năng xử lý đồng thời của worker có khắc phục trễ hạn
ứng dụng trong workload đã đặt hay không. Hoàn thành nghĩa là thu đủ dữ liệu
theo thiết kế, kiểm chứng được phép tính và công bố kết quả dù giả thuyết
được hỗ trợ hay không. Không có tiêu chí "đo đến khi có kết quả đẹp".

## Bằng chứng hiện có và phạm vi sử dụng

| Phần | Bằng chứng | Kết luận được phép |
|---|---|---|
| Các bài vận chuyển ban đầu | RTT, TCP một cặp, hai cặp và fan-in; raw, CPU/ENA, kiến trúc | Mô tả kết quả trong các phiên đã thực hiện; không coi chúng là 16 block xác nhận |
| Pilot/calibration ứng dụng | 62.200 yêu cầu; 600/800/1.000 rps | Xác định vùng tải và kiểm tra công cụ; không gộp vào kiểm định xác nhận |
| Engineering slots | 84.000 yêu cầu, queue logs ghép ID, CPU/ENA và route | Ở 800 rps, 8 → 16 slots nâng đúng hạn từ 3,6% lên 100% qua Peering, từ 3,2% lên 100% qua TGW trong phiên này |
| Xác nhận RTT | Trạng thái tính lại tại `results/confirmation-rtt-v1/analysis.json` | Chỉ đưa kết luận suy diễn khi đủ 16 block và tiêu chí chất lượng/ngày |
| Xác nhận slots | Trạng thái tính lại tại `results/application-slots-confirmation-v1/analysis.json` | Engineering không đóng góp block; áp dụng đủ 16 block riêng |

Các số liệu engineering và dấu vết lỗi tải log đã phục hồi được trình bày
trong [tài liệu 29](29-ket-qua-engineering-slots.md). Không biến một phiên
engineering thành xác nhận sau khi đã thấy hiệu ứng.

[Audit 30 JSON fan-in cũ](../results/analysis/fanin-common-window-audit.json)
xác nhận các interval là phía gửi, phía nhận có tổng byte/thời lượng và
server text. Thiếu receiver interval bytes cùng mốc thời gian đủ chính xác
để xác định byte nhận trong một cửa sổ chung. Giữ tổng goodput xấp xỉ của
các cửa sổ riêng; không nội suy sender bytes thành receiver bytes.

## Khi nào được kết luận xác nhận?

Mỗi nghiên cứu phải có đủ **16 block hợp lệ, ít nhất bốn ngày địa phương**,
các thời điểm bắt đầu cách nhau ít nhất hai giờ. Thứ tự mạng/điều kiện đã
khóa; giữ cohort, MTU 1500 và môi trường đã định. Kiểm tra raw trước khi
nhận block. Lỗi kỹ thuật được giữ lại và xử lý có lý do, không chọn lại
phiên vì chênh lệch nhỏ, outlier hay p-value chưa đạt.

Ký hiệu cho nghiên cứu RTT:

\[
\Delta_j=\overline{RTT}_{TGW,j}-\overline{RTT}_{Peering,j},\quad
Z_j=\mathbf{1}\{\Delta_j>0{,}1\ \mathrm{ms}\}.
\]

Ký hiệu cho nghiên cứu slots, tại 800 yêu cầu/s:

\[
p_{m,c,j}=\frac{\text{số yêu cầu hoàn tất đúng hạn 50 ms}}
{\text{tổng yêu cầu theo lịch}},\qquad
d_j=\frac{(p_{P,16,j}-p_{P,8,j})+(p_{T,16,j}-p_{T,8,j})}{2},
\quad Z_j=\mathbf{1}\{d_j>0{,}10\}.
\]

Ở đây \(j\) là block; \(m\) là mạng (\(P\): Peering, \(T\): TGW);
\(c\) là slots **trên mỗi worker**; \(p\) và \(d\) là tỷ lệ không đơn vị.
\(0{,}10\) là 10 điểm phần trăm, không phải tăng tương đối 10%.
Lỗi/timeout/yêu cầu không gửi được vẫn thuộc mẫu số theo lịch.

Trong từng nghiên cứu, \(K=\sum_{j=1}^{16}Z_j\),
\(\theta=P(Z_j=1)\). Kiểm định chính là
\(H_0:\theta\le0{,}5\) so với \(H_1:\theta>0{,}5\):

\[
p_{\mathrm{exact}}=\sum_{k=K}^{16}\binom{16}{k}2^{-16}.
\]

Ngưỡng đã khóa: ít nhất **12/16 block** vượt biên có ý nghĩa thực tế,
với p-value tại K = 12 bằng **0,0384063721**. Đây là phép tính thiết kế,
không phải p-value thực nghiệm hiện tại. Vẫn phải thu cả 16 block, kể cả
khi đã có 12 block vượt biên. Cỡ mẫu suy diễn là block, không phải hàng
chục nghìn request tương quan trong một phiên. Giả định về quá trình lấy
mẫu và độc lập đủ giữa block phải được công bố; khoảng cách hai giờ không
tự chứng minh độc lập.

Hai kiểm định chính dùng mức 0,05 **riêng cho từng câu hỏi**, như protocol
đã khóa. Không diễn giải thành bảo đảm đồng thời 95% cho tất cả nhận định
trong đồ án. Các đối chiếu mạng/queue và CI bootstrap phụ trợ là mô tả,
không sinh thêm chuỗi kiểm định rồi chỉ chọn kết quả thuận lợi.

## Cách viết kết luận sau khi đủ dữ liệu

Nếu đạt tiêu chí, báo cáo ghi số block vượt biên, độ lớn hiệu ứng, p-value
exact, cận dưới xác suất một phía 95% và điều kiện thí nghiệm. Nghiên cứu
RTT còn có cận dưới median chênh lệch; nghiên cứu slots có CI bootstrap
theo **toàn block** cho hiệu ứng trung bình, ghi rõ là kết quả phụ trợ.
Không lấy CI bằng resampling từng request để tạo cỡ mẫu giả.

Nếu không đạt tiêu chí, kết luận là thiết kế này chưa cung cấp đủ bằng
chứng cho giả thuyết đã định. Điều đó không chứng minh hai cấu hình tương
đương hoặc không có hiệu ứng. Kết quả âm vẫn là kết quả hoàn chỉnh nếu
thực hiện đúng thiết kế, có dữ liệu và giải thích được giới hạn.

ASA lưu ý p-value không phải xác suất giả thuyết đúng và không thể tự
thay thế độ lớn hiệu ứng hay lập luận khoa học. Vì thế một kết luận mạnh
phải phối hợp thiết kế, số liệu, kiểm tra cơ chế và phạm vi áp dụng.
Nguồn: [ASA Statement, 2016](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf).

## Đóng góp khoa học và liên hệ bài giảng

RTT đo vòng đi-về ở tầng mạng. Deadline/P95 ứng dụng đo thời gian hoàn
thành cả chuỗi A → B → C/D. Queue logs kiểm tra thời gian chờ và phục vụ
bằng đồng hồ monotonic trên từng worker; CPU/ENA hỗ trợ chẩn đoán điểm
nghẽn. Các đại lượng này không cùng tầng và không thay thế nhau.

Trong engineering, đổi đường mạng ở 8 slots/800 rps vẫn để phần lớn yêu
cầu trễ hạn; tăng slots trong từng mạng làm chờ hàng đợi giảm rõ trong
khi thời gian phục vụ vẫn cùng cỡ 10–11 ms. Đây là bằng chứng cơ chế trong
ứng dụng mô phỏng có giới hạn đồng thời đã biết, cần xác nhận lặp lại.
Không dùng nó để phát hiện giới hạn nội bộ AWS hoặc tuyên bố một nguyên
nhân duy nhất cho mọi hệ thống.

[The Tail at Scale — Dean và Barroso, 2013](https://research.google/pubs/the-tail-at-scale/)
đặt vấn đề về độ trễ đuôi khi mức sử dụng và độ phức tạp dịch vụ tăng.
Đồ án vận dụng câu hỏi đó vào một ứng dụng hai worker nhỏ, không tuyên
bố tái tạo quy mô hay chứng minh các kỹ thuật của bài báo. Liên hệ các
bài giảng về arrivals/queueing, congestion và QoS/metrics xem
[tài liệu 17](17-doi-chieu-bai-giang-va-cong-cu.md) và
[tài liệu 24](24-co-so-khoa-hoc-thong-ke-va-observability.md).

OpenTelemetry giúp theo dõi các lời gọi phân tán và minh họa phiên demo.
Nó không thay cho thiết kế lấy mẫu, raw request, queue logs hay kiểm định;
tracing đầy đủ tắt trong so sánh chính để giữ điều kiện giống nhau.

[Phân tích hàng đợi và công thức Little từ raw](33-hang-doi-va-dinh-luat-little.md)
bổ sung kiểm tra sample path: tích phân số đang chờ bằng tổng thời gian chờ
của cohort chứa trọn entry/exit. Phần này giải thích định lượng cơ chế,
không phải kiểm định mới hoặc bằng chứng độc lập với chính log đã dùng.

## Công việc để bàn giao trọn vẹn

1. Thu các block xác nhận còn thiếu; phân tích lại sau từng block, không
   chạy hai nghiên cứu cùng lúc. Không rút ngắn khoảng cách để xong nhanh.
2. Sau đủ 16 block RTT, chạy phần RTT khi tải đã định và ghi là thăm dò.
3. Chốt bảng hiệu ứng/CI/p-value từ raw; công bố mọi lỗi và mọi block hợp lệ.
4. Ghép kiến trúc, công thức, nguồn bài giảng/nghiên cứu, kết quả vận chuyển
   và ứng dụng vào báo cáo thống nhất; tách rõ lịch sử và xác nhận mới.
5. Kiểm tra demo quan sát, sao lưu dữ liệu, công bố code/raw đã rà soát lên
   nhánh `minh-work`; giữ state, credentials, khóa SSH và ZIP riêng tư.

Không cần thêm công cụ chỉ để làm đồ án trông lớn hơn. Việc còn thiếu quyết
định sức mạnh thống kê là các lần lặp đúng thiết kế và diễn giải trung thực.
Khi hoàn tất, vẫn ghi phạm vi cùng loại máy/AZ/workload đã thử; đây là độ
chặt chẽ của kết luận, không phải một phần việc chưa làm xong.
