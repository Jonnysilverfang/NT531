# Trạng thái triển khai — 05/10/2026

## Hạ tầng đã triển khai

4 VPC, 4 EC2 c6i.large cùng AZ us-east-1a, 4 Elastic IP, 6 Peering,
1 Transit Gateway và 4 attachment. Các route liên VPC đổi giữa hai phương án
trên cùng bốn endpoint; không tạo máy mới khi đổi phương án.

Systems Manager đã apply: 3 tạo, 4 cập nhật, 0 xóa. Cả bốn máy Online sau reboot.
Terraform sau bước này báo No changes. Validate và 3 mock test đạt.
Công cụ đã cài, ba listener iperf3 TCP 5201–5203 trên mỗi máy đều active.

| Máy | Private IP đo | EIP quản trị |
|---|---|---|
| A | 10.10.10.212 | 32.193.42.102 |
| B | 10.20.10.155 | 3.220.153.32 |
| C | 10.30.10.212 | 52.1.69.89 |
| D | 10.40.10.155 | 34.198.156.188 |

## Kiểm chứng thực tế

Cả Peering và TGW đã đạt mỗi phương án: 12 chiều ping, 36 kiểm tra cổng TCP,
12 smoke test iperf3, không có lỗi. Smoke test chỉ 1 Mbit/s trong 2 giây mỗi
chiều, không phải số liệu thông lượng cực đại hay benchmark chính thức.

Sau đó cả bốn máy đã chuẩn hóa MTU runtime 1500, cùng iperf3 3.19.1,
kernel 6.18.51-120.163.amzn2023.x86_64, ENA 2.17.2g, NTPSynchronized=yes.
MTU cần kiểm tra lại sau reboot. Kiểm tra cuối ở MTU 1500 đã hoàn tất:

| Chế độ | Ping | TCP ba cổng | iperf3 smoke | Lỗi | Route liên VPC active |
|---|---|---|---|---|---|
| Peering | 12/12 | 36/36 | 12/12 | 0 | 12/12 |
| TGW | 12/12 | 36/36 | 12/12 | 0 | 12/12 |

Route cuối đã trả về **Peering**, cả bốn máy sẵn sàng dùng Session Manager.
Terraform plan cuối báo **No changes**. TGW vẫn tồn tại để đổi mode khi đo.

Bằng chứng trong results/verification-20261005: peering.txt, tgw.txt,
readiness.json, peering-mtu1500.txt, tgw-mtu1500.txt, peering-routes.json và
tgw-routes.json. Kết quả chi tiết trên EC2 ở
/home/ec2-user/nt531-results/. Trạng thái này ghi nhận tại thời điểm kiểm tra,
không phải giám sát liên tục.

## Còn phải làm để hoàn thành đồ án

- Đo chính thức ba kịch bản với số lần lặp và điều kiện thống nhất.
- Thu log JSON, CPU, RTT, ENA; tổng hợp và giải thích giới hạn EC2/burst.
- Viết kết quả, biểu đồ, nhận xét và chuẩn bị bảo vệ.
- Đồng bộ mã/tài liệu mới sang repository GitHub sau khi rà soát diff.

SSH từ máy quản trị chưa xác minh lại thành công; dùng Session Manager đã được
kiểm chứng để truy cập. Không cần chờ SSH để đo. Xem docs/06-truy-cap-ssm.md.
Hạ tầng vẫn đang chạy, TGW/EIP vẫn tồn tại và phát sinh phí.
Không commit state, plan, PEM hoặc file biến cá nhân.

## Cập nhật SSH theo yêu cầu demo

Đã apply nguồn 0.0.0.0/0 cho TCP22 trên bốn SG: 0 tạo, 4 sửa, 0 xóa.
Cả bốn EIP trả lời SSH handshake, không còn timeout trong lần thử này.
Windows OpenSSH từ môi trường kiểm tra từ chối đọc PEM vì ACL quá rộng;
chưa xác nhận đăng nhập shell bằng OpenSSH. Người dùng thử lại Termius với
khóa đã import, username ec2-user. Cấu hình cổng đo giữ nguyên.

