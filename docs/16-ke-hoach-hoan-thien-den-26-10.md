# Kế hoạch hoàn thiện đồ án trước ngày 26 tháng 10 năm 2026

Mục tiêu là một đồ án có câu hỏi rõ, số liệu truy về file gốc, kết luận lựa chọn có căn cứ và demo tái lập. Không cần mở rộng mọi kịch bản hoặc tuyên bố kết luận đúng với mọi hệ thống. Kế hoạch lập ngày 06/10 và cập nhật ngày 13/10 sau ba block RTT và một block slots hợp lệ. [Trạng thái và lịch tự tiếp tục](32-trang-thai-xac-nhan.md) ghi rõ việc còn thiếu.

## Phần đã có và phần còn thiếu

| Hạng mục | Trạng thái đã có bằng chứng |
|---|---|
| Bốn VPC EC2 và chuyển Peering TGW bằng Terraform | Đã khôi phục 12/10: 100 tạo, 0 sửa/xóa; full mesh pass |
| RTT khi rảnh và TCP một luồng | Có 5 lượt mỗi mode mỗi bài |
| Fan-in A C D tới B | Có 5 lượt mỗi mode; 146 file gốc mỗi phiên đã sao lưu và đối chiếu |
| Báo cáo kết quả | Có bảng, biểu đồ, CPU ENA, công thức, khái niệm và kết luận lựa chọn |
| Tái lập giữa các thời điểm | Protocol 16 block đã khóa; hoàn tất 3/16 block RTT hợp lệ trên hai ngày |
| RTT khi có tải | Chưa tính là hoàn thành |
| Ứng dụng HTTP fan-out, P95 và tỷ lệ đúng hạn | Pilot/calibration 12/10 đã kiểm tra 62.200 requests; chưa suy luận xác nhận |
| Distributed tracing ứng dụng | 12 traces thật/120 spans; replay Collector → Tempo → Grafana local, chưa OTLP live |
| Can thiệp slots và log hàng đợi | Engineering 84.000 requests tách biệt; 1/16 block xác nhận với 84.000 requests mới đã kiểm tra; thiết kế đã khóa |
| Tổng fan-in theo cùng cửa sổ thời gian | Đã audit 30 JSON: interval phía gửi, tổng phía nhận và server text; thiếu receiver interval bytes/timestamp để tính chính xác; giữ tổng xấp xỉ |
| Báo cáo toàn bộ slide demo repo nộp | Cần hoàn thiện và rà soát; chương kết quả không thay cho báo cáo đầy đủ |

Sáu bộ đo chính đã đủ cho phạm vi tối thiểu đã chọn. Ngày 06/10 đã đối chiếu slide 15 của Introduction1: demo được ghi 60–70%, có tiêu chí mã nguồn/related work và hướng chi phí/so sánh, với tỷ lệ phối hợp theo hướng đề tài. Chưa xác nhận cách áp dụng các hướng cho đề tài AWS nên không cộng tỷ lệ hoặc quy đổi thành phần trăm hoàn thành/điểm số. Xem [đối chiếu bài giảng và công cụ](17-doi-chieu-bai-giang-va-cong-cu.md).

## Ba câu hỏi nghiên cứu cần giữ

1. Khi giữ nguyên EC2, AZ, MTU và tải, RTT khi rảnh và goodput TCP một luồng khác nhau bao nhiêu giữa hai đường định tuyến? Khác biệt có lặp lại qua các đợt không?
2. Khi nhiều nguồn cùng gửi vào B, dấu hiệu giới hạn endpoint xuất hiện như thế nào? Có thể mô tả goodput, CPU và ENA mà không nhầm thành giới hạn của TGW/Peering không?
3. Khi nào nên chọn Peering hoặc TGW nếu xét đồng thời hiệu năng quan sát, quy mô kết nối và chi phí? Lợi thế kiến trúc phải được tách khỏi lợi thế đã đo.

RTT khi có tải là phần bổ sung trực tiếp cho câu hỏi thứ hai. Không cần thay tên đồ án hoặc dựng thêm VPC để trả lời các câu hỏi này.

## Ưu tiên 1 Củng cố bằng dữ liệu đã có

Thực hiện trước khi chạy tải mới:

- Rà metadata, route mode, thời gian UTC và nơi lưu raw của sáu bộ. Giữ dữ liệu hủy hoặc lỗi nhưng đánh dấu lý do không đưa vào tổng hợp.
- Tận dụng log cũ: kiểm tra ngày 06/10 xác nhận 40 JSON TCP có cwnd, cửa sổ nhận, RTT TCP, retransmission và 30 interval sau warm-up mỗi file. Lập đồ thị theo thời gian; tính P50/P95/ECDF từ phiên ping chuẩn. Đây là phân tích bổ sung chưa thực hiện, không yêu cầu thêm tải AWS.
- Bổ sung related work, phần giải thích mã iperf3 phiên bản đang dùng và chi phí vận hành để liên hệ tiêu chí trong bài giảng. Không coi mã Terraform/iperf3 là mã nguồn nội bộ Peering/TGW.
- Kiểm tra JSON interval phía nhận, thời điểm bắt đầu nội bộ, đồng bộ đồng hồ và khoảng bỏ 5 giây để xác định có căn chỉnh được các nguồn fan-in hay không. Chỉ dùng wrapper start/end thì phải ghi là ước lượng, không đổi tên thành cửa sổ chính xác.
- Nếu đủ thông tin, tổng hợp byte nhận trong cửa sổ chung của mỗi lượt, công bố quy tắc với interval cắt biên. Nội suy theo tỷ lệ thời lượng là một giả định và phải ghi rõ. Nếu thiếu mốc, giữ tổng xấp xỉ hiện có; không dựng độ chính xác giả.
- Tách bảng số liệu thực nghiệm, bảng đặc điểm kiến trúc từ AWS và bảng giả định chi phí. Viết một kết luận chính, gom hạn chế vào đoạn riêng.

Tiêu chí xong: mỗi giá trị trên bảng/biểu đồ có đường dẫn nguồn, đơn vị, cửa sổ tính và phương pháp tái tạo; có danh sách bài chưa đo.

Định nghĩa tổng goodput theo cửa sổ chung W=[T_0,T_1]:

\[
G_{sum}(W)=\frac{8\sum_i R_i(W)}{(T_1-T_0)10^9}\quad\text{Gbps}.
\]

R_i(W): byte payload nhận từ nguồn i trong đúng W; T_0,T_1 tính bằng giây. Cộng goodput trung bình của cửa sổ riêng từng nguồn không mặc nhiên bằng đại lượng này. Số hiện có vẫn ghi tổng xấp xỉ; chưa có kết quả tổng chung cửa sổ đã kiểm chứng.

## Ưu tiên 2 Đo lặp RTT và TCP một luồng

Cập nhật 13/10 theo hướng người dùng chọn: RTT xác nhận dùng
[protocol 16 block](23-thiet-ke-xac-nhan-rtt.md), thay cho mức khởi đầu bốn
đợt RTT trước đây. Hạ tầng mới đã dựng và **3/16 block** đã hoàn tất:
`d₁=+0,2303 ms`, `d₂=+0,2397 ms`, `d₃=+0,4257 ms`, có hai thứ tự,
không mất phản hồi. Block 3 bắt đầu 11:10:24 ngày 13/10; toàn bộ 16 block phải trải trên
ít nhất bốn ngày và start cách nhau ít nhất hai giờ.

Thiết kế bốn đợt và CI Student t cũ được thay thế trước khi thu dữ liệu xác
nhận. Phân tích chính hiện dùng biến vượt margin `Z_b=1{d_b>0,1 ms}`, exact
binomial một phía, cận exact của xác suất vượt margin và cận order-statistic
cho median. Cần `K≥12/16` ở mức `α=0,05`; không dừng sớm. Công thức, giả định
và câu kết luận được khóa trong tài liệu 23. Phần TCP một luồng và loaded RTT
không nhập vào `K`.

## Ưu tiên 3 Một bài mới có ý nghĩa ứng dụng

Cập nhật theo yêu cầu ngày 12/10: ưu tiên **ứng dụng A → B → C/D** để đo thời
gian hoàn thành và tỷ lệ đúng hạn theo tải. Có pipeline traces cho phiên
kiểm tra riêng. Xem [thiết kế ứng dụng và công thức](25-ung-dung-phan-tan-va-qos.md).

