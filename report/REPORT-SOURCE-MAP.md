# Report Source Map

Traceability map cho báo cáo NT531. Nguồn được chọn theo loại claim, không dùng
một thứ tự duy nhất cho kiến trúc, phương pháp và số liệu.

- Kiến trúc: `infra/terraform/*.tf`, route snapshot và experiment metadata.
- Phương pháp: measurement scripts, run metadata và environment metadata.
- Số liệu: raw measurement data; sau đó là validated summary, comparison audit,
  `results/analysis/independent-review.json` và
  `results/analysis/report-metrics.json` để kiểm chứng/tổng hợp.
- Narrative: `docs/` và `README.md`.

`legacy/` không được dùng làm nguồn kết quả AWS thực nghiệm hiện tại.

## Front matter

### Tên đề tài và phạm vi

- `README.md`
- `docs/03-bon-vpc.md`
- `docs/19-trang-thai-ban-cong-bo.md`

### Thông tin lớp, giảng viên và sinh viên

- Thông tin do nhóm xác nhận trực tiếp: Nguyễn Ngọc Minh -- 24521068; Nguyễn
  Huy Nhật -- 24521253; Nguyễn Trung Kiên -- 24520885; giảng viên Đặng Lê Bảo
  Chương. Mã lớp chưa được cung cấp nên không suy đoán.

`misc/abstract.tex`, `misc/ack.tex` và `misc/council.tex` là front matter tùy
chọn. Các file được giữ nhưng không bật trong `main.tex` do chưa có yêu cầu môn
học đã xác minh.

## Chapter 1 - Tổng quan đề tài

### Bối cảnh, vấn đề, RQ và phạm vi

- `README.md`
- `docs/03-bon-vpc.md`
- `docs/04-do-va-giai-thich.md`
- `docs/15-khai-niem-va-ket-luan-so-sanh.md`
- `docs/16-ke-hoach-hoan-thien-den-26-10.md`
- `docs/19-trang-thai-ban-cong-bo.md`

## Chapter 2 - Nội dung thực hiện

### VPC, Peering, TGW và routing

- `infra/terraform/main.tf`
- `infra/terraform/peering.tf`
- `infra/terraform/transit-gateway.tf`
- `infra/terraform/routes.tf`
- `docs/15-khai-niem-va-ket-luan-so-sanh.md`
- AWS official documentation trong `references/references.bib`

### EC2 networking, ENA, TCP, fan-in và thống kê

- `infra/terraform/instances.tf`
- `docs/04-do-va-giai-thich.md`
- `docs/14-cong-thuc-va-ky-hieu.md`
- `docs/18-so-lieu-de-kiem-chung.md`
- `results/analysis/report-metrics.json`
- AWS EC2/ENA và ESnet iperf3 documentation trong bibliography

## Chapter 3 - Triển khai và kiểm thử

### Bốn VPC và EC2 endpoints

- `infra/terraform/main.tf`
- `infra/terraform/subnets.tf`
- `infra/terraform/expansion.tf`
- `infra/terraform/instances.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/README.md`

### Peering full mesh, TGW hub-and-spoke và route switching

- `infra/terraform/peering.tf`
- `infra/terraform/full-mesh.tf`
- `infra/terraform/transit-gateway.tf`
- `infra/terraform/routes.tf`
- `docs/images/results/00a-kien-truc-peering.png`
- `docs/images/results/00b-kien-truc-tgw.png`

### Management path và measurement path

- `infra/terraform/elastic-ips.tf`
- `infra/terraform/internet-gateways.tf`
- `docs/images/results/00c-quan-tri-eip.png`
- `docs/15-khai-niem-va-ket-luan-so-sanh.md`

### Benchmark configuration, workflow và threats to validity