## Tạm nghỉ theo yêu cầu người dùng

Đã stop và xác nhận cả bốn EC2 A/B/C/D ở trạng thái stopped ngày 05/10/2026.
Các kiểm chứng running/ready phía trên là trước lúc nghỉ. EBS, EIP và TGW vẫn giữ.
Khi tiếp tục: start bốn máy, đợi status checks/SSM, kiểm tra lại MTU 1500 vì
thiết lập MTU trước đó chỉ là runtime. Route vẫn là Peering.

## Tiếp tục phiên đo sau thời gian nghỉ — 05/10/2026

Đã start bốn EC2, xác nhận cả bốn system/instance checks OK và SSM Online.
Đặt lại MTU1500, NTP đồng bộ, ba listener mỗi máy active. AWS có 12 route Peering
active và 0 route liên VPC trỏ TGW. Kiểm tra sau start đạt 12 ping, 36 TCP,
12 iperf smoke, không lỗi. Bằng chứng: results/resume-20261005/.
Máy đang chạy để người dùng đo qua Termius; chưa chạy benchmark bão hòa phiên này.

## Bắt đầu bài RTT TGW — 05/10/2026

Đã kiểm tra bản RTT Peering do người dùng tải về tại
results/pilot-peering/rtt-idle-a-b/nt531-results/peering-rtt-idle-a-b-20261005T115510Z-6qX9Gm:
5 log, mỗi log 100 phản hồi, exit code 0, metadata và summary.csv đủ.
Đã apply rtt-tgw.tfplan: đổi 12 route sang TGW. AWS xác nhận 12 route TGW active,
0 route Peering. Hiện mode là TGW, chờ người dùng chạy 5 lượt RTT qua Termius.
Chưa có kết quả RTT TGW chính thức. Route snapshot lưu ở
results/formal/tgw/rtt-idle-a-b/routes-before-measurement.json.

## Tiếp tục bài TCP Peering — 06/10/2026

Các mục trước là nhật ký theo thời điểm, không phải trạng thái hiện tại.
Đã nhận và kiểm tra ba bộ kết quả: RTT Peering, RTT TGW và TCP TGW A→B.
TCP TGW có đủ 5 lượt JSON/CPU/ENA ở A và log CPU/ENA ở B.
Chưa có kết quả TCP Peering chính thức; còn đo hai kịch bản song song và fan-in
trên cả hai mode, sau đó phân tích CPU/ENA và hoàn thiện báo cáo.

Ngày 06/10 đã start A/B từ trạng thái stopped; cả hai system/instance checks OK,
SSM Online, MTU ens5 được đặt lại 1500, NTP đồng bộ, listener 5201–5203 active.
Route A↔B active qua pcx-0d52503115f5644b6 (Peering).
Chưa chạy benchmark bão hòa trong phiên này; người dùng đo qua Termius.
Phép đo tiếp theo: A→B TCP P1, 5 lượt, bỏ 5 giây đầu, đo 30 giây,
nghỉ 10 giây giữa các lượt; ghi CPU và ENA hai đầu để đối chiếu TCP TGW.

## Hoàn thành TCP Peering và chuẩn bị hai cặp — 06/10/2026

Đã nhận đủ 42 file A và 5 file B của TCP Peering. Kiểm tra 5 JSON hợp lệ,
exit0, stderr trống, CSV khớp JSON, CPU B bao phủ cả 5 lượt.
Đã phân tích CPU theo cửa sổ đo và delta năm bộ đếm allowance ENA của
cả Peering/TGW; chi tiết tại 07-ket-qua-tcp-mot-cap.md và
results/formal/tcp-single-comparison-audit.json.

