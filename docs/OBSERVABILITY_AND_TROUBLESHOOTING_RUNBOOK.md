# CẨM NANG GIÁM SÁT & XỬ LÝ SỰ CỐ HIỆU NĂNG MẠNG AWS
## (ADVANCED NETWORK OBSERVABILITY & TROUBLESHOOTING RUNBOOK)

Cẩm nang này hướng dẫn quy trình tiêu chuẩn (SOP - Standard Operating Procedure) để giám sát, phân tích gói tin sâu và xử lý các sự cố suy giảm hiệu năng mạng trên hạ tầng AWS bằng cách kết hợp **VPC Flow Logs**, **Amazon Athena**, **CloudWatch Alarms** và các công cụ dòng lệnh Linux cấp thấp.

---

## 1. Cấu Hình VPC Flow Logs Chuẩn Chuyên Sâu (Custom Format)

Mặc định, VPC Flow Logs định dạng tiêu chuẩn (Default Format v2) chỉ cung cấp các thông tin cơ bản: IP nguồn/đích, Port nguồn/đích, Packets, Bytes, Action. Để điều tra hiệu năng mạng và phân tích bão hòa đường truyền, ta bắt buộc phải sử dụng **Custom Format (v5)**.

### 1.1. Cấu Trúc Log Format Tối Ưu Cho Hiệu Năng
```
${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status} ${tcp-flags} ${flow-direction} ${traffic-path} ${pkt-srcaddr} ${pkt-dstaddr}
```

Ý nghĩa các trường bổ sung quan trọng:
- `${tcp-flags}`: Giá trị bitmask cờ TCP (SYN = 2, SYN-ACK = 18, FIN = 1, RST = 4, ACK = 16). Cho phép phát hiện TCP Reset, Half-open scans, hoặc kết nối bị từ chối.
- `${flow-direction}`: Chiều gói tin (`ingress` hoặc `egress`).
- `${traffic-path}`: Đường đi vật lý của gói tin:
  - `1`: Through an internet gateway / gateway VPC endpoint.
  - `2`: Through a virtual private gateway (Direct Connect / VPN).
  - `3`: Through a VPC peering connection.
  - `4`: Through a transit gateway.
  - `5`: Through a local gateway.
  - `6`: Through a carrier gateway.
  - `7`: Intra-VPC.
  - `8`: Inter-VPC (same Region).
- `${pkt-srcaddr}` & `${pkt-dstaddr}`: Địa chỉ IP thực tế ban đầu của gói tin trước khi bị NAT bởi Network Load Balancer hoặc Transit Gateway.

---

## 2. Truy Vấn Dữ Liệu Lưu Lượng Bằng Amazon Athena

Sau khi đẩy VPC Flow Logs vào Amazon S3 theo định dạng Apache Parquet hoặc text, tạo bảng Athena để phân tích:

### 2.1. Tạo Bảng Dữ Liệu Trong Athena
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS vpc_flow_logs_perf (
  version int,
  account_id string,
  interface_id string,
  srcaddr string,
  dstaddr string,
  srcport int,
  dstport int,
  protocol bigint,
  packets bigint,
  bytes bigint,
  start bigint,
  "end" bigint,
  action string,
  log_status string,
  tcp_flags int,
  flow_direction string,
  traffic_path int,
  pkt_srcaddr string,
  pkt_dstaddr string
)
PARTITIONED BY (region string, year string, month string, day string)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ' '
LOCATION 's3://your-vpc-flow-logs-bucket/AWSLogs/your-account-id/vpcflowlogs/ap-southeast-2/';
```

### 2.2. Các Câu Lệnh SQL Athena Phục Vụ Điều Tra Thực Tế

#### Truy vấn 1: Tìm Top 10 luồng tiêu tốn nhiều băng thông nhất (Top Talkers)
```sql
SELECT 
  srcaddr, 
  dstaddr, 
  dstport, 
  traffic_path,
  SUM(bytes) / (1024 * 1024 * 1024) AS total_gigabytes,
  SUM(packets) AS total_packets,
  (SUM(bytes) * 8.0) / (MAX("end") - MIN(start)) / 1000000 AS avg_megabits_per_sec
