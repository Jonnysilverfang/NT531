# Chương kết quả và biểu đồ từ sáu bộ đo chính

Đã hoàn tất tổng hợp dữ liệu thực nghiệm ngày 06/10/2026.
[Chương kết quả DOCX](13-chuong-ket-qua.docx) có 19 trang, gồm điều kiện đo,
ba sơ đồ kiến trúc, bảng tổng hợp, bốn biểu đồ, phân tích CPU/ENA và giới hạn của kết luận.
Đây là chương kết quả để ghép vào báo cáo, chưa phải toàn bộ báo cáo đồ án.

Mục 8–10, trang 16–19, thêm khái niệm mạng và phép đo cho người mới,
bảng kết luận lựa chọn Peering/TGW và kế hoạch củng cố trước 26/10.
Bản đọc riêng: [khái niệm và kết luận](15-khai-niem-va-ket-luan-so-sanh.md)
và [kế hoạch chi tiết](16-ke-hoach-hoan-thien-den-26-10.md).
Lợi thế kiến trúc/chi phí có nguồn AWS, tách khỏi số đo thực nghiệm.
Các bài bổ sung trong kế hoạch chưa được thực hiện.

## Công thức và ký hiệu

Mục 7, trang 9–15, bổ sung 18 công thức Word chỉnh sửa được. Mỗi công
thức có định nghĩa ký hiệu, đơn vị, ví dụ thế số và điều kiện áp dụng:
trung bình/SD/CV, RTT/mất phản hồi/goodput, chênh lệch và tổng ba nguồn,
Jain từng lượt, CPU/delta ENA, quy mô kết nối/route và mô hình vật lý độ trễ.
Bản đọc riêng: [Công thức và ký hiệu](14-cong-thuc-va-ky-hieu.md).

Jain trung bình của năm chỉ số từng lượt: Peering 0.999133, TGW 0.984494.
Đầu vào là thông lượng theo cửa sổ riêng của từng nguồn, chưa căn chỉnh
interval chung; chỉ mô tả hai phiên, chưa kết luận kiến trúc công bằng hơn
nói chung. Không dùng Jain của ba trung bình cả phiên thay cho trung bình
Jain từng lượt. Số đầy đủ và nguồn ví dụ byte/thời lượng nằm trong mục
`quantitative_methods` của `results/analysis/report-metrics.json`.

Hai ví dụ truyền/lan truyền là giả định có ghi rõ, không phải tham số
vật lý AWS đã đo. Không suy ra thời gian hàng đợi từ delta ENA.

## Kết quả chính

| Điều kiện | Peering | TGW |
|---|---:|---:|
| RTT khi rảnh, mean của 5 RTT trung bình | 0.2078 ms | 0.5630 ms |
| TCP một luồng A→B, mean receiver throughput | 4.7828 Gbps | 4.6083 Gbps |
| Ba nguồn A/C/D→B, tổng throughput trung bình xấp xỉ | 11.6110 Gbps | 11.5905 Gbps |
| CPU busy B trong bài ba nguồn | 59.18% | 56.88% |

Peering có RTT thấp hơn trong đợt đo này. Thông lượng TCP một luồng
Peering cao hơn khoảng 3.79% trong hai phiên; chưa đủ để suy rộng.
Tổng thông lượng ba nguồn gần nhau, đồng thời hai bộ đếm ENA về băng
thông nhận và PPS trên B tăng. Kết quả phản ánh giới hạn của hệ thống
thử nghiệm, chưa xác định năng lực tối đa của Peering/TGW.

## Biểu đồ dùng để chèn vào báo cáo

Phần kiến trúc ở trang 2–3 của DOCX:

- [Peering toàn lưới bốn VPC](images/results/00a-kien-truc-peering.png): đủ
  AB, AC, AD, BC, BD, CD; tô xanh ba kết nối dùng cho A/C/D → B.
- [TGW và bốn attachment](images/results/00b-kien-truc-tgw.png): cùng
  bốn VPC/subnet/EC2, bảng định tuyến TGW mặc định nhận propagation.
- [Quản trị bằng bốn EIP](images/results/00c-quan-tri-eip.png): Termius,
  Internet, IGW riêng của từng VPC, SG và EIP gắn EC2.

Mỗi VPC có ba route tới ba CIDR còn lại. `routing_mode` chọn target
Peering đúng cặp hoặc TGW cho tổng 12 route liên VPC. Đường đo dùng
IP riêng; EIP phục vụ SSH. Trong bài ba nguồn, B có ba listener TCP
5201/5202/5203 cho A/C/D. Sơ đồ dựa trên Terraform và metadata các
phiên đo đã kiểm tra, không gọi AWS để kiểm kê lại trạng thái.