Đã start C/D, đặt lại MTU1500 cả bốn máy, NTP đồng bộ, listener active.
Cài measure-tcp-pairs.sh vào home ec2-user cả bốn máy qua SSM,
bash -n thành công. AWS có 12 route Peering active; snapshot tại
results/formal/peering/tcp-two-pairs/routes-before-measurement.json.
Chưa chạy bài hai cặp; người dùng khởi chạy qua Termius theo docs/08-do-hai-cap.md.

## Điều chỉnh ưu tiên đo — 06/10/2026

Người dùng đã hoàn tất hai cặp Peering, cả A/B/C/D hiện DONE trong ảnh.
Chưa kiểm tra file của phiên hai cặp sau khi tải về. Giữ bộ này làm
quan sát bổ sung; không ưu tiên đo hai cặp TGW tiếp theo.
Tập trung phần còn lại vào fan-in A/C/D→B qua Peering và TGW, cùng
điều kiện và log CPU/ENA B. Không coi throughput giảm ở B là bằng chứng
TGW nghẽn khi chưa loại trừ giới hạn endpoint. Các tỷ lệ tiến độ trước
đó là ước lượng theo phạm vi cũ, cần cập nhật khi chốt báo cáo.

## Chuẩn bị fan-in Peering — 06/10/2026

Cả bốn EC2 running, system/instance checks OK. SSM xác nhận MTU1500,
NTP đồng bộ và ba listener active. Cài measure-tcp-fanin.sh vào home
ec2-user cả bốn máy và kiểm tra bash -n thành công.
Script chọn A→B:5201, C→B:5202, D→B:5203; B ghi CPU/ENA và tự kết thúc.
AWS có 12 route Peering active và 0 route TGW; snapshot tại
results/formal/peering/tcp-fanin/routes-before-measurement.json.
Người dùng chạy theo docs/09-do-fan-in.md. Chưa có số đo fan-in.

## Chuẩn bị đo lại fan-in sau cúp điện — 06/10/2026

Người dùng yêu cầu đo lại fan-in Peering sau cúp điện. Khi kiểm tra,
cả bốn EC2 ở trạng thái stopped; không suy ra nguyên nhân stop là cúp điện.
Đã start cả bốn và xác nhận system/instance checks OK, SSM Online.
Khôi phục MTU1500; NTP đồng bộ, ba listener active, script bash -n hợp lệ.
Kiểm tra A→B:5201, C→B:5202, D→B:5203 thành công, không phát hiện client
iperf/mpstat/script fan-in cũ trên các máy gửi sau restart.
AWS có 12 route Peering active và 0 route TGW. Bằng chứng route tại
results/formal/peering/tcp-fanin/restart-20261006T130540Z/.
Các thư mục fan-in cũ T=1791281853 vẫn còn trên cả bốn máy; giữ để kiểm tra,
không coi là phiên hợp lệ hoặc bị hỏng chỉ dựa trên việc mất kết nối.
Người dùng tạo T mới và chạy lại cùng script; chưa chạy benchmark tự động.

## Kiểm tra fan-in Peering phiên mới — 06/10/2026

Đã kiểm tra trực tiếp trên EC2 phiên T=1791293390, đủ 15 lượt TCP
(5 lượt mỗi nguồn A/C/D), exit0, stderr trống, CSV khớp JSON,
không có lỗi lịch. A/C/D mỗi máy 47 file; B có 5 file, tổng 146 file.
Các nguồn có cửa sổ đo chung xấp xỉ 29.05–29.71 giây mỗi lượt;
độ lệch khởi chạy wrapper 0.30–0.96 giây, không đồng thời tuyệt đối.
Tổng throughput phía nhận trung bình xấp xỉ 11.611 Gbps.
CPU tổng hợp B khoảng 59.18% trong cửa sổ theo lịch; ENA B tăng
bw_in_allowance_exceeded và pps_allowance_exceeded, cần xét giới hạn
endpoint khi so sánh với TGW. Snapshot sau đo vẫn 12 route Peering active.
Chi tiết tại docs/10-ket-qua-fan-in-peering.md và
results/formal/peering/tcp-fanin/audit-1791293390/.
Bản audit là trích dữ liệu; chưa xác nhận đã tải đủ file gốc về Windows.
Không chạy lại benchmark hoặc chuyển route trong lần kiểm tra này.

