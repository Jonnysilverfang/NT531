# Đối chiếu đồ án Peering TGW với bài giảng NT531

Ngày đối chiếu: 06/10/2026. Đây là đánh giá phạm vi và đề xuất bổ sung; không có phép đo EC2 mới trong lần đối chiếu này.

## Kết luận về mô hình và công cụ

Giữ mô hình bốn VPC, bốn EC2, sáu Peering và một TGW với bốn attachment. Mô hình thực nghiệm trên hệ thống thật phù hợp với hướng đánh giá hiệu năng trong môn. Không cần dựng thêm mạng chỉ để có đủ tên công cụ trong bài giảng.

Bộ hiện tại đã đo được các chỉ số chính: `ping`, `iperf3`, `mpstat`, `ethtool`, `jq`, cùng Terraform/AWS CLI để triển khai và kiểm chứng đường định tuyến. Phần cần phát triển là giải thích cơ chế TCP, phân bố độ trễ và tính tái lập. Dashboard và mô phỏng là lựa chọn mở rộng theo câu hỏi cụ thể.

## Nguồn bài giảng đã đọc

Số trang dưới đây là thứ tự trang PDF từ 1; số slide là thứ tự trong PPTX.

| Tài liệu | Phần liên quan nhất | Liên hệ đồ án |
|---|---|---|
| NT531 - Introduction1.pptx | Slide 12, 14, 15, 18 | Phương pháp thực nghiệm, ví dụ đề tài, tiêu chí seminar, sử dụng AI và khả năng tự giải thích |
| NT531 - Lecture 02 - Arrival Processes and Queuing Systems.pdf | Trang 3, 32, 34, 38, 43, 62–66, 69 | Tải và thời gian chờ; giả định mô hình; Little; công cụ quan sát |
| lec4 - NT531 - Congestion Control.pdf | Trang 3, 10, 16–20, 25, 30 | Tắc nghẽn, truyền lại, cửa sổ TCP, điều tiết tải |
| NT531 - Internet Performance, QoS and Cloud-Native Metrics.pdf | Trang 4–7, 11, 26–27, 39, 41–45 | Chỉ số mạng, fairness, tc, SLI/SLO/SLA, phân vị, quan sát hệ thống |

Bốn bài giảng do sinh viên cung cấp để đối chiếu, không được đóng gói trong
repo này. Tên file và trang/slide phía trên giúp tra lại trong tài liệu môn học.

Slide 15 của Introduction ghi **60–70% cho demo**, nhấn mạnh kịch bản, trace/log, tham số đầu vào, chỉ số đầu ra và topology. Slide còn chia tiêu chí theo hướng đề tài: có mục 40% phân tích mã nguồn mở, 10% related work ở criteria 1 và 30% chi phí vận hành/so sánh ở criteria 2; đồng thời ghi tỷ lệ phối hợp hai hướng. **Không cộng các tỷ lệ này thành một rubric duy nhất.** Cần xác nhận hướng áp dụng cho đề tài AWS nếu muốn quy đổi điểm; tài liệu này không dự đoán điểm hay thứ hạng.

Đồ án đã có phần demo và log đáng kể. Để bám tiêu chí tốt hơn, nên bổ sung related work có nguồn, chi phí tại region đang dùng và một phần giải thích mã nguồn công cụ đo. AWS Peering/TGW là dịch vụ quản lý: không có mã nguồn nội bộ trong repo để phân tích. Có thể phân tích iperf3 và mã thiết kế thí nghiệm của nhóm, nhưng không tự coi đó là đã đáp ứng toàn bộ mục mã nguồn của giảng viên.

## Đối chiếu nội dung môn với bằng chứng hiện tại

| Nội dung | Bằng chứng đã có | Phần bổ sung hữu ích |
|---|---|---|
| Latency, throughput | RTT khi rảnh và TCP một luồng, 5 lượt mỗi mode | Phân bố RTT và đo lặp theo đợt cân bằng thứ tự |
| Congestion control | Retransmission, CPU, ENA; log interval TCP | Vẽ goodput, cwnd, RTT TCP và retransmission theo thời gian |
| Tài nguyên dùng chung | Fan-in A/C/D cùng gửi vào B | Đối chiếu cửa sổ tải, CPU từng lõi và delta ENA; giữ giới hạn suy luận endpoint |
| Fairness | Chỉ số Jain giữa ba nguồn đã có | Giải thích Jain đo mức đều nhau; không chứng minh max-min fairness |
| Hàng đợi và QoS | Fan-in có cạnh tranh tại máy nhận | RTT khi có tải có kiểm soát; đọc qdisc ở endpoint |
| Percentiles | Log ping còn từng phản hồi | P50/P95 và ECDF, công bố cách tính và số phản hồi |
| Chi phí và quản trị | Terraform, topology và mô hình phí | Dự toán theo region, ngày giá, giờ attachment và GB xử lý |