- `scripts/measure-tcp-pairs.sh`
- `scripts/measure-tcp-fanin.sh`
- `scripts/prepare-measurement.sh`
- `scripts/setup-measurement-server.sh`
- `scripts/check-connectivity.sh`
- metadata trong `results/formal/`
- `docs/04-do-va-giai-thich.md`
- `docs/05-trang-thai-trien-khai.md`
- `docs/13-tong-hop-ket-qua.md`
- `docs/16-ke-hoach-hoan-thien-den-26-10.md`
- `docs/18-so-lieu-de-kiem-chung.md`
- `docs/19-trang-thai-ban-cong-bo.md`

### Verification pipeline: 434 checks, 307 source files

- `scripts/verify-results-for-review.py`
- `scripts/build-results-report.py`
- `scripts/report_context.py`
- `scripts/report_formulas.py`
- `results/analysis/independent-review.json`
- `results/analysis/report-metrics.json`
- `results/analysis/formula-verification.json`
- `results/analysis/render-verification.json`

### RTT: 0.2078 ms và 0.5630 ms

- `results/analysis/independent-review.json`
- `results/analysis/report-metrics.json`
- `results/pilot-peering/rtt-idle-a-b/`
- `results/formal/tgw/rtt-idle-a-b/`
- `docs/images/results/01-rtt.png`

Mode của RTT Peering được xác định từ metadata/filename và independent review,
không chỉ từ tên thư mục lịch sử.

### TCP single-flow và retransmission

- `results/analysis/independent-review.json`
- `results/analysis/report-metrics.json`
- `results/formal/peering/tcp-single-a-b/`
- `results/formal/tgw/tcp-single-a-b/`
- `docs/07-ket-qua-tcp-mot-cap.md`
- `docs/images/results/02-tcp-single.png`

### Fan-in, Jain index, CPU và ENA

- `results/analysis/independent-review.json`
- `results/analysis/report-metrics.json`
- `results/formal/fanin-comparison-audit.json`
- `results/formal/peering/tcp-fanin/`
- `results/formal/tgw/tcp-fanin/`
- `docs/10-ket-qua-fan-in-peering.md`
- `docs/12-ket-qua-fan-in-tgw-va-so-sanh.md`
- `docs/images/results/03-tcp-fanin.png`
- `docs/images/results/04-cpu-b.png`

## Chapter 4 - Các nghiên cứu liên quan

### Academic work, AWS documentation và iperf3

- Wang và Ng, *The Impact of Virtualization on Network Performance of Amazon
  EC2 Data Center*
- Li và cộng sự, *CloudCmp: Comparing Public Cloud Providers*
- AWS official VPC Peering, TGW, EC2 bandwidth và ENA documentation trong
  `references/references.bib`
- ESnet iperf3 documentation trong `references/references.bib`
- `docs/17-doi-chieu-bai-giang-va-cong-cu.md`

## Chapter 5 - Đánh giá và kết luận

### RQ, trade-off, limitations và future work

- Các finding chi tiết và đã kiểm chứng trong Chapter 3
- `docs/13-tong-hop-ket-qua.md`
- `docs/15-khai-niem-va-ket-luan-so-sanh.md`
- `docs/16-ke-hoach-hoan-thien-den-26-10.md`
- `docs/17-doi-chieu-bai-giang-va-cong-cu.md`
- `docs/18-so-lieu-de-kiem-chung.md`
- `docs/19-trang-thai-ban-cong-bo.md`
- `infra/terraform/*.tf`
- AWS official documentation trong bibliography

## Appendices

### Appendix A - Bảng phân công công việc

- Thành viên và MSSV do nhóm xác nhận trực tiếp. Phân công phản ánh các hạng
  mục có trong repository và cần được cả nhóm duyệt trước khi nộp.

### Appendix B - Câu hỏi phản biện và giải trình

- Không đưa vào bản PDF trước phản biện vì chưa có câu hỏi chính thức.

### Appendix C - Minh bạch trong việc sử dụng AI

- `appendix/appendix_c.tex` mô tả đúng phạm vi hỗ trợ AI và cách kiểm chứng.
- Được bật trong `main.tex` để công khai cách nhóm kiểm chứng nội dung.