## Tiến độ và phần còn lại — 06/10/2026

Phạm vi đo chính hiện tại: 3 bài (RTT khi rảnh, TCP một cặp, TCP fan-in)
trên 2 phương án, tổng 6 bộ. Đã kiểm tra 5 bộ: RTT Peering/TGW,
TCP một cặp Peering/TGW và fan-in Peering. Tương ứng 5/6 bộ (~83%),
chỉ là tiến độ thu thập các bộ số liệu, không phải phần trăm toàn đồ án
hoặc số điểm theo rubric. Hai cặp Peering là bộ bổ sung đã chạy,
chưa kiểm tra file gốc; không tính vào mẫu số 6 bộ chính.

Còn 1 đợt fan-in TGW, 5 lượt đồng thời của A/C/D→B (15 phép đo TCP),
với cùng script và điều kiện. Thời gian script từ mốc T đến kết thúc B
khoảng 220 giây, chưa tính chuẩn bị, kiểm tra và tải file.

Thứ tự tiếp theo: sao lưu đủ 146 file fan-in Peering; chuyển route sang
TGW bằng plan mới đã kiểm tra; xác nhận 12 route TGW active; chạy 5 lượt
qua Termius; sao lưu và kiểm tra log; lập bảng/biểu đồ so sánh RTT,
TCP một cặp và fan-in cùng CPU/ENA; hoàn thiện báo cáo, slide và bản
code/kết quả đã rà soát trên GitHub. Chưa mở thêm bài đo để tìm chênh
lệch đẹp; chỉ đo lại khi lỗi hoặc cần kiểm chứng một kết luận cụ thể.
Các bộ nối tiếp chưa loại trừ sai lệch thời điểm/burst; kết luận phải
giới hạn ở cấu hình và các đợt đã thực hiện, không khái quát toàn dịch vụ.

## Sao lưu Peering và sẵn sàng đo fan-in TGW — 06/10/2026

Đã tải đủ 146 file gốc của phiên Peering 1791293390 qua SSM, lưu nguyên
folder vào results/formal/peering/tcp-fanin/A/, B/, C/, D/. Bốn archive
khớp SHA256 từ EC2; số file giải nén, metadata và 15 JSON khớp audit.
Manifest tại audit-1791293390/full-backup-manifest.json. Không cần người
dùng kéo lại bộ này qua SFTP; log gốc trên EC2 vẫn giữ nguyên.

Đổi routing_mode sang tgw, fmt -check và validate thành công. Plan mới
fanin-tgw-20261006.tfplan chỉ có 12 aws_route update, chỉ đổi target,
0 tạo và 0 xóa. Đã apply thành công; AWS xác nhận 12 route TGW active,
0 route liên VPC qua Peering. Cả bốn EC2 running, health OK, không còn
client iperf hoặc mpstat cũ tại lúc chuẩn bị, MTU1500, NTP đồng bộ,
ba listener active và script fan-in hợp lệ. TCP A/C/D→B lần lượt qua
5201/5202/5203 thành công. Bằng chứng lưu ở results/formal/tgw/tcp-fanin/.
Chưa chạy benchmark fan-in TGW; người dùng chạy 5 lượt theo
docs/11-do-fan-in-tgw.md. Tham số mode không tự đổi route.

## Hoàn tất bộ đo chính và kiểm tra fan-in TGW — 06/10/2026

