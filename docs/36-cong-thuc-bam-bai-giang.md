# Công thức để hiểu và thuyết trình đồ án NT531

Bản hướng dẫn ngày 13/10/2026, dùng bộ kết quả đã chốt: 5 block RTT và 3 block ứng dụng. Không cần đo thêm để sử dụng tài liệu này. Các bản kế hoạch 16 block được giữ làm lịch sử phương pháp; không xem kiểm định dự kiến là kết quả đã đạt.

## Chọn công thức theo câu hỏi

| Câu hỏi của đồ án | Công cụ toán nên dùng | Liên hệ bài giảng NT531 |
|---|---|---|
| Peering và TGW khác nhau bao nhiêu về RTT? | Chênh lệch từng block, trung bình, khoảng min–max | Internet Performance, trang 4: latency; phép trung bình/chênh lệch là phép tổng hợp số liệu của nhóm |
| Một số yêu cầu có bị chậm dù trung bình thấp? | P50, P95 và phân bố thực nghiệm | Internet Performance, trang 41–42: percentiles và tail latency |
| Bao nhiêu yêu cầu đáp ứng ngưỡng 50 ms? | Tỷ lệ đúng hạn, một SLI | Internet Performance, trang 26–27: SLI/SLO |
| Vì sao tăng tải hoặc thiếu slots dẫn đến chờ? | Tải danh nghĩa và định luật Little | Arrival Processes, trang 3, 62–66; trang 66 có ví dụ thread pool |
| Thời gian của một yêu cầu nằm ở đoạn nào? | Trace/spans và thời gian chờ/phục vụ | Internet Performance, trang 31, 34, 39 |

Tên đầy đủ của nguồn: **NT531 - Lecture 02 - Arrival Processes and Queuing Systems.pdf** và **NT531 - Internet Performance, QoS and Cloud-Native Metrics.pdf** do sinh viên cung cấp. Số trang là thứ tự PDF từ 1. Không đưa bản bài giảng vào GitHub. Nội dung Xác suất thống kê UIT chưa có slide để đối chiếu; không tự gán tên chương hoặc khẳng định mọi công thức dưới đây đã học trong môn đó.

## 1. RTT và chênh lệch giữa hai đường mạng

RTT là thời gian yêu cầu ICMP đi từ A tới B rồi phản hồi về A. Ping tính trên cùng đồng hồ của A; không cần lấy đồng hồ B trừ đồng hồ A.

\[
\Delta_j=\bar r_{\mathrm{TGW},j}-\bar r_{\mathrm{Peering},j},\qquad
\overline\Delta=\frac{1}{m}\sum_{j=1}^{m}\Delta_j.
\]

| Ký hiệu | Nghĩa | Đơn vị |
|---|---|---|
| \(j\) | Số thứ tự block so sánh | Không có đơn vị |
| \(m\) | Số block hợp lệ; hiện là 5 | block |
| \(\bar r_{\mathrm{mode},j}\) | RTT trung bình của một mode trong block j | ms |
| \(\Delta_j\) | TGW trừ Peering trong block j | ms |
| \(\overline\Delta\) | Trung bình 5 chênh lệch | ms |

Thế số từ analysis, làm tròn để trình bày:

\[
\overline\Delta\approx
\frac{0{,}230333+0{,}239667+0{,}425667+0{,}305667+0{,}358000}{5}
=0{,}3119\ \mathrm{ms}.
\]

Cả 5 chênh lệch quan sát đều dương; min–max là 0,2303–0,4257 ms. Câu nói phù hợp: **“Trong 5 block của cấu hình đã thử, RTT TGW cao hơn Peering trung bình khoảng 0,312 ms.”** Không gọi đây là 0,312 ms xử lý nội bộ TGW: RTT còn bao gồm endpoint và toàn bộ đường đi.

Nguồn: [analysis RTT](../results/confirmation-rtt-v1/analysis.json). Trung bình/chênh lệch là phép tính mô tả; không cần đặt thêm giả định phân phối chuẩn để tính chúng.

## 2. P95: không chỉ nhìn trung bình

Slide Internet Performance trang 41 giải thích P50/P95/P99. Đồ án dùng cách **nearest rank**:

\[
k=\lceil0{,}95n\rceil,\qquad P95=x_{(k)}.
\]

- \(n\): số quan sát hợp lệ của chỉ số đang xét.
- \(x_{(k)}\): giá trị thứ k sau khi sắp xếp tăng dần; đơn vị ms nếu đo độ trễ.
- \(\lceil\cdot\rceil\): làm tròn lên số nguyên.
- Với 100 giá trị, lấy giá trị thứ 95. Nếu có nhiều giá trị bằng nhau, ít nhất 95% nằm dưới hoặc bằng ngưỡng này.

Định nghĩa phân vị có trong slide; quy tắc nearest rank là lựa chọn tính toán của code nhóm, không khẳng định slide quy định đúng thuật toán này.

