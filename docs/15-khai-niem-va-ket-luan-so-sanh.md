# Khái niệm và kết luận so sánh Peering với TGW

Cập nhật 06/10/2026. Khái niệm dành cho người mới; kết luận dựa trên sáu bộ thực nghiệm đã kiểm tra, không phải giới hạn tuyệt đối của dịch vụ.

## Kết luận dùng trong báo cáo

Trong cấu hình bốn EC2 c6i.large cùng AZ và MTU 1500 đã thử nghiệm, Peering có lợi thế về RTT khi rảnh và thông lượng TCP một luồng quan sát được. TGW có lợi thế kiến trúc khi cần kết nối nhiều VPC và tổ chức định tuyến tập trung. Với ít VPC, ưu tiên độ trễ và chi phí kết nối, Peering là lựa chọn phù hợp; khi quy mô và quản trị mạng là yêu cầu chính, TGW đáng cân nhắc. Bài fan-in ghi nhận giới hạn máy nhận ở cả hai mode, nên chưa xác định năng lực tối đa của dịch vụ.

## Khái niệm mạng

### VPC và subnet

VPC là mạng riêng logic trên AWS; subnet là một phần dải địa chỉ của VPC trong một AZ. Đồ án dùng bốn VPC có CIDR khác nhau, mỗi VPC có một EC2 làm điểm gửi hoặc nhận.

### CIDR và private IP

CIDR viết dải địa chỉ theo dạng 10.10.0.0/16. Private IP là địa chỉ của EC2 bên trong mạng, ví dụ A là 10.10.10.212. Bài đo dùng private IP để đi qua kết nối liên VPC.

### Route table và security group

Route table chọn nơi chuyển gói theo địa chỉ đích; security group cho phép hoặc chặn lưu lượng tới EC2. Có kết nối Peering/TGW chưa đủ: cần route hai chiều và quyền truy cập phù hợp.

### Peering và tính không bắc cầu

Peering nối trực tiếp một cặp VPC. Có AB và BC không tự tạo đường A tới C qua B. Muốn mọi cặp trong bốn VPC liên lạc trực tiếp, mô hình toàn lưới cần sáu kết nối.

### TGW và attachment

TGW là router vùng do AWS quản lý; attachment nối một VPC vào TGW. Bốn VPC dùng bốn attachment. TGW chuyển tiếp giữa các attachment theo route; các VPC không tự liên lạc chỉ vì đã gắn vào TGW.

### Association và propagation

Association chọn bảng TGW dùng để tra đường cho lưu lượng đi vào từ attachment. Propagation đưa dải địa chỉ của attachment vào bảng TGW. Chúng khác với route trong bảng subnet của từng VPC.

### EIP và AZ

Elastic IP là IP công cộng cố định để quản trị SSH trong đồ án. AZ là vùng sẵn sàng thuộc một region; bốn EC2 được đo cùng us-east-1a. EIP không nằm trên đường benchmark private IP.

## Khái niệm đo

### RTT

Round trip time là thời gian từ khi A gửi gói tới khi A nhận phản hồi từ B. Ping đo RTT, không đo riêng độ trễ một chiều. Không lấy RTT chia hai rồi coi là số đo một chiều đã xác minh.

### Goodput và Gbps

Thông lượng phía nhận của iperf3 là tốc độ dữ liệu ứng dụng nhận được. Gbps là tỷ bit mỗi giây; 1 byte bằng 8 bit. Số này không phải tốc độ đường truyền vật lý hoặc tốc độ tải file bằng GB/s.

### Một luồng và fan-in

Một luồng là một kết nối TCP tải từ A tới B. Fan-in là nhiều nguồn cùng gửi tới một receiver: A, C, D tới B. Ba nguồn có thể tranh tài nguyên nhận của B dù dùng ba kết nối Peering khác nhau.

### MTU và PPS

MTU là kích thước gói IP lớn nhất giao diện gửi mà không cần phân mảnh ở đó; bài cơ sở dùng 1500 byte. PPS là số gói mỗi giây. Cùng thông lượng bit, gói nhỏ hơn có thể tạo nhiều gói hơn và tăng chi phí xử lý.

### Retransmission và mất phản hồi

