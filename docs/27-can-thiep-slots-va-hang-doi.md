# Kiểm chứng khả năng xử lý worker và hàng đợi

Trạng thái: protocol đã khóa ngày 12/10/2026; engineering validation tách
riêng; không mặc định việc viết code hoặc chạy một phiên là đã đủ xác nhận.

## Câu hỏi có thể kiểm chứng

Giữ tải 800 yêu cầu/s và tác vụ cố định, tăng đồng thời C/D từ 8 lên 16
slots có cải thiện tỷ lệ đúng hạn 50 ms hơn 10 điểm phần trăm, trung bình
qua Peering/TGW, trong đa số block ghép cặp hay không?

Đây là can thiệp có kiểm soát trên ứng dụng tổng hợp. Giới hạn slots và
I/O sleep do thí nghiệm đặt; xác nhận cơ chế trong workload này không phải
phát hiện giới hạn nội tại AWS hoặc một quy luật chưa biết. Mạng vẫn là
factor của thiết kế, không đổi tên đề tài thành benchmark chỉ về asyncio.

## Tám tổ hợp trong mỗi block

| Factor | Giá trị |
|---|---|
| Đường mạng | Peering / TGW |
| Slots trên mỗi worker C/D | 8 / 16 |
| Tốc độ yêu cầu A | 600 / 800 yêu cầu/s |

Cả hai worker luôn cùng cấu hình. Mỗi request A làm B gọi C và D song song;
mỗi worker nhận λ yêu cầu/s, không tự cộng thành 2λ trên một worker.
Giữ 10 ms I/O mô phỏng, 4096 bytes/worker, MTU 1500, cùng loại EC2/AMI/AZ,
deadline 50 ms, timeout 2 s, generator cap 4000, FD server 8192.
Mỗi tổ hợp warm-up 5 s, chờ hết backlog, lập lịch đo 15 s rồi thu toàn bộ
kết quả/timeout. Fresh server trước mỗi tổ hợp loại backlog điều kiện trước.
Tracing đầy đủ tắt; ghi worker timing nhẹ giống nhau trong mọi tổ hợp.

Thứ tự mạng cân bằng 8 block mỗi kiểu; thứ tự bốn tổ hợp slots/tải dùng
bốn phép xoay vòng cân bằng, phân bổ ngẫu nhiên trước. Hai mode trong cùng
block dùng cùng thứ tự tổ hợp. Đây không phải IID request/Poisson arrival.

## Dữ liệu mới tại worker

A đặt `X-NT531-Request-ID`, B truyền cùng mã tới C/D. Các request warm-up
có prefix riêng. Trên mỗi worker, lưu e_i lúc vào, b_i khi lấy được slot,
c_i lúc xong tác vụ, x_i khi thoát handler. Tất cả lấy từ cùng đồng hồ
monotonic trên worker, không trừ timestamp C với D hay A.

- Wq_i = 1000(b_i − e_i): thời gian chờ lấy slot, đơn vị ms.
- S_i = 1000(c_i − b_i): thời gian phục vụ thực, gồm delay và timer/scheduling.
- Q_i: số đang chờ trước lúc i vào; H_i: số đang có slot trước lúc i vào.
- Status: handler_completed, cancelled hoặc tên lỗi; mốc chưa có giữ null.