Người dùng chạy phiên TGW T=1791296141, cả bốn DONE. Đã kiểm tra đủ
15 JSON/exit0/stderr trống/CSV khớp, không có lỗi lịch, CPU/ENA đủ.
Đã sao lưu 146 file gốc TGW vào results/formal/tgw/tcp-fanin/A/, B/,
C/, D/; SHA256 bốn archive khớp, số file/metadata/15 JSON đúng audit.
Phiên A T=1791296096 bị hủy được giữ riêng, không dùng làm số liệu.
Snapshot sau đo xác nhận 12 route TGW active, 0 route liên VPC Peering.

Tổng receiver throughput trung bình xấp xỉ TGW 11.5905 Gbps, Peering
11.6110 Gbps, chênh lệch quan sát 0.18%. CPU tổng hợp B TGW 56.88%,
Peering 59.18% theo cửa sổ lịch. Cả hai tăng ENA bandwidth/PPS allowance
ở B; không kết luận dịch vụ nào tốt hơn từ chênh lệch này.
Chi tiết: docs/12-ket-qua-fan-in-tgw-va-so-sanh.md,
results/formal/tgw/tcp-fanin/audit-1791296141/ và
results/formal/fanin-comparison-audit.json.

Đã đủ 6/6 bộ đo chính trong phạm vi hiện tại. Phần còn lại là biểu đồ,
phân tích, báo cáo, slide và cập nhật GitHub; chưa coi toàn đồ án xong.
Hai cặp Peering là bổ sung, chưa kiểm tra file gốc. Không tự chạy thêm
benchmark, đổi route hay stop máy trong lần kiểm tra này.

## Bản ZIP sao lưu kết quả — 06/10/2026

Theo yêu cầu lưu file kết quả, đã kiểm tra lại hai manifest fan-in và
tạo backups/nt531-results-20261006T142912Z.zip (2,607,632 byte).
ZIP giữ toàn bộ 686 file kết quả đã có, docs/README và 8 archive gốc
fan-in khớp SHA256 từ EC2. Hai phiên fan-in có 292 file gốc (146 mỗi
mode); bản sao trùng và pilot giữ nguyên nhưng không tính như phép
đo độc lập. Đã đọc lại ZIP và xác nhận kích thước/SHA256 708 file
payload; manifest và hướng dẫn được nhúng trong ZIP, checksum ZIP
lưu bên cạnh. Chi tiết tại backups/README.md. Chưa sao lưu sang ổ
khác hoặc dịch vụ lưu trữ bên ngoài.

## Chương kết quả và biểu đồ — 06/10/2026

Đã tạo docs/13-chuong-ket-qua.docx gồm sáu trang từ sáu bộ đo chính,
bốn biểu đồ PNG/SVG trong docs/images/results/ và bảng số liệu cùng
SHA256 đầu vào ở results/analysis/report-metrics.json. Hướng dẫn đọc và
tái tạo: docs/13-tong-hop-ket-qua.md, scripts/build-results-report.py.

Đã xuất DOCX chỉ đọc qua Microsoft Word 16 và kiểm tra trực quan cả
sáu trang PNG, không có bảng/biểu đồ bị cắt hoặc chữ chồng nhau.
Renderer LibreOffice của Documents không có executable trên máy nên
dùng Word và pdf2image thay thế. Bản xem thử giữ riêng trong tmp/.

Nội dung phân biệt SD giữa lượt với mdev của ping, retransmits với
tỷ lệ mất gói, CPU tổng hợp với CPU tiến trình và delta ENA toàn phiên.
Tổng fan-in ghi là xấp xỉ, không kết luận tương đương thống kê hay năng
lực tối đa của dịch vụ từ chênh lệch 0.18%. Không chạy thêm benchmark
hoặc thay đổi AWS. Phần còn lại là ghép toàn báo cáo, slide và GitHub.

## Bổ sung mô hình kiến trúc — 06/10/2026

