# Kế hoạch hoàn thiện đồ án trước ngày 26 tháng 10 năm 2026

Mục tiêu là một đồ án có câu hỏi rõ, số liệu truy về file gốc, kết luận lựa chọn có căn cứ và demo tái lập. Không cần mở rộng mọi kịch bản hoặc tuyên bố kết luận đúng với mọi hệ thống. Kế hoạch này được lập ngày 06/10; các phép đo mới dưới đây **chưa thực hiện**.

## Phần đã có và phần còn thiếu

| Hạng mục | Trạng thái đã có bằng chứng |
|---|---|
| Bốn VPC EC2 và chuyển Peering TGW bằng Terraform | Đã triển khai và dùng để đo; tài liệu kiến trúc đã có |
| RTT khi rảnh và TCP một luồng | Có 5 lượt mỗi mode mỗi bài |
| Fan-in A C D tới B | Có 5 lượt mỗi mode; 146 file gốc mỗi phiên đã sao lưu và đối chiếu |
| Báo cáo kết quả | Có bảng, biểu đồ, CPU ENA, công thức, khái niệm và kết luận lựa chọn |
| Tái lập giữa các thời điểm | Chưa có thiết kế bổ sung cân bằng thứ tự được thực hiện |
| RTT khi có tải | Chưa tính là hoàn thành |
| Tổng fan-in theo cùng cửa sổ thời gian | Hiện vẫn là tổng xấp xỉ; cần kiểm tra interval và mốc thời gian gốc |
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

Đề xuất **bốn đợt bổ sung** ở các thời điểm khác nhau. Mỗi đợt có cả Peering và TGW; mỗi mode chạy ba lượt RTT khi rảnh và ba lượt TCP một luồng. Tổng là **24 lượt ping và 24 lượt TCP**, ngoài dữ liệu cũ. Bốn đợt là mức khởi đầu theo thời gian/ngân sách, không phải chứng minh đủ công suất thống kê.

Phân bổ hai đợt Peering trước, hai đợt TGW trước; xáo thứ tự bốn đợt và lưu lịch trước khi chạy. Đây là cách áp dụng ý tưởng block theo thời gian và cân bằng thứ tự từ [NIST randomized block designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm). Không gọi việc luôn chạy Peering trước là ngẫu nhiên. Không ghép lượt 1 của hai phiên cũ thành cặp đồng thời.

Giữ cấu hình RTT 100 gói, 56 byte payload, interval 0,2 giây; TCP P1, omit 5 giây, đo 30 giây. Giữ EC2, AZ, MTU, kernel/công cụ, congestion control, chiều truyền, warm-up và nghỉ giống nhau giữa mode. Sau đổi mode, kiểm tra route hai chiều bằng AWS và connectivity; chỉ đo khi thay đổi đã ổn định. Mỗi chế độ phải có cùng quy tắc warm-up/nghỉ. Nghỉ cố định không chứng minh burst credits đã hồi phục, vì vậy lưu lịch hoạt động và nêu đây là yếu tố chưa quan sát trực tiếp.

Lưu raw JSON/ping, mã thoát, route snapshot, metadata và CPU/ENA A/B trước sau từng lượt. Snapshot route dùng API có chọn trường định tuyến, không xuất credentials. Nếu lượt lỗi, lưu nguyên log và lý do chạy lại. Không bỏ outlier chỉ vì kết quả xấu; không dừng lấy mẫu chỉ khi p-value đã nhỏ.

### Phân tích theo đợt và khoảng tin cậy

Với đợt b, lấy trung bình ba lượt của từng mode rồi tính:

\[
d_b = \bar{x}_{TGW,b} - \bar{x}_{Peering,b},\qquad
CI_{95\%} = \bar d \pm t_{0.975,B-1}\frac{s_d}{\sqrt B}.
\]

Trong đó tính từ B chênh lệch theo đợt:

\[
\bar d=\frac{1}{B}\sum_{b=1}^{B}d_b,\qquad
s_d=\sqrt{\frac{\sum_{b=1}^{B}(d_b-\bar d)^2}{B-1}}.
\]

Với B=4, t_{0.975,3} ≈ 3,18245 nên nửa độ rộng CI ≈ 1,59122s_d. Đây là ví dụ thiết kế, chưa có CI thực nghiệm theo đợt. d_b>0 nghĩa TGW có RTT cao hơn khi xét RTT, nhưng có goodput cao hơn khi xét goodput; dấu dương không có cùng ý nghĩa tốt/xấu cho hai chỉ số.