P95 ứng dụng đang báo là độ trễ của các yêu cầu **hoàn thành thành công** trong từng điều kiện. Tỷ lệ lỗi và tỷ lệ đúng hạn vẫn có mẫu số toàn bộ yêu cầu theo lịch. P95 hàng đợi worker và P95 thời gian hoàn thành ở A là hai chỉ số khác nhau. Không lấy trung bình các P95 rồi đặt tên là P95 gộp.

Ở 800 rps qua Peering, 8 slots có P95 từng block khoảng 1.350–1.499 ms; 16 slots khoảng 12,651–12,698 ms. Khoảng này là min–max giữa ba block, không phải khoảng tin cậy.

## 3. Tỷ lệ đúng hạn: phần xác suất dễ giải thích

Theo slide trang 26, SLI là chỉ số định lượng phản ánh chất lượng dịch vụ. Nhóm chọn sự kiện tốt: yêu cầu thành công và hoàn thành trong 50 ms tính từ lịch gửi. 50 ms là ngưỡng thử nghiệm đã chọn, không phải SLA AWS và không phải mục tiêu giảng viên áp đặt.

\[
\widehat p=\frac{N_{\mathrm{good}}}{N_{\mathrm{scheduled}}},\qquad
SLI_{\%}=100\widehat p.
\]

\(N_{\mathrm{good}}\): số yêu cầu thành công trong deadline; \(N_{\mathrm{scheduled}}\): toàn bộ yêu cầu theo lịch, gồm lỗi và yêu cầu trễ. \(\widehat p\) nằm trong [0,1], không có đơn vị; \(SLI_\%\) tính bằng %. Dấu mũ nhắc đây là tỷ lệ từ mẫu đã quan sát, không phải xác suất thật đã biết cho mọi phiên tương lai.

| 800 rps, ba block | Đúng hạn / theo lịch | SLI quan sát |
|---|---:|---:|
| Peering, 8 slots | 1.096 / 36.000 | 3,044% |
| Peering, 16 slots | 36.000 / 36.000 | 100% |
| TGW, 8 slots | 1.178 / 36.000 | 3,272% |
| TGW, 16 slots | 36.000 / 36.000 | 100% |

Ví dụ: Peering 8 slots có \(\widehat p=1096/36000\approx0{,}03044\), tương ứng 3,044%. 100% trong cửa sổ này không có nghĩa tương lai chắc chắn không có yêu cầu trễ. Yêu cầu trễ nhưng HTTP thành công vẫn không đạt deadline.

Khi tính hiệu ứng can thiệp, so sánh 16 trừ 8 slots **trong cùng block và cùng mode**, rồi trung bình qua hai mode và ba block. Hiệu ứng trung bình là **96,8417 điểm phần trăm**. Đây là điểm phần trăm, không ghi thành “tăng 96,84%” hay “nhanh hơn 96,84%”.

Nguồn: [bảng tổng hợp đã chốt](../results/analysis/reduced-study-summary.json). Các request trong cùng phiên có thể phụ thuộc nhau; 252.000 request không được coi là 252.000 lần lặp độc lập của thí nghiệm.

## 4. Tải danh nghĩa: vì sao 8 và 16 slots khác nhau?

Slide Arrival trang 3 dùng \(\rho=\lambda/\mu\); trang 66 liên hệ concurrency, throughput, latency và kích thước thread pool. Với M slots, mỗi lời gọi chiếm một slot trung bình s giây, nhóm dùng ước lượng danh nghĩa:

\[
\mu_{\mathrm{nom}}=\frac{M}{s},\qquad
\rho_{\mathrm{nom}}=\frac{\lambda_{\mathrm{cfg}}s}{M}.
\]

- M: số slots phục vụ đồng thời trên **một worker**, không phải số vCPU.
- s: thời gian phục vụ cấu hình, giây/lời gọi; ở đây 10 ms = 0,010 s.
- \(\lambda_{\mathrm{cfg}}\): tải theo lịch, lời gọi/s trên mỗi worker.
- \(\mu_{\mathrm{nom}}\): công suất danh nghĩa, lời gọi/s; \(\rho_{\mathrm{nom}}\) không có đơn vị.

| Tải | Slots | \(\mu_{nom}\) | \(\rho_{nom}\) |
|---|---:|---:|---:|
| 600 lời gọi/s | 8 | 800 lời gọi/s | 0,75 |
| 800 lời gọi/s | 8 | 800 lời gọi/s | 1,00 |
| 800 lời gọi/s | 16 | 1.600 lời gọi/s | 0,50 |

Đây là cách đọc “tải có gần công suất phục vụ không”. Ở 8 slots và 800 rps, hệ thống gần mức danh nghĩa, không còn nhiều dư địa cho overhead. Log thực cho thấy thời gian phục vụ có thể dài hơn 10 ms; vì vậy phải kiểm tra hàng đợi thật, không chỉ nhìn bảng này.

Một yêu cầu A gọi C và D song song: **mỗi worker nhận khoảng 800 lời gọi/s**, không phải 1.600. 1.600 là tổng hai worker. Công thức trên là suy luận năng lực phục vụ từ mô hình slots, không phải công thức M/M/1 đã áp thẳng vào AWS; không tuyên bố traffic là Poisson hay service là exponential. \(\rho_{nom}\) cũng không phải %CPU.

