# Cách đo và tự giải thích đồ án

## Trước mỗi phiên đo

1. Kiểm tra trạng thái AWS và `routing_mode` đã apply, không chỉ nhìn file.
2. Bốn EC2 running, status checks đạt; truy cập Session Manager rồi `sudo -iu ec2-user`
   theo [hướng dẫn SSM](06-truy-cap-ssm.md). SSH qua EIP chỉ dùng khi đã xác minh kết nối.
3. Xác nhận công cụ cùng phiên bản, không còn bài tải cũ đang chạy.
4. Chọn MTU thống nhất; bài cơ sở dùng 1500 trên cả bốn máy. Ví dụ chạy
   `sudo ip link set dev ens5 mtu 1500` trên từng máy rồi `ip link show ens5`.
   Đây là thay đổi runtime, cần kiểm tra lại sau reboot.
5. Xác nhận đồng hồ đồng bộ (`timedatectl`), lưu thời gian UTC, loại máy,
   kernel, phiên bản công cụ, MTU và mode cùng kết quả.
6. Chạy kiểm tra connectivity, tách log này khỏi số liệu benchmark.

## Các kịch bản và ưu tiên hiện tại

Cập nhật 06/10/2026: phần đo chính để hoàn thiện bản báo cáo hiện tại
gồm RTT khi rảnh, TCP một cặp và TCP fan-in, mỗi bài trên Peering/TGW,
5 lượt mỗi phương án. Đã kiểm tra đủ 6/6 bộ và sao lưu đủ file gốc
hai phiên fan-in. Kết quả đối chiếu tại
[bài fan-in TGW và so sánh](12-ket-qua-fan-in-tgw-va-so-sanh.md).
Hai cặp Peering đã chạy được giữ làm quan sát bổ sung; không ưu tiên
đo hai cặp TGW. RTT khi có tải và các đợt lặp xen kẽ là phần mở rộng,
chưa được tính là đã hoàn thành hoặc bắt buộc trong phạm vi tối thiểu này.
Phạm vi này là lựa chọn triển khai hiện tại, không thay thế yêu cầu của
giảng viên. Khi trình bày phải nêu hạn chế về thời điểm đo và burst credits.

| Bài | Nguồn → đích | Cổng listener | Mục đích |
|---|---|---|---|
| Một cặp | A → B | B:5201 | Hiệu năng cơ sở |
| Hai cặp | A → B và C → D | B:5201, D:5201 | Hai cặp hoạt động đồng thời |
| Nhiều nguồn | A → B, C → B, D → B | B:5201, B:5202, B:5203 | Receiver dùng chung |

Ba cổng ở bài cuối là ba tiến trình iperf3 server độc lập. Không gửi cả
ba client vào một tiến trình server rồi nhầm `server is busy` với lỗi mạng.

Listener systemd `nt531-iperf@5201`, `@5202`, `@5203` khởi động cùng EC2,
chỉ bind private IP; không tự phát sinh tải. Kiểm tra bằng:

```bash
systemctl status nt531-iperf@5201 --no-pager
ss -ltn
```

Ví dụ trên A khi đã xác nhận đang chạy Peering, một lượt 30 giây đo +
5 giây bỏ qua; TCP một luồng, log JSON tên duy nhất:

```bash
mkdir -p ~/nt531-results
run_file=$(mktemp ~/nt531-results/peering-a-b-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.json)
iperf3 -c 10.20.10.155 -p 5201 -P 1 -O 5 -t 30 -i 1 -J --get-server-output > "$run_file"
jq '{error, sent: .end.sum_sent, received: .end.sum_received}' "$run_file"
```

Đổi tên mode cho đúng lần đo. C→D dùng đích 10.40.10.155. C→B dùng
10.20.10.155:5202; D→B dùng 10.20.10.155:5203. Các bài đồng thời cần
được bắt đầu gần cùng thời điểm, ghi thời gian bắt đầu/kết thúc và phân
tích khoảng chồng nhau; thao tác bấm tay không bảo đảm đồng bộ tuyệt đối.

Giữ nguyên số luồng, thời gian, chiều truyền và MTU giữa hai phương án.
Đề xuất tối thiểu 5 lượt cho mỗi kịch bản/phương án; luân phiên thứ tự
Peering/TGW giữa các đợt để giảm sai lệch do thời gian và burst credits.
Không coi mỗi dòng 1 giây của cùng một lần chạy là một thí nghiệm độc lập.

## Số liệu cần lưu

- Throughput receiver của từng luồng và tổng trên cùng khoảng thời gian.
- RTT khi rảnh và khi có tải; nêu số mẫu nếu tính median/p95.
- TCP retransmission phía gửi, không đồng nhất với tỷ lệ packet loss.
- CPU từng máy, đặc biệt máy B trong bài nhiều nguồn: `mpstat 1`.
- ENA counters trước/sau (`ethtool -S ens5`), xem chênh lệch bộ đếm
  `bw_in_allowance_exceeded`, `bw_out_allowance_exceeded`, `pps_allowance_exceeded`.
- Mọi lượt lỗi vẫn được lưu và giải thích; không chỉ chọn lần cao nhất.

`c6i.large` có baseline 0.781 Gbps, burst tới 12.5 Gbps; burst không phải
cam kết tốc độ duy trì. Luồng đơn ngoài cluster placement group có giới
hạn 5 Gbps. Vì vậy không kết luận Peering tối đa 4.96 Gbps từ log đo thử.
[Thông số EC2](https://docs.aws.amazon.com/ec2/latest/instancetypes/co.html)
· [Cơ chế bandwidth/credits](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-network-bandwidth.html)
· [ENA counters](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html).

TGW hỗ trợ MTU tới 8500 cho đường VPC. Không so Peering 9001 với TGW
ở cấu hình khác rồi quy mọi chênh lệch cho công nghệ.
[TGW quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html).

## Sáu câu bạn nên tự trả lời được

1. **Gói A→C đi thế nào?** Tra route 10.30.0.0/16 của A: Peering AC
   hoặc TGW; phía C phải có route về 10.10.0.0/16. SG cũng phải cho phép.
2. **Sao 6 Peering nhưng 4 attachment?** Peering nối hai VPC, attachment
   nối một VPC vào TGW. Số kết nối hạ tầng không phải số luồng TCP.
3. **Sao dùng private IP?** Để bài đo đi qua đường liên VPC đã chọn;
   EIP dùng SSH và quản trị.
4. **Sao không chỉ lấy tốc độ cao nhất?** Cần độ ổn định và tính lặp lại,
   đồng thời kiểm soát sai lệch do CPU, burst và thứ tự chạy.
5. **Ba nguồn chậm đi có phải TGW nghẽn?** Chưa chắc; B có thể chạm giới
   hạn nhận/CPU. Cần số liệu CPU, ENA và đối chiếu Peering cùng điều kiện.
6. **Terraform No changes chứng minh gì?** Code khớp các resource đang
   quản lý, không thay cho kiểm tra route hoặc chạy thử ứng dụng.