Log được thêm vào bộ nhớ ngay khi handler vào, cập nhật mốc khi tiến triển,
nén/lưu sau shutdown. Không chỉ log request được A nhận thành công. Giữ
request không tới worker, client timeout nhưng worker tiếp tục xử lý, và
handler bị hủy; báo cáo đủ các nhóm. Handler hoàn tất không chứng minh A
đã nhận kết quả. aiohttp mặc định có thể tiếp tục xử lý sau khi peer đóng;
xem [tài liệu server](https://docs.aiohttp.org/en/stable/web_advanced.html#peer-disconnection).

Tính P50/P95 chờ và phục vụ theo node; nêu mẫu số của quantile (có mốc
bắt đầu / hoàn tất) và số missing/cancelled. Không cộng Wq_C + Wq_D như
hai bước nối tiếp; hai RPC chồng nhau, đường tới kết quả phụ thuộc nhánh chậm.
Kích thước log/CPU và lịch generator cần qua engineering validation;
không kết luận logger không có overhead từ một phiên. Phiên formal luôn
dùng cùng instrumentation ở tất cả điều kiện.

## Outcome và phép kiểm định chính

Với block j, mode m, slots s, tải λ:

    p̂_(j,m,s,λ) = số phản hồi đúng và hoàn tất ≤50 ms / số yêu cầu theo lịch
    d_j = [(p̂_(j,P,16,800) − p̂_(j,P,8,800))
          +(p̂_(j,T,16,800) − p̂_(j,T,8,800))] / 2
    Z_j = 1 nếu d_j > 0,10; ngược lại bằng 0
    K = Σ Z_j; θ = P(d_j > 0,10) theo quá trình lấy mẫu block

P/T là Peering/TGW; d_j là chênh tỷ lệ (nhân 100 để thành điểm phần trăm).
Ngưỡng 0,10 lấy từ kế hoạch trước phiên can thiệp, nhằm yêu cầu cải thiện
có ý nghĩa thực tế, không chỉ một chênh lệch nhỏ. Đây là tiêu chí thiết kế
của workload, không phải SLA do một đơn vị ngoài cấp.

H0: θ ≤ 0,5; H1: θ > 0,5. Với n=16 và giả định block độc lập phù hợp,
test một phía dùng đuôi nhị thức exact:

    p-value = Σ từ k=K đến 16 [ C(16,k) × 0,5^k × 0,5^(16−k) ]

Tại K=12, p=0,038406; K=11 chưa qua α=0,05. Hòa đúng ngưỡng không tính
là thành công. Cận dưới θ một phía 95% giải phương trình
P_(θ_L)(Binomial(16,θ_L) ≥ K)=0,05 (K=0 thì θ_L=0).
Đây là xác suất **qua block**, khác tỷ lệ request đúng hạn p̂.
[SciPy binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)
là tài liệu đối chiếu kiểm định nhị thức và khoảng tin cậy exact.

Nếu giả định θ=0,8, xác suất đạt K≥12 khoảng 0,7982. Đây là tính power
từ giả định, không phải effect đã đo hoặc lời hứa CI hẹp. Không dừng sớm
khi thấy đủ dấu thuận lợi; thu đủ 16 block hợp lệ, tối thiểu 4 ngày, cách
nhau ≥2 giờ. Spacing không tự chứng minh độc lập; công bố thời điểm/cohort.

Đồng thời báo cáo effect từng block, mean chênh tỷ lệ và CI bootstrap 95%
resample nguyên block (20.000 lần, cùng indices cho tất cả contrasts).
Chênh mạng ở từng tải/slots là secondary descriptive; không kiểm định
thêm rồi chọn kết quả thắng, không kết luận tương đương từ p>0,05.
Không công bố suy luận khi chưa đủ block/ngày/chất lượng.

## Liên hệ bài học và giới hạn mô hình

λ là tốc độ đến, c là số slots, s là thời gian phục vụ lý tưởng 0,010 s.
ρ_nom = λs/c: tại 800 rps, c=8 cho 1; c=16 cho 0,5. Chỉ số này giúp chọn
can thiệp, không phải utilization đo được; dùng S_i để đối chiếu overhead.
CPU host và ENA là chẩn đoán riêng. Chờ slot có thể tăng dù CPU chưa 100%
vì đây là I/O mô phỏng có concurrency cap.

Đồ án liên hệ Arrival Processes/Queuing Systems ở e_i, Wq_i, S_i và tải
đến; QoS ở deadline success và phân vị đuôi. Không ép dữ liệu đều/nhiều
slots thành M/M/1, không tính Little's Law khi chưa kiểm tra trạng thái dừng
và thu đủ throughput/occupancy cùng cửa sổ. Phiên 15 s là thử tải hữu hạn.
Xem [đối chiếu bài giảng](17-doi-chieu-bai-giang-va-cong-cu.md).

Nếu tăng slots làm chờ giảm, service time gần ổn định và đúng hạn tăng
lặp lại, dữ liệu hỗ trợ tác động của can thiệp này và cơ chế hàng đợi.
Không khẳng định chờ là nguyên nhân duy nhất hoặc mọi ứng dụng sẽ như vậy.
Nếu không cải thiện, vẫn giữ dữ liệu và xem CPU/lịch generator/ENA/nhánh RPC;
không đổi threshold hay tác vụ để đạt kết quả mong muốn.

## Chạy và lưu trữ

```powershell
py scripts/application-slots.py init
py scripts/application-qos.py setup
py scripts/application-slots.py engineering
tmp/application-venv/Scripts/python.exe experiments/application-qos/analyze_slots.py RESULTS_FOLDER
py scripts/application-slots.py block --block 1
tmp/application-venv/Scripts/python.exe experiments/application-qos/analyze_slots.py --study
```

`init` từ chối ghi đè protocol. Engineering có thư mục riêng và không được
analyzer đưa vào confirmatory inference. Mỗi attempt lưu app/runner/deployment/
requirements thực chạy, hash, boot ID/uptime, route, mọi request, C/D queue
logs và CPU/ENA theo tổ hợp. Lỗi kỹ thuật giữ nguyên, không tự retry.

Mỗi block formal phải cùng EC2/TGW cohort, AMI cố định, uptime ≥30 phút,
MTU/NTP đúng, app source hash khớp. Stop/start giữ ID nhưng có thể đổi host;
boot ID/uptime được ghi, không mô tả thành cùng host vật lý. Nếu xóa/dựng
lại phải mở cohort/nghiên cứu riêng, không gộp vào v1.

Cuối phiên dừng app/monitor và khôi phục route ban đầu. Theo lựa chọn của
người dùng, stop bốn EC2 sau khi sao lưu; giữ EBS/EIP/TGW. Các tài nguyên
giữ lại vẫn có phí ([EC2 lifecycle](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html),
[TGW pricing](https://aws.amazon.com/transit-gateway/pricing/),
[IPv4 pricing](https://aws.amazon.com/vpc/pricing/)). Đợt RTT riêng không chạy
đồng thời với ứng dụng; protocol RTT và các block cũ không bị sửa.