Chương kết quả DOCX hiện gồm tám trang. Trang 2 có Peering toàn lưới
(sáu kết nối cho bốn VPC) và TGW (một gateway, bốn attachment).
Trang 3 có đường quản trị Termius qua bốn Elastic IP, bảng so sánh
định tuyến và giải thích các luồng đo A/C/D tới B. Sơ đồ ghi CIDR,
subnet, EC2, private IP, SG và route table theo Terraform hiện có;
đây là mô hình cấu hình, không phải snapshot trạng thái AWS mới.

Ba sơ đồ được lưu PNG/SVG trong docs/images/results/00a–00c và
được tái tạo bằng scripts/build-results-report.py. Đã cập nhật README,
docs/03-bon-vpc.md và docs/13-tong-hop-ket-qua.md. Số liệu kết quả
được giữ nguyên. Đã xuất qua Microsoft Word 16 và kiểm tra trực quan
cả tám trang: sơ đồ/bảng/chữ không bị cắt hay chồng nhau. Bản Word
trước sửa được giữ trong tmp/ và ZIP sao lưu cũ. Không đổi hạ tầng AWS.

## Công thức ký hiệu và phân tích bổ sung — 06/10/2026

Chương kết quả DOCX hiện gồm 15 trang. Mục 7 ở trang 9–15 thêm 18
công thức OMML chỉnh sửa được, có định nghĩa ký hiệu, đơn vị, ví dụ thế
số và điều kiện áp dụng. Bao gồm thống kê mô tả, RTT/mất phản hồi/goodput,
chênh lệch, tổng ba nguồn, Jain, CPU/ENA, số kết nối/route và mô hình vật lý.
Bản Markdown riêng: docs/14-cong-thuc-va-ky-hieu.md. Tái tạo bằng builder
và scripts/report_formulas.py. Nội dung tám trang trước được giữ nguyên.

Jain tính riêng 10 lượt từ ba nguồn rồi lấy trung bình mỗi mode:
Peering 0.999133, TGW 0.984494. Đã đối chiếu thông lượng từ byte/thời lượng
của 30 JSON gốc, kiểm tra Jain bằng biểu thức CV tương đương và SD mẫu
bằng NumPy ddof=1. Chi tiết ở results/analysis/formula-verification.json.
Các cửa sổ nguồn chưa căn chỉnh chung nên Jain là mô tả hai phiên;
không suy ra công bằng của dịch vụ nói chung. Ví dụ vật lý là giả định.

Đã xuất qua Word 16 và kiểm tra trực quan đủ 15 trang, không bị cắt hay
chồng công thức. Không chạy benchmark hoặc thay đổi AWS. Bản Word trước
sửa giữ trong tmp/ và ZIP sao lưu cũ.

## Khái niệm kết luận lựa chọn và kế hoạch đến 26/10 — 06/10/2026

Đã thêm mục 8–10, trang 16–19 của chương kết quả: khái niệm mạng/phép
đo cho người mới, bảng Peering/TGW có lợi thế ở đâu, phân biệt số đo
với khả năng kiến trúc và kế hoạch củng cố. Có hai tài liệu Markdown:
docs/15-khai-niem-va-ket-luan-so-sanh.md và
docs/16-ke-hoach-hoan-thien-den-26-10.md. Builder dùng thêm
scripts/report_context.py để tái tạo nội dung và bản Markdown khái niệm.

Đề xuất ưu tiên rà raw/cửa sổ, bốn đợt lặp RTT/TCP một luồng cân bằng
thứ tự, rồi RTT khi có tải hữu hạn; có thiết kế phân tích theo đợt,
giải thích ký hiệu CI và mô hình chi phí. Các bài mới chưa chạy, không
đổi hạ tầng AWS. Phần định lượng cũ giữ nguyên, report-metrics.json
giữ SHA256 đã đối chiếu trong formula-verification.json. Nội dung 15
trang cũ được kiểm tra giữ nguyên qua XML; đủ 19 trang được xuất bằng
Word 16 và kiểm tra trực quan, 18 công thức OMML vẫn còn nguyên.