- b: chỉ số đợt; B: số đợt đã thực hiện đủ hai mode, ban đầu đề xuất B=4.
- x: chỉ số đang so; dùng ms cho RTT hoặc Gbps cho goodput, không trộn đơn vị.
- d_b: chênh lệch trong đợt; d trung bình: trung bình B chênh lệch; s_d: SD mẫu giữa B chênh lệch.
- t: phân vị Student t với B−1 bậc tự do. Khoảng tin cậy này yêu cầu chênh lệch giữa các đợt đủ độc lập và phân bố phù hợp; B nhỏ khiến việc đánh giá giả định yếu. Nếu giả định không phù hợp, báo cáo mô tả theo đợt và cân nhắc thêm dữ liệu, không ép kiểm định.

CI chứa 0 không chứng minh hai mode tương đương. Muốn đánh giá tương đương thực tiễn phải định trước biên chênh lệch chấp nhận được dựa trên nhu cầu ứng dụng và thiết kế phép kiểm định tương đương; không lấy chênh lệch đã thấy làm biên. Không dùng số gói ping hoặc số interval thay cho B. CI không sửa được sai lệch thiết kế hoặc loại bỏ ảnh hưởng credits.

Tiêu chí xong: bảng mỗi đợt và biểu đồ chênh lệch có độ bất định; kết luận nêu cỡ ảnh hưởng, điều kiện áp dụng và việc khác biệt có nhất quán hay không. Nếu CI rộng, công bố đúng như vậy.

## Ưu tiên 3 Một bài mới có ý nghĩa ứng dụng

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
| 09–12/10 | Bốn đợt bổ sung RTT khi rảnh và TCP một luồng | Đủ log hai mode, thứ tự cân bằng và bằng chứng route |
| 13–16/10 | Phân tích các đợt; bài RTT khi có tải nếu ngân sách cho phép | Có đồ thị tải độ trễ, CPU ENA; phân biệt đo thử và chính thức |
| 17–20/10 | Ghép báo cáo đầy đủ, chi phí, công thức và tài liệu tham khảo | Các số truy về raw, nhất quán thuật ngữ và đơn vị |
| 21–23/10 | Repo GitHub sạch, slide, demo và video dự phòng | Chạy thử từ tài liệu; rà không lẫn dữ liệu mô phỏng với thực nghiệm |
| 24–25/10 | Tập bảo vệ, sửa trình bày, chốt bản nộp | Không mở thêm kịch bản; trả lời được câu hỏi phương pháp |
| 26/10 | Báo cáo | Có bản nộp, slide và bằng chứng dự phòng |

## Việc chưa cần mở rộng

Chưa ưu tiên thêm VPC/EC2, cross-region, UDP, thay MTU hoặc thử mọi số luồng. Bài hai cặp độc lập giữ làm bổ sung, không cần đo TGW đối ứng chỉ để tăng số bài. Thay receiver lớn hơn có thể giúp kiểm tra giả thuyết endpoint nhưng thay đổi chi phí/cấu hình; chỉ lên phương án khi kết quả bổ sung cần giải đáp câu hỏi đó.

Demo phân đoạn TGW có thể minh họa khả năng nhiều bảng route sau khi chốt dữ liệu hiệu năng, nhưng chỉ làm nếu cần chứng minh quản trị bằng thực hành. Nó không thay thế benchmark và chưa có trong trạng thái đã hoàn thành.

## Chuẩn bị bảo vệ

Chuẩn bị câu trả lời có trỏ nguồn cho các câu: vì sao chọn bốn VPC; sáu Peering so với bốn attachment có công bằng không; route nào chứng minh mode; RTT khác độ trễ một chiều thế nào; vì sao throughput không phải năng lực dịch vụ; ENA tăng có phải packet loss không; vì sao chưa kết luận tương đương; tác động credits; lựa chọn theo chi phí/quy mô ra sao.

Điểm mạnh nên trình bày là hạ tầng tái lập, số liệu thực có provenance, phân tích endpoint và kết luận lựa chọn theo tiêu chí. Không có thiết kế thực nghiệm nào khiến đồ án miễn bị phản biện; giải thích đúng phạm vi và bảo vệ được bằng chứng đáng tin hơn lời khẳng định tuyệt đối hoặc cam kết hơn nhóm khác.