Đã chạy hai phiên khám phá tối 12/10, xem [kết quả và giới hạn](26-ket-qua-pilot-ung-dung.md).
Tải 800 yêu cầu/s làm tỷ lệ đúng hạn giảm còn khoảng 6% ở cả hai mạng.
Việc tiếp theo là can thiệp slots 8/16 và các phiên độc lập theo
[thiết kế xác nhận ứng dụng](../experiments/application-qos/study-plan.md),
không chỉ đo lại các mức tải cũ. Không gộp pilot vào mẫu xác nhận.
Pilot là đợt thăm dò tách biệt, không thay protocol 16 block RTT. Kế hoạch
loaded RTT dưới đây giữ làm phương án tùy chọn, chưa tự động chạy hoặc
được tính là phần bắt buộc bên cạnh nghiên cứu ứng dụng.

**RTT khi có tải TCP**, giữ A/B làm cặp đo, cùng cấu hình cho cả hai mode. Đo idle và hai mức tải giới hạn phía gửi bằng pacing, ví dụ 0,25 và 0,50 Gbps tổng cho P1. Đây là mức đề xuất, cần chạy thử ngắn để kiểm tra goodput thực đạt và delta ENA; không coi giá trị -b của TCP là tải thực tế được đảm bảo.

Mỗi điều kiện có ba lượt; mỗi mode có ba điều kiện nên tổng **18 lượt RTT**, trong đó **12 lượt có tải TCP và 6 lượt idle**. Ping chỉ lấy mẫu trong cửa sổ tải ổn định, bỏ warm-up nhất quán. Giữ nguyên mức tải đặt trước giữa hai mode và báo cáo cả mức đặt lẫn goodput đạt được. Lưu RTT từng gói, receiver interval, CPU từng lõi và ENA trước/sau đúng cửa sổ. Báo cáo mean, median và p95 cùng số mẫu/cách tính phân vị.

Nếu mức đề xuất vẫn gây allowance counter tăng, giữ dữ liệu và phân loại là tải chạm giới hạn endpoint; không âm thầm giảm tải riêng một mode. Điều này liên hệ trực tiếp với [AWS ENA metrics](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html) và [cơ chế bandwidth EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-network-bandwidth.html).

Tiêu chí xong: trả lời được độ trễ tăng bao nhiêu khi tải tăng, goodput có đúng mức đặt không và giới hạn endpoint có xuất hiện không. Bài này không nhằm ép TGW hoặc Peering thua; kết quả gần nhau vẫn có giá trị. Một phiên mở rộng chưa đủ để suy rộng độ trễ khi tải trong mọi điều kiện.

## Chi phí và quy mô kết nối

Giữ phần này là phân tích kiến trúc và mô hình chi phí, không gọi là benchmark quản trị đã đo.