FROM vpc_flow_logs_perf
WHERE action = 'ACCEPT'
GROUP BY srcaddr, dstaddr, dstport, traffic_path
ORDER BY total_gigabytes DESC
LIMIT 10;
```

#### Truy vấn 2: Phát hiện các kết nối bị từ chối do Security Group hoặc NACL (REJECT Actions)
```sql
SELECT 
  srcaddr, 
  dstaddr, 
  dstport, 
  protocol,
  COUNT(*) AS reject_count,
  SUM(packets) AS dropped_packets
FROM vpc_flow_logs_perf
WHERE action = 'REJECT'
GROUP BY srcaddr, dstaddr, dstport, protocol
ORDER BY reject_count DESC
LIMIT 20;
```

#### Truy vấn 3: Phát hiện sự bất đối xứng luồng (Asymmetric Routing Detection)
```sql
SELECT 
  srcaddr, 
  dstaddr, 
  traffic_path, 
  flow_direction, 
  SUM(packets) AS total_packets
FROM vpc_flow_logs_perf
WHERE srcaddr LIKE '10.1.%' OR dstaddr LIKE '10.1.%'
GROUP BY srcaddr, dstaddr, traffic_path, flow_direction;
```

---

## 3. Thiết Lập Giám Sát Tự Động Thanh Ghi ENA Bằng CloudWatch

Để không bị bất ngờ khi ứng dụng bị bóp nghẽn mạng phần cứng (Hardware Throttling), ta cấu hình script thu thập đẩy định kỳ vào Amazon CloudWatch Custom Metrics.

### 3.1. Kịch Bản Đẩy Metric Lên CloudWatch (Chạy Cron Mỗi 1 Phút)
```bash
#!/usr/bin/env bash
# /opt/scripts/push_ena_metrics_cw.sh
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="ap-southeast-2"

# Đọc các chỉ số allowance từ ethtool
BW_IN=$(ethtool -S eth0 | awk '/bw_in_allowance_exceeded/ {print $2}')
BW_OUT=$(ethtool -S eth0 | awk '/bw_out_allowance_exceeded/ {print $2}')
PPS_EXC=$(ethtool -S eth0 | awk '/pps_allowance_exceeded/ {print $2}')
CONNTRACK_EXC=$(ethtool -S eth0 | awk '/conntrack_allowance_exceeded/ {print $2}')

# Đẩy vào CloudWatch Namespace 'AWS/EC2/NetworkPerformance'
aws cloudwatch put-metric-data --namespace "AWS/EC2/NetworkPerformance" \
  --region "${REGION}" \
  --metric-data \
    MetricName=BwInAllowanceExceeded,Value="${BW_IN}",Unit=Count,Dimensions=[{Name=InstanceId,Value="${INSTANCE_ID}"}] \
    MetricName=BwOutAllowanceExceeded,Value="${BW_OUT}",Unit=Count,Dimensions=[{Name=InstanceId,Value="${INSTANCE_ID}"}] \
    MetricName=PpsAllowanceExceeded,Value="${PPS_EXC}",Unit=Count,Dimensions=[{Name=InstanceId,Value="${INSTANCE_ID}"}] \
    MetricName=ConntrackAllowanceExceeded,Value="${CONNTRACK_EXC}",Unit=Count,Dimensions=[{Name=InstanceId,Value="${INSTANCE_ID}"}]