Bốn biểu đồ số liệu:

1. [RTT khi rảnh](images/results/01-rtt.png).
2. [Thông lượng và retransmission TCP một luồng](images/results/02-tcp-single.png).
3. [Thông lượng ba nguồn cùng gửi tới B](images/results/03-tcp-fanin.png).
4. [CPU tổng hợp của B](images/results/04-cpu-b.png).

Mỗi biểu đồ có bản PNG nền trắng, độ phân giải cao và SVG cùng tên.
Hai panel RTT dùng thang khác nhau; CPU dùng chung thang 0–100%.
Số thứ tự lượt ở hai mode không biểu thị đo cùng thời điểm.

## Cách hiểu số liệu

- Mỗi bộ có 5 lượt của một phiên; các mode đo nối tiếp, chưa xen kẽ.
- SD mẫu tính giữa năm trung bình từng lượt, không phải mdev của ping
  và không phải khoảng tin cậy hay kiểm định thống kê.
- Retransmits không phải phần trăm mất gói.
- CPU busy bằng 100−%idle trên dòng all của mpstat, không phải riêng
  iperf3. CPU tổng hợp chưa đạt 100% vẫn có thể tồn tại giới hạn khác.
- Tổng ba nguồn cộng trung bình theo cửa sổ riêng; chưa tổng hợp lại
  từ interval trong cửa sổ thời gian chung. Không suy ra tương đương
  thống kê từ chênh lệch tổng khoảng 0.18%.
- Delta ENA B bao phủ cả phiên, gồm chờ/nghỉ. Bộ đếm allowance tăng
  khi xảy ra vượt giới hạn; không tự tăng chỉ vì đo lâu. Không cộng các
  delta để thành số gói mất.

Định nghĩa ENA dựa trên [tài liệu AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html),
kiểm tra ngày 06/10/2026. Số liệu và giới hạn chi tiết nằm trong DOCX.

## Nguồn và tái tạo

Script [build-results-report.py](../scripts/build-results-report.py) đọc hai
CSV RTT, audit TCP một luồng và hai audit fan-in chuẩn, không gọi AWS và
không thay đổi file gốc. Đầu vào cùng SHA256, số liệu từng lượt và thống
kê nằm ở [report-metrics.json](../results/analysis/report-metrics.json).

Chạy bằng Python/Node và package directory do workspace dependency loader
cung cấp, có python-docx, ReportLab và Sharp; không cần matplotlib.
Script dùng thêm module `scripts/report_context.py` cho khái niệm/kết luận
và xuất Markdown từ cùng nội dung; `scripts/report_formulas.py` để tính Jain, xuất
công thức OMML và tạo tài liệu Markdown từ cùng nội dung:

```powershell
& <bundled-python.exe> scripts/build-results-report.py `
  --node <bundled-node.exe> --node-modules <bundled-node_modules>
```

Trên Windows, script dùng Arial trong C:/Windows/Fonts/arial.ttf.
Phải xuất và kiểm tra lại từng trang sau khi sửa DOCX. Công cụ render_docx
của Documents không chạy được vì thiếu LibreOffice; đã thay bằng Word 16
để xuất PDF từ DOCX chỉ đọc, rồi pdf2image để kiểm tra cả 19 trang PNG.
Script [Render-ResultsReport.ps1](../scripts/Render-ResultsReport.ps1)
thực hiện bước xuất Word; bản xem thử nằm ở tmp/report-render/ và không
phải tài liệu nộp. Word automation có thể cần chạy ngoài sandbox của Codex.

Không đưa bài hai cặp Peering vào so sánh chính vì chưa kiểm tra đầy đủ
file gốc và chưa có bộ TGW đối ứng. Không tính bản sao trùng hoặc bộ dữ
liệu mô phỏng trong clone riêng như số liệu thực nghiệm.

## Tiếp theo

Thu thập sáu bộ chính đã xong. Ghép chương này vào báo cáo, hoàn thiện
cơ sở lý thuyết và phương pháp, chuẩn bị slide và bản GitHub đã rà soát.
Phần củng cố đã có câu hỏi cụ thể: kiểm chứng độ tái lập giữa các đợt
và RTT khi endpoint có tải. Thứ tự, số lượt đề xuất và tiêu chí chốt
nằm trong [kế hoạch đến 26/10](16-ke-hoach-hoan-thien-den-26-10.md).
Kế hoạch mới chưa được thực hiện; không đổi số bộ chính đã hoàn thành.
