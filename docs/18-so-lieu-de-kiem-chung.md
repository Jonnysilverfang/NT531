# Số liệu để kiểm chứng đồ án NT531

Tính lại từ file gốc ngày 06/10/2026. Bộ chuẩn: 5 lượt mỗi mode mỗi bài; không có phép đo mới. Số hiện theo dấu chấm thập phân. JSON đi kèm giữ độ chính xác đầy đủ và SHA256 từng nguồn.

## Nhận xét về bản phản biện gửi kèm

Nhận xét hợp lý: giữ đề tài, siết điều kiện áp dụng. Cần làm rõ đơn vị GB/GiB, giả định warm-up, ranh giới đếm route, và tổng fan-in theo cửa sổ chung. Khoảng tin cậy ghép theo đợt chưa thể tính từ việc ghép tùy ý lượt 1–5 của hai phiên cũ. Bản phản biện chỉ xem kế hoạch; lần kiểm chứng này đối chiếu thêm ping, TCP JSON, mpstat và ENA đã lưu.

## Bảng tổng hợp

| Chỉ số | Peering | TGW |
| --- | --- | --- |
| RTT trung bình các lượt (ms) | 0.207800 | 0.563000 |
| SD mẫu giữa 5 RTT trung bình (ms) | 0.007855 | 0.077508 |
| TCP một luồng: goodput nhận (Gbps) | 4.782804 | 4.608265 |
| SD mẫu goodput một luồng (Gbps) | 0.000510 | 0.001640 |
| Fan-in: tổng xấp xỉ (Gbps) | 11.611009 | 11.590520 |
| SD mẫu tổng xấp xỉ fan-in (Gbps) | 0.015338 | 0.023209 |
| CPU A bài một luồng (%) | 20.9507 | 17.8091 |
| CPU B bài một luồng (%) | 18.6647 | 20.5068 |
| CPU B bài fan-in (%) | 59.1802 | 56.8751 |
| Trung bình Jain 5 lượt fan-in | 0.999133 | 0.984494 |

CPU busy = 100 − %idle, lấy dòng CPU all của mpstat trong cửa sổ nêu ở JSON. Số tổng hợp là trung bình năm giá trị từng lượt, không phải tổng hai lõi; fan-in B có một cửa sổ Peering 29 mẫu, các cửa sổ còn lại 30 mẫu.

## RTT khi mạng rảnh

ICMP A→B→A; MTU 1500; mỗi lượt 100 gói, payload 56 byte, interval 0.2 giây. RTT avg/min/max/mdev dưới đây lấy từ dòng thống kê ping (đã được ping làm tròn).

### peering