- Toàn lưới N VPC: N(N−1)/2 Peering hoặc một TGW với N attachment. Tăng từ 4 lên 5 VPC cần thêm 4 Peering hoặc 1 attachment; còn route và chính sách vẫn cần cập nhật ở cả hai phương án.
- Cấu hình hiện tại giữ route riêng tới mỗi CIDR: 12 route liên VPC ở bảng subnet cho bốn VPC, cả hai mode. TGW có thể thiết kế route tổng hợp trong mô hình khác; không gán lợi ích đó cho code chưa thực hiện.
- [AWS Peering](https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html) không thu phí tạo kết nối và truyền cùng AZ miễn phí. EC2/EIP vẫn là khoản riêng.
- [AWS TGW pricing](https://aws.amazon.com/transit-gateway/pricing/) tính attachment theo giờ và xử lý GB gửi vào TGW. Cần xác minh đơn giá us-east-1 tại ngày dự toán và làm tròn giờ theo chính sách; không chép ví dụ Ohio thành giá đã xác minh Virginia.

Mô hình phần TGW:

\[
C_{TGW} = \sum_{j=1}^{N} h_j r_h + V_{in}r_g.
\]

C_TGW: USD phí TGW; h_j: giờ bị tính phí attachment j; r_h: USD/attachment/giờ tại region; V_in: tổng dung lượng gửi vào TGW tính theo GB quy định của AWS; r_g: USD/GB xử lý. Không tự nhân đôi payload chỉ vì gói đi vào attachment nguồn và ra attachment đích; chiều ngược ACK hoặc tải ngược có dung lượng riêng. Mô hình chưa gồm EC2, EBS, IPv4/EIP, data transfer khác, thuế hay ưu đãi.

Ước lượng dung lượng trước khi đo: V_payload ≈ G × 10^9 × t / (8 × 2^30) GiB, trong đó G là Gbps phía ứng dụng và t là số giây tạo tải. Nếu giả định 4,6 Gbps giữ đều suốt 35 giây thì được 20.125.000.000 byte = 20,125 GB thập phân = 18,742867 GiB. Chỉ 30 giây ở cùng tốc độ tương ứng 17,25 GB = 16,065314 GiB. Tốc độ trung bình của cửa sổ đo 30 giây không chứng minh 5 giây warm-up đạt cùng tốc độ; nhân với 35 giây chỉ là giả định dự toán. Trang giá AWS ghi GB bằng 1024 MB; khi tính phí phải dùng quy ước billing của AWS và tránh lẫn với GB thập phân. Các ước lượng payload chưa gồm ACK, truyền lại và overhead. Do đó đo thêm hàng chục lượt cần dự toán trước; không chỉ tính tiền EC2 theo phút. Chi phí actual phải lấy billing/metering phù hợp, không suy ra chính xác từ payload iperf3.

## Lịch hoàn thiện đề xuất

| Thời gian | Việc chính | Điều kiện chốt |
|---|---|---|
| 06–08/10 | Rà raw, kết luận, glossary, phạm vi và thiết kế thí nghiệm | Câu hỏi và quy tắc tổng hợp được ghi trước |
| 12–16/10 | Hoàn tất 16 block RTT xác nhận trên ≥4 ngày | Đủ log hai mode, spacing ≥2 giờ, thứ tự cân bằng và bằng chứng route |
| 17–18/10 | Chốt suy luận và chạy loaded RTT khám phá | Có effect size, cận exact, đồ thị tải độ trễ, CPU và ENA |
| 17–20/10 | Ghép báo cáo đầy đủ, chi phí, công thức và tài liệu tham khảo | Các số truy về raw, nhất quán thuật ngữ và đơn vị |
| 21–23/10 | Repo GitHub sạch, slide, demo và video dự phòng | Chạy thử từ tài liệu; rà không lẫn dữ liệu mô phỏng với thực nghiệm |
| 24–25/10 | Tập bảo vệ, sửa trình bày, chốt bản nộp | Không mở thêm kịch bản; trả lời được câu hỏi phương pháp |
| 26/10 | Báo cáo | Có bản nộp, slide và bằng chứng dự phòng |

## Việc chưa cần mở rộng

Chưa ưu tiên thêm VPC/EC2, cross-region, UDP, thay MTU hoặc thử mọi số luồng. Bài hai cặp độc lập giữ làm bổ sung, không cần đo TGW đối ứng chỉ để tăng số bài. Thay receiver lớn hơn có thể giúp kiểm tra giả thuyết endpoint nhưng thay đổi chi phí/cấu hình; chỉ lên phương án khi kết quả bổ sung cần giải đáp câu hỏi đó.

Demo phân đoạn TGW có thể minh họa khả năng nhiều bảng route sau khi chốt dữ liệu hiệu năng, nhưng chỉ làm nếu cần chứng minh quản trị bằng thực hành. Nó không thay thế benchmark và chưa có trong trạng thái đã hoàn thành.

## Chuẩn bị bảo vệ

Cập nhật 12/10: phân tích offline ECDF/phân vị/tần suất RTT vượt ngưỡng
và đồ thị TCP một luồng đã hoàn thành; xem [phần thống kê](20-thong-ke-va-xac-suat.md).
Bốn đợt đề xuất không bảo đảm đủ công suất thống kê. Phần mới giải thích
giả thuyết/CI theo đợt và giới hạn exact sign test với B nhỏ. Trước khi đo,
chốt đầu ra chính, số đợt, độ chính xác mong muốn, phương pháp và ngân sách;
không dừng lấy mẫu ngay khi p-value nhỏ. Hai block đã hoàn tất nhưng chưa đủ để
đưa ra kết luận suy diễn.

Chuẩn bị câu trả lời có trỏ nguồn cho các câu: vì sao chọn bốn VPC; sáu Peering so với bốn attachment có công bằng không; route nào chứng minh mode; RTT khác độ trễ một chiều thế nào; vì sao throughput không phải năng lực dịch vụ; ENA tăng có phải packet loss không; vì sao chưa kết luận tương đương; tác động credits; lựa chọn theo chi phí/quy mô ra sao.

Điểm mạnh nên trình bày là hạ tầng tái lập, số liệu thực có provenance, phân tích endpoint và kết luận lựa chọn theo tiêu chí. Không có thiết kế thực nghiệm nào khiến đồ án miễn bị phản biện; giải thích đúng phạm vi và bảo vệ được bằng chứng đáng tin hơn lời khẳng định tuyệt đối hoặc cam kết hơn nhóm khác.