```

### 3.2. Cấu Hình CloudWatch Alarm Bằng AWS CLI
Tạo báo động ngay khi có bất kỳ gói tin nào bị bóp nghẽn trong 5 phút:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "Alarm-EC2-Network-Throttling-Sydney" \
  --alarm-description "Canh bao khi EC2 bi bop nghen bang thong hoac PPS tai Nitro Card" \
  --metric-name "BwOutAllowanceExceeded" \
  --namespace "AWS/EC2/NetworkPerformance" \
  --statistic "Sum" \
  --period 300 \
  --threshold 1 \
  --comparison-operator "GreaterThanOrEqualToThreshold" \
  --evaluation-periods 1 \
  --region ap-southeast-2
```

---

## 4. Quy Trình 5 Bước Khắc Phục Sự Cố Mạng (Troubleshooting Workflow)

Khi ứng dụng gặp hiện tượng chậm đường truyền, timeout kết nối hoặc rớt thông lượng:

```
                  +----------------------------------------------+
                  | BƯỚC 1: KIỂM TRA THANH GHI PHẦN CỨNG NITRO  |
                  |     (ethtool -S eth0 | grep allowance)       |
                  +----------------------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
              [Có biến đếm > 0]                   [Mọi biến đếm = 0]
                       |                                   |
                       v                                   v
        +-------------------------------+  +--------------------------------+
        | NGUYÊN NHÂN: Chạm trần AWS   |  | NGUYÊN NHÂN: Phần mềm/Định tuyến|
        | - bw_out: Instance quá nhỏ     |  | - Kiểm tra MTU & PMTUD         |
        | - pps: Quá nhiều gói tin nhỏ  |  | - Kiểm tra Route Table/NACL/SG |
        | - conntrack: Vượt phiên SG     |  | - Kiểm tra SoftIRQ / CPU load  |
        +-------------------------------+  +--------------------------------+
                       |                                   |
                       v                                   v
             [Nâng cấp Instance Type             [Dùng traceroute, ping,
             hoặc bật Jumbo Frames]               ss -tiepm, tcpdump]
```

### Chi tiết hành động khắc phục:
1. **Nếu `bw_out_allowance_exceeded` tăng**:
   - Instance đã xài hết burst credits hoặc đạt trần băng thông phân bổ.
   - *Khắc phục*: Nâng cấp cỡ instance (ví dụ từ `c6i.large` lên `c6i.xlarge` hoặc `c6i.2xlarge`) để có baseline bandwidth lớn hơn.
2. **Nếu `pps_allowance_exceeded` tăng**:
   - Hệ thống gửi quá nhiều gói tin kích thước nhỏ làm nghẽn hàng đợi ngắt.
   - *Khắc phục*: Chuyển sang kích hoạt **Jumbo Frames (MTU 9001)** trong VPC và cấu hình TCP Segmentation Offload (`ethtool -K eth0 tso on`).
3. **Nếu `conntrack_allowance_exceeded` tăng**:
   - Số phiên kết nối mở đồng thời vượt quá năng lực tracking của Security Group.
   - *Khắc phục*: Thay thế các luật Security Group bằng **Network Access Control Lists (NACL)** cho các luồng traffic tĩnh khối lượng lớn (vì NACL là stateless, hoàn toàn không tốn tài nguyên conntrack!).
4. **Nếu kết nối ngắt sau đúng 350 giây**:
   - Hiện tượng điển hình của NAT Gateway Idle Timeout.
   - *Khắc phục*: Bật TCP Keepalive trên ứng dụng với thời gian thăm dò `< 300` giây (`sysctl -w net.ipv4.tcp_keepalive_time=120`).
5. **Nếu lưu lượng qua Transit Gateway bị rớt gói chập chờn**:
   - Hiện tượng Asymmetric Routing do thiếu Appliance Mode khi có tường lửa stateful.
   - *Khắc phục*: Bật Appliance Mode trên Transit Gateway VPC Attachment:
     ```bash
     aws ec2 modify-transit-gateway-vpc-attachment \
       --transit-gateway-attachment-id tgw-attach-xxxxxx \
       --options ApplianceModeSupport=enable \
       --region ap-southeast-2
     ```