| Lượt | Gửi/nhận | Loss (%) | Min (ms) | Avg (ms) | Max (ms) | mdev (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 100/100 | 0.0 | 0.187 | 0.212 | 0.25 | 0.01 |
| 2 | 100/100 | 0.0 | 0.177 | 0.195 | 0.238 | 0.009 |
| 3 | 100/100 | 0.0 | 0.198 | 0.215 | 0.256 | 0.01 |
| 4 | 100/100 | 0.0 | 0.186 | 0.211 | 0.256 | 0.01 |
| 5 | 100/100 | 0.0 | 0.181 | 0.206 | 0.227 | 0.008 |

Nguồn: `results/pilot-peering/rtt-idle-a-b/nt531-results/peering-rtt-idle-a-b-20261005T115510Z-6qX9Gm/summary.csv` và run-1.txt đến run-5.txt cạnh file đó.

### tgw

| Lượt | Gửi/nhận | Loss (%) | Min (ms) | Avg (ms) | Max (ms) | mdev (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 100/100 | 0.0 | 0.576 | 0.666 | 5.897 | 0.525 |
| 2 | 100/100 | 0.0 | 0.483 | 0.521 | 1.271 | 0.076 |
| 3 | 100/100 | 0.0 | 0.453 | 0.501 | 1.961 | 0.147 |
| 4 | 100/100 | 0.0 | 0.583 | 0.626 | 0.903 | 0.04 |
| 5 | 100/100 | 0.0 | 0.467 | 0.501 | 1.006 | 0.064 |

Nguồn: `results/formal/tgw/rtt-idle-a-b/nt531-results/tgw-rtt-idle-a-b-20261005T120751Z-mx0lij/summary.csv` và run-1.txt đến run-5.txt cạnh file đó.

Cả hai phiên 500/500 phản hồi, loss quan sát 0%. mdev là độ lệch chuẩn RTT bên trong một lượt; SD mẫu trong bảng tổng hợp là SD của năm RTT avg, hai đại lượng khác nhau.

## TCP một luồng A→B

TCP P1, omit 5 giây, đo 30 giây, MTU 1500, iperf3 3.19.1, TCP cubic. Goodput dùng phía nhận.

### peering

| Lượt | Payload nhận (byte) | Thời gian nhận (s) | Goodput (Gbps) | Retransmits | CPU A (%) | CPU B (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 17932877824 | 30.00049 | 4.782022647 | 48253 | 19.5490 | 17.6557 |
| 2 | 17937072128 | 30.00049 | 4.783141109 | 57185 | 22.5777 | 21.5133 |
| 3 | 17936941056 | 30.00048 | 4.783107752 | 49851 | 19.8120 | 17.7440 |
| 4 | 17937989632 | 30.001638 | 4.783202739 | 55189 | 19.0663 | 17.9837 |
| 5 | 17934843904 | 30.000498 | 4.782545651 | 49724 | 23.7483 | 18.4270 |

### tgw

| Lượt | Payload nhận (byte) | Thời gian nhận (s) | Goodput (Gbps) | Retransmits | CPU A (%) | CPU B (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 17286299648 | 30.001017 | 4.609523643 | 280 | 16.2093 | 18.2293 |
| 2 | 17285513216 | 30.000702 | 4.609362332 | 193 | 17.7763 | 22.8813 |
| 3 | 17286037504 | 30.000914 | 4.609469566 | 0 | 15.4370 | 21.5923 |
| 4 | 17273585664 | 30.00071 | 4.606180497 | 671 | 20.5223 | 18.0797 |
| 5 | 17275944960 | 30.000843 | 4.606789205 | 411 | 19.1007 | 21.7513 |

Các delta ENA đã theo dõi đều bằng 0 ở bài một luồng: A lấy trước/sau từng lượt, B lấy trước/sau cả phiên ghi. Không suy ra toàn đường mạng không có mất gói. Retransmits là số segment truyền lại do TCP báo, không phải phần trăm mất gói.

## Fan-in A/C/D cùng gửi tới B

Mỗi nguồn một luồng; cổng 5201/5202/5203; 5 lượt, lịch bắt đầu cách 45 giây. Mỗi nguồn dùng cửa sổ nhận riêng. Tổng dưới đây cộng ba goodput trung bình, chưa phải goodput chung cửa sổ chính xác.

### peering

| Lượt | A nhận (Gbps) | C nhận (Gbps) | D nhận (Gbps) | Tổng xấp xỉ (Gbps) | Jain | CPU B (%) | Mẫu CPU B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.013128394 | 3.608911045 | 3.980132508 | 11.602171948 | 0.997759397 | 59.4503 | 30 |
| 2 | 3.938178336 | 3.888724225 | 3.774961064 | 11.601863625 | 0.999687864 | 58.7417 | 30 |
| 3 | 3.950159489 | 3.824059668 | 3.863921498 | 11.638140655 | 0.999815997 | 60.2253 | 30 |
| 4 | 3.997646869 | 3.664123477 | 3.945451897 | 11.607222242 | 0.998568731 | 57.8530 | 30 |
| 5 | 3.892527300 | 3.913698520 | 3.799419646 | 11.605645466 | 0.999835377 | 59.6307 | 29 |

| Nguồn | Goodput nhận TB (Gbps) | Retransmits 5 lượt | CPU nguồn TB (%) |
| --- | --- | --- | --- |
| A | 3.958328078 | 24993, 26323, 25420, 25668, 25768 | 15.0710 |
| C | 3.779903387 | 22949, 25027, 22739, 24385, 25682 | 15.6178 |
| D | 3.872777323 | 28089, 25302, 25795, 30529, 26983 | 11.4764 |

### tgw

| Lượt | A nhận (Gbps) | C nhận (Gbps) | D nhận (Gbps) | Tổng xấp xỉ (Gbps) | Jain | CPU B (%) | Mẫu CPU B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.987996849 | 3.457244129 | 4.144947424 | 11.590188403 | 0.994232420 | 57.4843 | 30 |
| 2 | 3.519559397 | 3.875595003 | 4.155517492 | 11.550671893 | 0.995451976 | 57.7543 | 30 |
| 3 | 3.113589346 | 4.605977490 | 3.882726488 | 11.602293324 | 0.975775550 | 59.5387 | 30 |
| 4 | 3.753373051 | 4.232073733 | 3.622777241 | 11.608224025 | 0.995438727 | 49.7720 | 30 |
| 5 | 4.608679287 | 2.800579652 | 4.191963236 | 11.601222176 | 0.961570814 | 59.8263 | 30 |

| Nguồn | Goodput nhận TB (Gbps) | Retransmits 5 lượt | CPU nguồn TB (%) |
| --- | --- | --- | --- |
| A | 3.796639586 | 66458, 75103, 23690, 24217, 1017 | 14.8387 |
| C | 3.794294002 | 57152, 84048, 1602, 31508, 18164 | 17.0836 |
| D | 3.999586376 | 63560, 50315, 30093, 21649, 29722 | 14.2277 |

Jain từng lượt J=(Σgᵢ)²/(3Σgᵢ²), với gᵢ là goodput nhận từng nguồn trong cửa sổ riêng; số tổng hợp là trung bình năm J, không phải J của ba goodput trung bình cả phiên. J gần 1 mô tả mức đều nhau trong bộ đo, chưa chứng minh max-min fairness hay năng lực tối đa dịch vụ.

### ENA máy B: trước, sau và delta cả phiên


**peering**

| Counter | Trước | Sau | Delta |
| --- | --- | --- | --- |
| bw_in_allowance_exceeded | 0 | 1434501 | 1434501 |
| bw_out_allowance_exceeded | 0 | 0 | 0 |
| pps_allowance_exceeded | 0 | 160457411 | 160457411 |
| conntrack_allowance_exceeded | 0 | 0 | 0 |
| linklocal_allowance_exceeded | 0 | 0 | 0 |

**tgw**

| Counter | Trước | Sau | Delta |
| --- | --- | --- | --- |
| bw_in_allowance_exceeded | 1434501 | 8042711 | 6608210 |
| bw_out_allowance_exceeded | 0 | 0 | 0 |
| pps_allowance_exceeded | 160457411 | 237551867 | 77094456 |
| conntrack_allowance_exceeded | 0 | 0 | 0 |
| linklocal_allowance_exceeded | 0 | 0 | 0 |

Các delta ENA B trên bao gồm toàn phiên ghi, cả thời gian chờ/nghỉ; không phải riêng 30 giây của một lượt. Không cộng bw_in và PPS thành số gói mất: các counter có thể cùng phản ánh một gói vượt allowance. [Định nghĩa counter AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html).

## Công thức để tự tính lại

- Trung bình: x̄ = Σxᵣ/5. SD mẫu giữa lượt: s = √[Σ(xᵣ−x̄)²/4]. CV = 100s/x̄ (%).
- Goodput nhận: G = 8 × receiver_bytes / receiver_seconds / 10⁹ (Gbps).
- CPU busy mỗi mẫu = 100 − %idle; mỗi lượt lấy trung bình các mẫu thuộc cửa sổ; bảng tổng hợp lấy trung bình 5 lượt.
- ENA delta = counter_sau − counter_trước, cùng NIC và không reset giữa hai lần đọc.
- Tổng xấp xỉ fan-in mỗi lượt = G_A + G_C + G_D; chỉ số chung cửa sổ cần byte nhận trong cùng W.

Ví dụ Peering một luồng lượt 1: 8 × 17,932,877,824 / 30.00049 / 10⁹ = 4.7820226467 Gbps.

### Chênh lệch quan sát

- RTT TGW − Peering = 0.3552 ms; tỷ số TGW/Peering = 2.7093.
- TCP một luồng: (Peering/TGW − 1) × 100 = 3.787519%; mẫu số là TGW.
- Fan-in: (1 − TGW/Peering) × 100 = 0.176460%; mẫu số là Peering, dùng tổng xấp xỉ.

Đây là thống kê mô tả các phiên nối tiếp. Lượt cùng số ở hai mode không phải cặp đo đồng thời. Chưa có CI theo đợt, kiểm định tương đương, RTT khi tải hay bảng giá us-east-1 đã chốt.

## Ví dụ dự toán, không phải số đo hay hóa đơn

Giả định tốc độ 4.6 Gbps giữ đều trong 35 giây: 20,125,000,000 byte = 20.125 GB thập phân = 18.742867 GiB. Nếu chỉ xét 30 giây cùng tốc độ: 17,250,000,000 byte = 17.25 GB = 16.065314 GiB. Warm-up thực tế, ACK, retransmission và overhead cần được tính riêng để ước lượng lưu lượng tính phí. Giá trị 4.6 Gbps đo trong 30 giây không tự chứng minh tốc độ 5 giây warm-up.

C_TGW = Σhⱼr_h + V_in r_g: phí attachment theo giờ bị tính và phí dung lượng gửi vào TGW. Đơn giá theo region còn cần xác minh. [Quy tắc AWS](https://aws.amazon.com/transit-gateway/pricing/) ghi giờ attachment lẻ tính tròn giờ và 1 GB bằng 1024 MB. Không nhân đôi payload unicast chỉ vì có attachment nguồn và đích.

N=4: 6 Peering full mesh hoặc 1 TGW + 4 attachment; 12 route liên VPC ở bốn bảng subnet nếu mỗi bảng có ba CIDR đích. Không phải tổng số route toàn hệ thống. Đây là đếm kiến trúc, không phải kết quả tốc độ.

## Nguồn và cách chạy lại

Chạy `scripts/verify-results-for-review.py` bằng Python có sẵn. Script tính lại từ raw bằng thư viện chuẩn, đối chiếu với báo cáo và xuất riêng tài liệu này cùng `results/analysis/independent-review.json`.

Đã đối chiếu 434 phép tính/giá trị từ 307 file nguồn. JSON liệt kê đầy đủ đường dẫn, SHA256, byte/thời lượng nhận, cửa sổ CPU và kiểm tra từng giá trị. Các số không làm tròn trong JSON phù hợp để gửi người khác kiểm chứng.

Nguồn chuẩn:
- RTT peering: `results/pilot-peering/rtt-idle-a-b/nt531-results/peering-rtt-idle-a-b-20261005T115510Z-6qX9Gm/summary.csv`.
- TCP một luồng peering: `results/formal/peering/tcp-single-a-b/A/peering-tcp-single-a-b-20261006T091620Z-uupMz9`.
- Fan-in peering A: `results/formal/peering/tcp-fanin/A/peering-tcp-fanin-a-1791293390-RyXrAo`.
- Fan-in peering C: `results/formal/peering/tcp-fanin/C/peering-tcp-fanin-c-1791293390-P5LLrh`.
- Fan-in peering D: `results/formal/peering/tcp-fanin/D/peering-tcp-fanin-d-1791293390-DcwPRL`.
- RTT tgw: `results/formal/tgw/rtt-idle-a-b/nt531-results/tgw-rtt-idle-a-b-20261005T120751Z-mx0lij/summary.csv`.
- TCP một luồng tgw: `results/formal/tgw/tcp-single-a-b/A/tgw-tcp-single-a-b-20261005T123159Z-rqzOZj`.
- Fan-in tgw A: `results/formal/tgw/tcp-fanin/A/tgw-tcp-fanin-a-1791296141-V2CCdZ`.
- Fan-in tgw C: `results/formal/tgw/tcp-fanin/C/tgw-tcp-fanin-c-1791296141-jimn5d`.
- Fan-in tgw D: `results/formal/tgw/tcp-fanin/D/tgw-tcp-fanin-d-1791296141-NefCr0`.
