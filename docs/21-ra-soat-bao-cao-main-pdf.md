# Rà soát bản PDF người dùng gửi — 12/10/2026

## Phiên bản và phạm vi

Nguồn: `main.pdf` người dùng cung cấp, 27 trang PDF;
SHA256 `99f0babd2ce47888767eb2783473977e2ea6906a23834cbc7a24223900c2ef62`.
Số trang PDF dưới đây tính từ trang bìa; khác số trang in trong báo cáo.
Đã đọc toàn bộ nội dung trích xuất và xem trực quan trang 12, 20, 23 liên quan
đến thống kê, chênh lệch và future work. Đây không phải audit bố cục mọi trang.
Không sửa hoặc ghi đè PDF gốc; không có phép đo AWS mới.

PDF được gửi khác phiên bản `report/main.pdf` và source đang trên GitHub.
Ví dụ source ở commit `c2301aa` đã dùng 3.7875% với mẫu số TGW trong bài
single-flow; PDF người dùng gửi còn câu diễn giải 3.65% không đúng mẫu số.
Không thay PDF trong repo bằng file gửi này để tránh lùi phiên bản.

## Kết luận về nhận xét thiếu thống kê

Nhận xét **đúng về thiếu phân bố và suy luận**, nhưng nói báo cáo không có
thống kê là quá rộng: mục 2.8, trang PDF 12 có mean, SD, CV và Jain; chương 5
đã có bảng số và phân biệt quan sát với giới hạn dịch vụ. Đây là thống kê mô
tả, chưa có phân tích xác suất và chưa thực hiện kiểm định theo đợt độc lập.

Bản này ở trang PDF 23 vẫn đưa P50/P95/ECDF và TCP cwnd/RTT vào future work.
Vì vậy người đọc bản PDF không nhìn thấy các phân tích mới đã làm offline.
Giải pháp là đưa kết quả từ [phần bổ sung](20-thong-ke-va-xac-suat.md) vào đúng
chương, rồi build/render lại; không chỉ thêm nhiều công thức vào lý thuyết.

## Những chỗ cần sửa trước bản nộp

| Vị trí | Vấn đề | Cách sửa cụ thể |
|---|---|---|
| Mục 2.8, trang PDF 12 | Chỉ có thống kê mô tả; chưa định nghĩa biến/mẫu/phân bố | Thêm biến RTT X, chỉ báo vượt ngưỡng, ECDF và quy tắc nearest-rank; ghi n=500 phản hồi mỗi mode khác m=5 lượt |
| Mục 5.1, trang PDF 19 | Chỉ trình bày RTT mean; không thấy phần đuôi | Thêm ECDF, P50/P95/P99 và bảng tần suất; giữ bảng mean cũ với nguồn summary avg |
| Mục 5.2, trang PDF 19–20 | Công thức lấy Peering làm mốc nhưng câu sau nói Peering cao hơn 3.65% | Nếu lấy Peering làm mốc: “TGW thấp hơn 3.65%”; nếu nói “Peering cao hơn TGW”: dùng TGW làm mốc, được 3.79% |
| Mục 5.3 và cơ sở TCP | Có retransmits, chưa khai thác RTT/cwnd có sẵn | Thêm hình TCP RTT/cwnd/sender rate theo thời gian; giữ nhãn sender khác receiver goodput |
| Mục 5.7–5.8, trang PDF 22–23 | Các đợt lặp và phân tích log cũ chưa tách rõ | Đánh dấu ECDF/phân vị/TCP một luồng đã tính offline; RTT khi tải và đợt lặp vẫn chưa thực hiện |
| Bìa, trang PDF 1 | TODO mã lớp, giảng viên, họ tên/MSSV | Điền theo thông tin nhóm được xác nhận; không suy đoán từ Git username/email |

Mỗi kết quả mới cần một chuỗi rõ: câu hỏi → biến/mẫu → công thức → số liệu →
điều kiện áp dụng. Khi nhắc slide, chỉ ra phần tương ứng thay vì ghi chung
“vận dụng kiến thức môn học”. Xem bảng ánh xạ bài giảng ở tài liệu 20.

## Số mới có thể đưa vào ngay, không cần chạy AWS

| Đại lượng từ các RTT hiển thị | Peering | TGW |
|---|---:|---:|
| P50 (ms) | 0.208 | 0.517 |
| P95 (ms) | 0.227 | 0.638 |
| P99 (ms), mô tả phiên | 0.239 | 0.880 |
| Phản hồi RTT > 1 ms | 0/500 (0%) | 4/500 (0.8%) |

Ngưỡng 1 ms được chọn sau khi có dữ liệu: chỉ là ngưỡng khám phá, chưa phải
SLO đăng ký trước hoặc SLA AWS. P99 với 500 phản hồi còn ít thông tin ở đuôi.
Mean của RTT hiển thị hơi khác mean từ summary của ping do độ chính xác đầu
ra; không thay số cũ để ép khớp. Tài liệu 20 giải thích rõ hai cách tính.

Một ví dụ xác suất có điều kiện: nếu probe độc lập Bernoulli với xác suất
không phản hồi cố định p, quan sát 0/500 cho cận trên một phía 95%
`p_U = 1 - 0.05^(1/500) ≈ 0.597355%`. Giả định iid chưa được xác nhận cho
trace này; không gọi đây là cận đảm bảo SLA của AWS. Nó minh họa vì sao
“không quan sát lỗi” khác “xác suất lỗi bằng không”.

Script mới đã kiểm SHA256 20 file đầu vào; kiểm chứng độc lập có 645 kiểm tra
đạt bằng NumPy phân vị inverted_cdf, SD ddof=1, byte/thời lượng interval và
hash nguồn. Bảng kết quả cũ và raw không thay đổi. Có hai hình PNG/SVG,
10 JSON TCP một luồng với tổng 300 interval không omitted.

## Còn cần lấy thêm dữ liệu để làm gì?

Đợt b phải có cả hai mode với thứ tự cân bằng, sau đó so chênh lệch theo đợt.
Đây là bước cần cho CI/kiểm định có điều kiện hợp lý và đánh giá tái lập, không
phải để làm một bảng có nhiều dòng. Không ghép tùy ý lượt cùng số của hai phiên
cũ hoặc coi 500 gói là 500 thí nghiệm độc lập.

Chốt đầu ra chính, số đợt, phương pháp, độ chính xác mong muốn và ngân sách
trước khi chạy. Bốn đợt cũ là mức khởi đầu, không bảo đảm công suất thống kê.
RTT khi tải là bài tiếp theo liên hệ congestion/queueing; chưa cần dựng lại
topology hoặc ép traffic hiện tại thành Poisson/M/M/1.

## Gói nội dung để ghép báo cáo

- [Công thức, ký hiệu, phân bố, bảng và giới hạn suy luận](20-thong-ke-va-xac-suat.md).
- [ECDF RTT](images/statistics/01-rtt-ecdf.png).
- [TCP theo thời gian](images/statistics/02-tcp-trajectories.png).
- [Số liệu và SHA256 đầu vào](../results/analysis/statistics-probability.json).
- [Kiểm chứng độc lập](../results/analysis/statistics-probability-verification.json).

Phần bổ sung đã hoàn thành ở dạng Markdown/hình/JSON; chưa được ghép vào
PDF 27 trang được gửi hoặc chương DOCX 19 trang. Không coi bản PDF hiện tại
là bản nộp đã chốt. Source LaTeX trong `report/` cần ghép phần mới và build lại
trong môi trường nhóm đang dùng; máy kiểm tra hiện chưa có compiler TeX.