Hai cặp độc lập A→B và C→D hữu ích như kiểm tra bổ sung. Fan-in liên hệ tắc nghẽn rõ hơn vì cùng nhận tại B. Cả hai không tự chứng minh đã làm bão hòa router TGW hoặc Peering.

## Có thể tận dụng log cũ ngay

Đã kiểm tra **40 JSON phía gửi** thuộc bộ dữ liệu hiện dùng: 10 lượt TCP một luồng và 30 lượt fan-in. Cả 40 file có 30 interval sau warm-up, mỗi interval có `bits_per_second`, `retransmits`, `snd_cwnd`, `snd_wnd`, `rtt`, `rttvar`. Đây là kiểm tra khả năng khai thác dữ liệu, chưa phải kết quả phân tích cơ chế mới.

Trong mã [iperf3 phiên bản 3.19.1, tcp_info.c](https://github.com/esnet/iperf/blob/3.19.1/src/tcp_info.c), `snd_cwnd` và `snd_wnd` được xuất theo byte; `rtt` và `rttvar` theo microsecond. [iperf_api.c](https://github.com/esnet/iperf/blob/3.19.1/src/iperf_api.c) thu TCP_INFO, tính chênh lệch retransmission và xuất JSON theo interval. Vì vậy RTT TCP tính bằng ms là `rtt / 1000`. Không nhân `snd_cwnd` với MSS lần nữa.

Khi phân tích:

1. Bỏ interval `omitted=true` khỏi cửa sổ chính, giữ nguyên file gốc.
2. Vẽ riêng từng lượt, từng nguồn và mode; dùng `start`, `end`, `seconds` thật.
3. Goodput interval trong JSON phía gửi là phía gửi; không đổi nhãn thành goodput phía nhận.
4. `rtt` là ước lượng RTT TCP tại thời điểm lấy TCP_INFO, không phải toàn bộ RTT mỗi segment; `rttvar` không phải độ lệch chuẩn mẫu RTT của ping.
5. Snapshot mỗi giây không ghi lại mọi biến động cwnd. Hai đường biến động cùng lúc là bằng chứng để thảo luận, chưa xác định vị trí hay nguyên nhân mất gói.

Log RTT chuẩn đang dùng còn **500 giá trị phản hồi mỗi mode**. Một bản sao thư mục Peering nằm dưới nhánh TGW; lọc theo đúng phiên chuẩn trong `scripts/build-results-report.py`, không glob rồi coi các bản sao là lượt mới. Có thể tính P50/P95 mà không ping lại. Gộp 500 phản hồi chỉ mô tả phân bố phiên đó, không biến chúng thành 500 thí nghiệm độc lập.

Chi tiết file và SHA256 trong `results/analysis/lecture-alignment-audit.json`. Các file raw không bị thay đổi.

## Công cụ nên bổ sung theo thứ tự

| Công cụ | Dùng để làm gì? | Mức ưu tiên |
|---|---|---|
| Phân tích JSON và ping bằng Python | Đồ thị TCP, P50/P95, ECDF; dùng dữ liệu đã lưu | Làm trước; không tăng tải AWS |
| `ss -tin`, `tc -s qdisc show dev ens5` | Xem trạng thái socket TCP và qdisc của Linux endpoint | Bổ sung nhẹ vào lần đo tiếp theo nếu có sẵn |
| `sar -n DEV 1` | Đối chiếu byte/gói theo giây ở NIC khi cần | Tùy chọn; sysstat đã là phụ thuộc của mpstat |
| `tcpdump` và Wireshark | Một trace ngắn minh họa ACK, retransmission, cửa sổ TCP | Tùy chọn cho phần giải thích giao thức |
| Prometheus/Grafana | Dashboard CPU/mạng cho demo observability | Sau khi hoàn thiện phân tích; không bắt buộc cho benchmark này |
| SimPy/ns-3, k6/wrk2, OTel/Loki/Tempo | Mô phỏng hàng đợi hoặc đo HTTP/microservices theo câu hỏi riêng | Chưa cần cho phạm vi hiện tại |

`tc -s` chỉ đọc hàng đợi Linux. Nó không nhìn được hàng đợi nội bộ AWS. Cấu hình `tc netem`/TBF/HTB thay đổi mạng thực nghiệm; nếu triển khai phải tách thành bài riêng và ghi rõ là độ trễ/mất gói/giới hạn do nhóm tạo ra. Không trộn vào baseline AWS.

Nếu bắt gói, dùng phiên riêng có thời lượng và tải giới hạn, lọc đúng flow. Bắt toàn bộ fan-in hàng chục Gbps có thể tạo tải CPU/đĩa và mất gói trong bộ bắt. Theo [tài liệu kernel về segmentation offloads](https://www.kernel.org/doc/html/latest/networking/segmentation-offloads.html), offload làm thay đổi cách segment xuất hiện tại host; timestamp/kích thước trong pcap không mặc nhiên là chuỗi gói trên đường truyền. [Wireshark](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvChecksums.html) cũng lưu ý checksum offload có thể làm gói bắt tại host trông như checksum sai. Không dùng các hiện tượng này để kết luận mạng AWS làm hỏng gói.

## Công thức gắn đúng với phép đo

### Cửa sổ TCP và RTT

\[
R_{window} \approx \frac{8\min(W_c,W_r)}{T_{RTT}}.
\]

- R_window: mức bit/s ước lượng do giới hạn cửa sổ khi cửa sổ được sử dụng đầy.
- W_c: cửa sổ tắc nghẽn `cwnd`, byte; W_r: cửa sổ nhận được quảng bá, byte.
- T_RTT: RTT TCP, giây; hệ số 8 đổi byte sang bit.

Đây là quan hệ để giải thích cơ chế, không phải công thức đảm bảo goodput. CPU, pacing, đường truyền, retransmission và mức sử dụng cửa sổ cũng ảnh hưởng. Dùng RTT và cửa sổ trong cùng lượt/cửa sổ; không ghép RTT ping khi rảnh ngày trước với goodput tải ngày sau để chứng minh nguyên nhân. Metadata hiện dùng `cubic`; các ví dụ Reno/Tahoe trong bài giảng không mô tả chính xác mọi bước điều chỉnh của CUBIC.

### Little và M/M/1

\[
L=\lambda W.
\]

- L: số đơn vị trung bình đang trong hệ thống được chọn (ví dụ gói).
- λ: tốc độ đến hiệu dụng của cùng nhóm đơn vị, đơn vị/giây.
- W: thời gian trung bình của cùng nhóm đơn vị trong chính hệ thống đó, giây.

Cần cùng ranh giới hệ thống, đơn vị và điều kiện trung bình ổn định. Little không đòi hỏi arrival Poisson. Tuy nhiên, số liệu hiện có chưa đo được λ và W của hàng đợi TGW. **Không lấy bit/s iperf nhân RTT ping để suy ra số gói trong hàng đợi TGW.**

Nếu minh họa lý thuyết M/M/1:

\[
\rho=\lambda/\mu<1,\qquad W=1/(\mu-\lambda),\qquad
L=\rho/(1-\rho),\qquad L_q=\rho^2/(1-\rho).
\]

μ: tốc độ phục vụ, đơn vị/giây; ρ: mức sử dụng theo mô hình; L: số đơn vị trong toàn hệ thống; L_q: số đang chờ, loại phần đang phục vụ. Giả định arrival Poisson, phục vụ exponential độc lập, một server, FIFO và trạng thái ổn định. ρ không được thay bằng phần trăm CPU B; bốn VPC không đồng nghĩa bốn server M/M/4. Chưa có bằng chứng các giả định này đúng với benchmark TCP hiện tại, nên chỉ dùng mô hình như ví dụ lý thuyết, không gán kết quả dự đoán cho AWS.

### Phân vị và mức tăng RTT khi tải

\[
\Delta Q_{95}=Q_{95,load}-Q_{95,idle}.
\]

Q95: phân vị 95% RTT phản hồi, ms; ΔQ95: chênh lệch giữa điều kiện tải và rảnh có thiết kế so sánh tương ứng, ms. Công bố phương pháp tính phân vị, số phản hồi và số mất gói riêng. Mẫu nhỏ khiến P99 phụ thuộc rất ít quan sát ở đuôi; ưu tiên P50/P95 và ECDF. `ping mdev` là độ lệch chuẩn RTT, không đồng nhất với jitter UDP của iperf3.

RTT tăng khi tải là kết quả end-to-end; chưa tách chính xác bao nhiêu do xếp hàng tại Linux, EC2, TGW hoặc thành phần khác. SLI/SLO có thể dùng để đặt mục tiêu thử nghiệm có định nghĩa rõ; vài trăm gói không chứng minh SLA hoặc availability cả tháng của AWS.

## Việc nên làm tiếp

1. **Offline trước:** đồ thị TCP từ 40 JSON và P50/P95/ECDF từ hai phiên ping chuẩn; bổ sung phần giải thích mã iperf3 3.19.1 và các giới hạn lấy mẫu.
2. **Củng cố kết luận:** thực hiện các đợt lặp cân bằng thứ tự theo kế hoạch 16 nếu ngân sách cho phép; giữ số liệu lỗi/outlier có lý do.
3. **Một bài mới trực tiếp:** RTT khi có tải với mức pacing chung cho hai mode, goodput thực đạt, CPU và delta ENA. Bài này chưa được tính hoàn thành.
4. **Hoàn thiện nộp:** related work, chi phí, tài liệu kiến trúc, slide và demo; một trace TCP ngắn là bổ sung có ích nếu cần giải thích bằng hình ảnh.

Không cần làm tất cả nội dung môn thành kịch bản mới. Giá trị của phần bổ sung nằm ở câu hỏi được trả lời, cơ chế được giải thích và số liệu có thể tái tạo. Theo slide 18, chuẩn bị để tự giải thích/sửa code và kiểm chứng nguồn; ghi AI Usage Declaration theo việc sử dụng thực tế của nhóm, không khai thay cho những việc chưa làm.