TCP có thể truyền lại dữ liệu khi không nhận ACK theo cơ chế của nó. Retransmits của iperf3 là số lần truyền lại, không phải phần trăm mất gói. Ping mất phản hồi cũng không định vị được gói bị mất ở chiều nào.

### CPU và ENA

CPU busy tổng hợp là 100 trừ phần trăm idle, gồm mọi hoạt động trên máy. ENA là adapter mạng của EC2; delta allowance counter phản ánh số đếm tăng do vượt giới hạn instance. Không dùng counter tích lũy như throughput hoặc cộng chúng thành số gói mất.

### Lượt và đợt đo

Năm lượt liên tiếp của một phiên mô tả biến động trong phiên đó. Đợt bổ sung ở thời điểm khác, có cả hai mode và kiểm soát thứ tự, giúp đánh giá khả năng tái lập. Dòng log mỗi giây không phải các thí nghiệm độc lập.

## Bảng so sánh

| Tiêu chí | Peering | TGW |
|---|---|---|
| RTT khi rảnh<br>Số đo hiện có | 0,2078 ms<br>Thấp hơn trong phiên | 0,5630 ms |
| TCP một luồng<br>Số đo hiện có | 4,7828 Gbps<br>Cao hơn khoảng 3,79% | 4,6083 Gbps |
| Ba nguồn tới B<br>Tổng xấp xỉ | 11,6110 Gbps | 11,5905 Gbps<br>Chưa chứng minh tương đương |
| Bốn VPC toàn lưới<br>Đặc điểm kiến trúc | 6 kết nối Peering | 1 TGW và 4 attachment |
| Mở rộng thêm VPC<br>Nếu giữ toàn lưới | Thêm một kết nối tới mỗi VPC cũ | Thêm một attachment<br>Vẫn cần cập nhật route |
| Quản lý định tuyến<br>Khả năng dịch vụ | Theo các cặp VPC | Tập trung; có nhiều bảng để phân đoạn |
| Chi phí kết nối<br>Theo tài liệu AWS | Không phí tạo Peering;<br>truyền cùng AZ miễn phí | Phí attachment theo giờ<br>và xử lý dữ liệu theo GB |

Khả năng định tuyến tập trung và phân đoạn là đặc điểm dịch vụ, chưa được đo thành lợi ích vận hành trong đồ án. Toàn lưới với N VPC cần N(N−1)/2 Peering hoặc N attachment TGW; trong cấu hình route theo từng CIDR hiện tại, tổng route liên VPC ở bảng subnet vẫn là N(N−1) cho cả hai phương án.

### Những điểm không nên đánh đồng

- Số kết nối hạ tầng khác số luồng TCP; cả Peering và TGW đều cho phép nhiều cặp gửi đồng thời.
- TGW không phải một EC2 router trung tâm do nhóm tự dựng; sơ đồ hub không chứng minh một điểm nghẽn vật lý duy nhất.
- TGW hỗ trợ nhiều bảng route nhưng không tự làm mạng an toàn hơn nếu cấu hình vẫn cho mọi attachment liên lạc.
- Fan-in đã đo là tổng xấp xỉ từ cửa sổ riêng. Chưa chứng minh tương đương thống kê hoặc giới hạn tối đa.
- RTT một phiên, chi phí dịch vụ và mức dễ quản trị là ba tiêu chí khác nhau; không cộng thành một điểm thắng tổng thể tùy ý.

## Nguồn đối chiếu

- [AWS VPC Peering và chi phí cùng AZ](https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html).
- [AWS VPC connectivity options và tính không bắc cầu](https://docs.aws.amazon.com/whitepapers/latest/aws-vpc-connectivity-options/amazon-vpc-to-amazon-vpc-connectivity-options.html).
- [TGW route tables association propagation](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html).
- [TGW phí attachment và xử lý dữ liệu](https://aws.amazon.com/transit-gateway/pricing/).
- [ENA allowance counters](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html).

Nguồn số đo: [chương kết quả](13-tong-hop-ket-qua.md) và [report-metrics.json](../results/analysis/report-metrics.json).
Kế hoạch bổ sung: [hoàn thiện đến 26/10](16-ke-hoach-hoan-thien-den-26-10.md).
