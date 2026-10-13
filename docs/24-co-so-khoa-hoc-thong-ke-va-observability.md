# Cơ sở khoa học, thống kê và observability của đồ án

## Kết luận mà đồ án đang hướng tới

Đồ án không cố chứng minh một dịch vụ AWS tốt hơn trong mọi tình huống. Câu
hỏi xác nhận hẹp và kiểm chứng được là:

> Trong cohort bốn VPC, cặp EC2 A–B `c6i.large` cùng AZ, cùng AMI, MTU 1500
> và các khung thời gian đã lấy mẫu, RTT idle qua TGW có cao hơn Peering trên
> 0,1 ms trong đa số block hay không?

Thiết kế 16 block ghép cặp, thứ tự cân bằng và ngẫu nhiên hóa trước giúp loại
bớt ảnh hưởng của thời điểm và thứ tự. Mỗi block dùng đúng hai máy, chỉ đổi
route, rồi đo cả Peering lẫn TGW. Ba lượt trong một mode là lặp kỹ thuật; đơn
vị suy luận vẫn là block. Dữ liệu 05–06/10 dùng để khám phá câu hỏi và không
được trộn vào phép xác nhận.

Kết luận kiến trúc là một câu hỏi khác và có thể phát biểu ngay từ đặc tính
dịch vụ: Peering là kết nối điểm–điểm, không chuyển tiếp; full mesh `n` VPC
cần `n(n-1)/2` peering. TGW dùng mô hình hub-and-spoke và cần `n` attachment.
Với bốn VPC, hai con số là 6 và 4. AWS mô tả Peering có độ trễ thấp nhất và
TGW thêm một hop, đồng thời TGW quản lý tập trung và mở rộng tốt hơn.

Nguồn AWS:

- [VPC Peering là điểm–điểm, không transitive và công thức full mesh](https://docs.aws.amazon.com/whitepapers/latest/building-scalable-secure-multi-vpc-network-infrastructure/vpc-peering.html).
- [Bảng so sánh Peering và TGW về kiến trúc, scale, latency và visibility](https://docs.aws.amazon.com/whitepapers/latest/building-scalable-secure-multi-vpc-network-infrastructure/transit-vpc-solution.html).
- [TGW hub-and-spoke và quản lý tập trung](https://docs.aws.amazon.com/whitepapers/latest/building-scalable-secure-multi-vpc-network-infrastructure/transit-gateway.html).

## Kết quả xác nhận hiện có

Block 1 bắt đầu `2026-10-12T09:41:00Z`, thứ tự Peering rồi TGW. Cả hai mode
nhận đủ 300/300 phản hồi và không có lỗi kiểm soát.

| Đại lượng | Peering | TGW | TGW − Peering |
|---|---:|---:|---:|
| Mean của 3 RTT avg | 0,2113 ms | 0,4417 ms | +0,2303 ms |
| Packet chính | 300/300 | 300/300 | 0 missing |
| TTL | 127 | 126 | phù hợp TGW thêm một hop |

Block 2 bắt đầu `2026-10-12T14:26:56Z`, đo TGW rồi Peering: Peering 0,2067 ms,
TGW 0,4463 ms, chênh +0,2397 ms, không mất packet. Cả hai block vượt margin
đã chốt `δ=0,1 ms`, nên `Z₁=Z₂=1`. Block 3 bắt đầu 11:10:24 ngày 13/10:
Peering 0,1900 ms, TGW 0,6157 ms, chênh +0,4257 ms, không mất phản hồi.
Hiện có 3/16 block trên hai ngày; không tính p-value kết luận và không dừng
sớm. [Trạng thái và lịch](32-trang-thai-xac-nhan.md) lấy từ analysis mới nhất. Cohort phải giữ hai
instance ID `i-089bae0de9ec6bc4e`, `i-0484f42b82795f765` và TGW
`tgw-036e551008b8c0805` trong toàn đợt.

## Mô hình toán và ý nghĩa từng ký hiệu

### Hiệu ứng ghép cặp

Với mode `m`, block `b` và lượt kỹ thuật `j`:

$$
\bar{x}_{m,b}=\frac{1}{3}\sum_{j=1}^{3}x_{m,b,j},\qquad
d_b=\bar{x}_{TGW,b}-\bar{x}_{Peering,b}.
$$

`x` và `d` có đơn vị ms. Ghép cặp làm cho hai mode trong cùng block chia sẻ
gần cùng cohort và khung thời gian. Điều này không xóa mọi nhiễu cloud, nhưng
tốt hơn so sánh hai ngày tách rời.

Đặt:

$$
Z_b=\mathbf{1}(d_b>\delta),\quad \delta=0,1\text{ ms},\quad
K=\sum_{b=1}^{16}Z_b.
$$

`Z_b` là biến Bernoulli và `K` là số block vượt margin. Giả thuyết chính:

$$
H_0:\pi\le 0,5,\qquad H_1:\pi>0,5,
$$

trong đó `π=P(d_b>δ)` của quá trình lấy block đã định nghĩa. Ở biên của
`H0`, p-value exact một phía là:

$$
p=\sum_{j=K}^{16}{16\choose j}(0,5)^{16}.
$$

Với `α=0,05`, cần `K≥12`; `K=12` cho `p=0,0384064`. Đây là biến thể bảo thủ
của paired sign test vì tie `d_b=δ` được tính là không vượt margin. [NIST giải
thích thống kê dấu theo phân bố binomial](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/signtest.htm)
và [cận exact cho tỷ lệ binomial](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm).

Ngưỡng quyết định và cận dưới Clopper–Pearson một phía 95% đã được tính trước:

| `K` trên 16 block | p-value exact một phía | Cận dưới 95% của `π` |
|---:|---:|---:|
| 12 | 0,038406 | 0,515604 |
| 13 | 0,010635 | 0,583428 |
| 14 | 0,002090 | 0,656175 |
| 15 | 0,000259 | 0,736043 |
| 16 | 0,000015 | 0,829250 |

Nếu xác suất thật `π=0,8`, xác suất thiết kế đạt `K≥12` là khoảng 79,8%; nếu
`π=0,85` thì khoảng 92,1%. Đây là công suất theo mô hình Bernoulli của block,
không phải xác suất kết luận hiện tại đúng. Script phân tích tính lại toàn bộ
các giá trị từ raw data sau block 16.

### Độ bất định và tail latency

Ngoài quyết định `K≥12`, báo cáo phải công bố `d_b` từng block, mean, median,
min/max, hai nhóm thứ tự và cận dưới exact 95% của `π`. Không chỉ báo mean.
P50 mô tả trung tâm; P95/P99 mô tả đuôi. Dean và Barroso chỉ ra rằng latency
hiếm nhưng cao có thể chi phối hệ thống fan-out quy mô lớn; vì vậy report giữ
cả ECDF và percentile thay vì một con số trung bình.

Nguồn: [Dean & Barroso, “The Tail at Scale”, CACM 2013](https://research.google/pubs/the-tail-at-scale/).

### RTT và thành phần hàng đợi

Một cách phân rã khái niệm:

$$
RTT \approx d_{host}+
\sum_{h\in P_{forward}}(d_{prop,h}+d_{tx,h}+d_{proc,h}+d_{queue,h})+
\sum_{h\in P_{return}}(d_{prop,h}+d_{tx,h}+d_{proc,h}+d_{queue,h}).
$$

`d_prop` là trễ lan truyền, `d_tx=L/R` là thời gian đẩy gói dài `L` bit lên
đường tốc độ `R` bit/s, `d_proc` là xử lý và `d_queue` là chờ hàng đợi. Công
thức dùng `P_forward` và `P_return` cho đường đi/về, `d_host` cho xử lý ở hai
endpoint. Chỉ khi giả định hai chiều đối xứng mới dùng hai lần tổng một chiều.
Công thức giúp giải thích vì sao thêm một hop có thể tăng RTT; số đo end-to-end
không tự xác định chính xác thành phần nào tạo ra chênh lệch.

Với mô hình M/M/1 lý tưởng:

$$
\rho=\frac{\lambda}{\mu}<1,\qquad
W=\frac{1}{\mu-\lambda},\qquad
W_q=\frac{\rho}{\mu-\lambda},\qquad L=\lambda W.
$$

`λ` là tốc độ đến, `μ` là tốc độ phục vụ, `ρ` là mức sử dụng, `W` là thời
gian trong hệ thống, `W_q` là thời gian đợi và `L` là số khách trung bình.
Khi `ρ→1`, `W_q` tăng phi tuyến. Đây là cơ sở cho bài RTT dưới tải và liên hệ
Little `L=λW` ở bài giảng Lecture 02 trang 62–66. Không fit M/M/1 vào dữ liệu
ping nếu chưa kiểm tra arrival Poisson và service exponential; Lecture 02
trang 32 và 68 cũng yêu cầu kiểm tra giả định này.

### TCP, tải và nghẽn

Bài giảng Congestion Control trang 3–18 mô tả nghẽn qua trễ hàng đợi, mất gói,
retransmission và AIMD. Quan hệ gần đúng của một sender:

$$
rate\approx\frac{cwnd}{RTT}.
$$

RTT cao làm chậm tốc độ tăng cửa sổ; loss/retransmission làm giảm goodput.
Vì vậy bài loaded RTT sẽ báo rate thực nhận, RTT percentile, retransmission,
CPU và delta bộ đếm ENA cùng lúc. Không dùng riêng retransmit để quy nguyên
nhân cho Peering hoặc TGW.

Nếu đo nhiều flow, dùng Jain fairness index:

$$
J=\frac{(\sum_{i=1}^{n}x_i)^2}{n\sum_{i=1}^{n}x_i^2},\qquad \frac1n\le J\le1.
$$

`x_i` là goodput của flow `i`. `J≈1` nghĩa chia sẻ đều; throughput tổng cao
không đồng nghĩa công bằng.

## Liên hệ với bài giảng và tiêu chí môn học

| Nội dung môn | Phần áp dụng trong đồ án | Bằng chứng |
|---|---|---|
| Performance measurement | ping, iperf3, CPU, ENA, route snapshot | raw JSON/text và hash |
| Queueing | `ρ`, `W_q`, Little `L=λW` | loaded RTT; không áp mô hình khi chưa kiểm định giả định |
| Congestion control | RTT, cwnd, retransmission, goodput | iperf3 JSON và TCP/ENA counters |
| QoS thống kê | mean, P50, P95, P99, loss | ECDF/percentile, không chỉ average |
| Cloud observability | metrics, logs, traces | lớp demo riêng, không làm nhiễu phép thử chính |
| Project seminar | topology, input, output, trace/log, source code, related work | Terraform, scripts, raw result, tài liệu và nguồn |

Slide Introduction trang 12 yêu cầu queueing, simulation/real systems, traffic
management và công cụ đo. Trang 15 chấm mạnh phần demo, kịch bản, trace/log,
input, output, topology và related work. Cấu trúc repo hiện bám trực tiếp các
điểm này.

## Đối chiếu phương pháp với nghiên cứu khoa học

| Nguồn | Ý chính dùng trong đồ án | Cách áp dụng |
|---|---|---|
| Kalibera & Jones, 2013 | Hệ thống hiện đại không xác định; cần repetition và lượng hóa bất định | 16 block, không coi 9.600 packet là độc lập |
| Leitner & Cito, 2016 | IaaS có biến thiên và ảnh hưởng multitenancy | phân bố qua ≥4 ngày, không kết luận từ một phiên |
| Li et al., CloudCmp, 2010 | Benchmark cloud cần fairness, representativeness và kiểm soát chi phí | cùng endpoint/cấu hình; chỉ đổi route; lưu cost |
| Dean & Barroso, 2013 | Tail latency quan trọng ở hệ thống fan-out | báo P95/P99/ECDF cùng mean |

Nguồn chính:

- [Kalibera & Jones, “Rigorous Benchmarking in Reasonable Time”](https://kar.kent.ac.uk/33611/).
- [Leitner & Cito, “Patterns in the Chaos”](https://arxiv.org/abs/1411.2429).
- [Li et al., “CloudCmp: Comparing Public Cloud Providers”](https://www.microsoft.com/en-us/research/publication/cloudcmp-comparing-public-cloud-providers/).

## Có nên dùng OpenTelemetry, Collector và Grafana?

**Có, nhưng dùng cho observability phụ trợ và demo, không dùng làm nguồn bằng
chứng chính của 16 block RTT.**

Bộ cấu hình agent/gateway, Prometheus và Grafana đã được chuẩn bị trong
[`monitoring`](../monitoring/README.md), có sơ đồ, dashboard provision tự động,
SSH tunnel và hướng dẫn dừng agent. Compose schema, JSON dashboard và tag
image đã được kiểm tra. Tối 12/10 stack local đã chạy và replay 12 traces thật
/120 spans qua Collector → Tempo → Grafana; xem [bằng chứng runtime](../results/application-qos-calibration-v2/1c0d1fb25e544fb0bee95078cbfc265c/observability-validation.json).
Chưa chạy hostmetrics agent hoặc OTLP live từ EC2. Không mô tả replay như
đợt xác nhận hiệu năng hoặc dữ liệu CPU/network đã gửi trực tiếp lên dashboard.

OpenTelemetry Collector có thể chạy dạng agent hoặc gateway. Host Metrics
receiver đọc CPU, memory, disk, network và TCP connection theo chu kỳ; mặc
định receiver hỗ trợ `collection_interval`. Prometheus lưu time series và
Grafana hiển thị. Traces chỉ có ích khi có ứng dụng nhiều service đã được
instrument; `ping` và `iperf3` không tự sinh application span có ý nghĩa.

Nguồn:

- [Kiến trúc agent/gateway của OpenTelemetry Collector](https://opentelemetry.io/docs/collector/architecture/).
- [Host Metrics receiver và các scraper CPU/network](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/README.md).
- [TGW có CloudWatch metrics, TGW Flow Logs và VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-monitoring.html).

Collector trên A/B sẽ thức dậy định kỳ, đọc `/proc`, dùng CPU, ghi log và gửi
network traffic. Chênh lệch RTT cần xác nhận chỉ khoảng 0,1–0,3 ms, nên bật
agent trong cửa sổ primary sẽ tạo thêm một biến gây nhiễu. Thiết kế triển khai:

1. **Primary RTT:** OTel/Prometheus/Grafana tắt trên A/B. Dùng raw ping,
   `mpstat`, `ethtool -S`, route snapshot và metadata như hiện tại.
2. **Demo observability:** chạy một phiên riêng có nhãn rõ sau bài loaded RTT,
   collector lấy host metrics 10 giây/lần; dashboard hiện CPU, network bytes,
   OS drop counter và load. ENA/retransmission vẫn đối chiếu raw logs, không
   coi hostmetrics là nguồn cung cấp các bộ đếm ENA. Bài loaded RTT theo script
   cũng chạy khi agent tắt để nhất quán giữa hai mode. Không nhập phiên demo
   vào 16 block.
3. **AWS-native visibility:** có thể bật TGW Flow Logs/CloudWatch trong phiên
   chẩn đoán. Vì Peering không có cùng TGW metric, không dùng các metric riêng
   của TGW làm thước đo đối xứng để xếp hạng hai mode.
4. **Application tracing:** chỉ thêm khi dựng một ứng dụng client/server thật.
   Nếu mục tiêu vẫn là hiệu năng kết nối VPC, traces không tăng sức mạnh thống
   kê bằng việc hoàn tất block và loaded RTT.

## Ma trận kết luận để tránh bị bắt bẻ

| Câu kết luận | Bằng chứng tối thiểu | Trạng thái |
|---|---|---|
| Peering có RTT idle thấp hơn TGW trên 0,1 ms trong đa số block của cohort | 16 block, `K≥12`, cận exact `π_L>0,5`, không lỗi chất lượng | 3/16, chưa kết luận |
| TGW dễ mở rộng topology full mesh hơn Peering | công thức 6 Peering vs 4 attachment và tài liệu AWS | đủ bằng chứng kiến trúc |
| RTT TGW cao hơn đi kèm đường đi có thêm hop | TTL, route snapshot, số đo paired và tài liệu AWS | bằng chứng bước đầu; không phân lập được chi phí riêng của hop |
| TGW/Peering chịu tải tốt hơn | loaded RTT lặp theo block, goodput/loss/CPU/ENA | chưa đủ; bài tải hiện chỉ khám phá |
| Một dịch vụ luôn nhanh hơn trong mọi AWS workload | cần nhiều region, AZ, instance, traffic, thời gian và workload | ngoài phạm vi, không tuyên bố |

Một kết luận mạnh là kết luận có phạm vi, effect size và độ bất định rõ. Từ
“tuyệt đối” không làm kết luận mạnh hơn nếu thiết kế không bao phủ mọi AWS
region, instance type, thời điểm và workload.
