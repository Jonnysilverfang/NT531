# GIAO THỨC THỰC NGHIỆM MODE B TRÊN AWS

> Trạng thái: **preregistered protocol — chưa có dữ liệu đo AWS trong repo**. Tài liệu này định nghĩa điều phải làm và điều kiện được phép kết luận; nó không biến dữ liệu Mode A thành bằng chứng empirical.

## 1. Phạm vi và Research Questions

Tên đề tài: **Đánh giá thực nghiệm ảnh hưởng của kiến trúc mạng và cơ chế xử lý gói tin Linux đến hiệu năng mạng trên AWS**.

English: **Experimental Evaluation of AWS Network Architecture and Linux Packet Processing Performance**.

| RQ | Biến độc lập | Primary endpoint | Chỉ số bổ sung | Testcase |
|---|---|---|---|---|
| RQ1: Peering và TGW ảnh hưởng thế nào đến tail latency? | Path = Peering/TGW | Paired delta P99 RTT theo independent run | P50, P95, jitter, loss, CPU, NET_RX | TC-01 |
| RQ2: MTU 1500/9001 ảnh hưởng thế nào khi số TCP stream tăng? | MTU × streams = `{1500,9001}` × `{1,4,8}` | Throughput và SoftIRQ theo từng mức stream | PPS, CPU, retransmit, ENA counters | TC-02 |
| RQ3: PrivateLink đổi bao nhiêu hiệu năng để lấy service isolation? | Direct/PrivateLink tới **cùng backend** | Paired delta P99 RTT | Throughput, CPU, chi phí | TC-03P |
| RQ4: XDP duy trì legitimate service tốt hơn iptables tới ngưỡng tải nào? | Filter × offered-load stage | Saturation point theo legitimate-flow SLO | achieved TX/RX PPS, filter drop, CPU, SoftIRQ, P50/P95/P99 | TC-04 |

Overlapping CIDR là **TC-03F functional architecture validation** riêng. Nó chứng minh khả năng kết nối/cô lập, không được gộp vào ước lượng hiệu năng TC-03P.

## 2. Giả thuyết và quy tắc quyết định đăng ký trước

- H1: TGW có paired P99 RTT cao hơn Peering trong cùng block/run.
- H2: MTU 9001 giảm packet-processing overhead; hiệu ứng phải báo cáo riêng cho P1, P4 và P8, không gộp các mức stream.
- H3: PrivateLink có overhead P99/throughput so với direct path tới cùng EC2 backend; khuyến nghị phải cân cùng isolation và chi phí.
- H4: XDP có saturation point cao hơn iptables khi bảo vệ cùng UDP port trên cùng DUT.

Saturation của TC-04 là **mức offered load nhỏ nhất** mà ít nhất một điều kiện dưới đây vi phạm trong toàn cửa sổ đo:

- loss của **legitimate probe** lớn hơn `1%`; hoặc
- P99 của legitimate probe lớn hơn `5 ms`; hoặc
- CPU tổng lớn hơn `90%` sustained.

`filter_drop_pps` của attack traffic không phải packet loss và không được thay cho legitimate-flow loss. Nếu một stage không đạt offered load, phải báo achieved load; không được gắn nhãn stage bằng target PPS rồi coi đó là PPS thực tế.

## 3. Experimental unit, replication và randomization

- Đơn vị độc lập là **run**, không phải packet/interval.
- `validation` và `pilot`: N=3 để bắt lỗi công cụ/dữ liệu; không dùng làm kết luận cuối.
- `final`: N≥10; ưu tiên 20–30 nếu ngân sách cho phép.
- Mỗi run là một block. Condition order dùng seed lưu trong run manifest.
- TC-01 hiện có hai target host. Host identity/assignment phải được lưu và xử lý như blocking factor; không tuyên bố “route là biến duy nhất” nếu chưa hoán đổi host-path hoặc dùng cùng target.
- TC-02 randomize toàn bộ 6 cell MTU × streams. TC-04 giữ load stages tăng dần nhưng randomize iptables/XDP trong từng stage.

Schedule có thể review offline bằng:

```bash
bash scripts/benchmark_runner.sh --plan-only --profile final --experiment-id review-final
```

File plan ghi `aws_verified=false`, `empirical=false` và không gọi AWS.

## 4. Lifecycle mỗi phép đo

```text
Prepare → Warmup 10s → Snapshot Before → Measurement 30s → Snapshot After → Cooldown 15s
```

Thời lượng lấy từ [`experiment.yaml`](../experiment.yaml). Mode B từ chối measurement dưới 30 giây. Không đổi instance type, AMI, kernel, offload, congestion control hoặc experiment config giữa các run, trừ khi đó là biến độc lập đã đăng ký.

## 5. Metadata và raw evidence bắt buộc

Mỗi run nằm dưới `results/mode_b/<experiment_id>/run_NNN/` và phải có:

- `experiment.yaml`, `manifest.json`, `environment.json`;
- Region/AZ, instance ID/type, AMI, kernel, ENA driver/version, CPU/RAM;
- interface/MTU, congestion control, IRQ affinity, GRO/GSO/TSO;
- tool versions, Git commit, seed, order, block ID và host/path identity;
- raw command output, SSM invocation stdout/stderr, before/after SoftIRQ, ENA, iptables và XDP-map evidence;
- `checksums.sha256` tạo **sau cùng**.

`manage_run_artifacts.py finalize` niêm phong run; `verify` từ chối digest sai, entry trùng, đường dẫn tuyệt đối/`..`, symlink và raw artifact không được khai báo.

## 6. Preflight và fail-closed policy

Offline scope chỉ kiểm config/source/Terraform format và phải ghi `aws_verified=false`. AWS scope phải được gọi rõ:

```bash
bash scripts/preflight_check.sh --scope aws \
  --profile pilot --dut-instance-id i-0123456789abcdef0
```

Runner không chạy ngầm: bắt buộc chọn `--plan-only` hoặc `--execute`. Khi chạy AWS, target IP và instance ID phải lấy từ `terraform output`; repo không cung cấp endpoint IP giả. Bất kỳ preflight check bắt buộc nào fail thì **không benchmark**.

## 7. Phân tích và điều kiện được phép kết luận

Mode A tiếp tục dùng `scripts/analyze_results.py` và bộ checksum hiện hữu. Mode B là schema run-tree riêng; không được đưa run live vào parser Mode A.

Mỗi endpoint Mode B phải báo:

- N independent runs và missing/excluded runs;
- observed paired run-level estimate;
- 95% run-aware bootstrap CI và effect size;
- P50/P95/P99 mô tả; pooled-observation tests chỉ được ghi exploratory;
- practical impact, cost snapshot date và giới hạn hiệu lực.

Repo chỉ chuyển trạng thái từ methodology prototype sang empirical study sau khi: AWS preflight PASS, N final đạt cấu hình, mọi run checksum PASS, không thiếu design cell, analyzer Mode B tái lập summary/graphs và evidence review xác nhận không có environment drift ngoài biến đã đăng ký.

## 8. Threats to validity đăng ký trước

- Một Region và một họ kernel/AMI;
- số instance type hạn chế;
- shared-cloud/noisy-neighbor và host placement;
- không có DPDK, multi-Region hoặc nhiều congestion-control algorithms;
- offered load có thể khác achieved load;
- N=10–30 giới hạn khả năng khái quát.

Những giới hạn này phải xuất hiện trong báo cáo cuối, kể cả khi kết quả thuận lợi.