## 5. Little: công thức chính có ngay trong slide

Arrival trang 62 viết \(N=\lambda T\), trang 65–66 dùng \(L=\lambda W\). Đó là cùng mối quan hệ với cách đặt tên khác nhau. Đồ án dùng phiên bản cho phần đang chờ:

\[
L_q=\lambda_C\overline W_q.
\]

| Ký hiệu | Nghĩa | Đơn vị |
|---|---|---|
| \(L_q\) | Số lời gọi đang chờ trung bình theo thời gian trong nhóm đã chọn | lời gọi |
| \(\lambda_C=N/T_C\) | Số lời gọi đã vào worker chia thời lượng chứa trọn nhóm | lời gọi/s |
| N | Số lời gọi thuộc cùng nhóm request ID | lời gọi |
| \(T_C\) | Từ lần vào đầu tiên tới lần thoát cuối cùng trên worker đó, gồm đuôi xử lý | s |
| \(\overline W_q\) | Trung bình thời gian chờ của cùng các lời gọi | s |

**Ví dụ từ log thật:** worker C, Peering, 8 slots, cấu hình 800 rps, block 3:

\[
L_q=732{,}2866\ \mathrm{lời\ gọi/s}\times0{,}7009511\ \mathrm{s}
\approx513{,}2971\ \mathrm{lời\ gọi}.
\]

Số 732,2866 khác 800 vì mẫu số gồm đuôi xử lý của cùng nhóm lời gọi. Không thay nó bằng tốc độ cấu hình khi thế số. Với 16 slots ở cùng block/mode/worker, tốc độ 799,5313 lời gọi/s và thời gian chờ trung bình 0,000005239 s cho \(L_q\approx0{,}004189\) lời gọi. Số trung bình nhỏ hơn một là hợp lệ: phần lớn thời gian hàng đợi trống.

Giải thích bằng lời: **“Cộng toàn bộ thời gian từng lời gọi đã chờ, rồi chia thời gian quan sát, ta được số lời gọi đang chờ trung bình.”** Đây chính là ý diện tích minh họa ở slide trang 65. Phần tích phân trong [tài liệu Little chi tiết](33-hang-doi-va-dinh-luat-little.md) là chứng minh mở rộng cho cửa sổ hữu hạn; để phụ lục nếu chưa quen ký hiệu tích phân/hàm chỉ thị.

Phép kiểm tra cùng log cho hai vế là kiểm tra nhất quán số liệu, không phải một kiểm định thống kê độc lập. Không cần giả định Poisson cho đẳng thức hữu hạn của nhóm quan sát đầy đủ. Không lấy goodput iperf nhân RTT ping để suy ra hàng đợi TGW.

Nguồn ví dụ: [queue audit](../results/analysis/queue-occupancy-audit.json), block 3, worker C, hai điều kiện Peering 8/16 slots ở 800 rps.

## 6. Phần nào để phụ lục?

| Nội dung | Cách dùng khi bảo vệ |
|---|---|
| Trung bình, chênh lệch, P95, SLI, Little | Phần chính; phải giải thích được ký hiệu, đơn vị, mẫu số và một ví dụ từ raw |
| Độ lệch chuẩn, ECDF, Jain | Dùng khi nói về biến động/phân bố/chia đều; Jain là tài liệu tham khảo mở rộng, không đánh đồng với max-min fairness ở slide trang 6 |
| Tích phân sample path của Little | Phụ lục chứng minh; không cần mở đầu bằng công thức dài |
| M/M/1 và công thức thời gian chờ | Lý thuyết trong bài giảng; không dùng để dự đoán workload nếu chưa kiểm tra giả định |
| Sign test 16 block, kiểm định nhị thức, công suất, bootstrap/CI | Lưu lịch sử thiết kế; không dùng như kết quả xác nhận đã hoàn thành sau khi rút gọn 5/3 block |
| Công thức lan truyền/truyền gói với tham số giả định | Minh họa phụ; không dùng để giải thích định lượng RTT AWS đã đo |

## Câu kết luận dễ nói

“Trong cấu hình thử nghiệm, Peering có RTT thấp hơn TGW. Tuy nhiên, ở 800 yêu cầu/s, cả hai đường mạng đều có tỷ lệ đúng hạn thấp khi worker chỉ có 8 slots. Tăng lên 16 slots cải thiện tỷ lệ đúng hạn rõ rệt và giảm chờ tại worker. Vì vậy chọn đường mạng phải xét cùng khả năng phục vụ và deadline của ứng dụng. Log hàng đợi và định luật Little giúp giải thích kết quả; trace trên Grafana giúp minh họa luồng lời gọi.”

Thống kê mô tả, giới hạn phạm vi và số liệu đầy đủ ở [báo cáo tổng hợp](34-bao-cao-tong-hop.md) và [phạm vi đã chốt](35-pham-vi-rut-gon-va-ket-luan.md). Quy trình mở Grafana/quay video ở [hướng dẫn demo](37-quay-video-va-grafana.md).
