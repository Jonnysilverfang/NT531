# Đợt xác nhận RTT và phép thử có tiêu chí kết luận — 12/10/2026

## Câu hỏi cần trả lời

**Trong cohort EC2 và các khung thời gian được lấy mẫu, lợi thế RTT của Peering
so với TGW có vượt 0.1 ms ở đa số đợt đo, với bằng chứng thống kê hay không?**

Dữ liệu 05–06/10 là khám phá, giúp chọn câu hỏi. Không đưa chúng vào đợt xác
nhận này. Ngưỡng 0.1 ms do nhóm chọn trước dữ liệu xác nhận, là mức chênh lệch
quan tâm của nghiên cứu, không phải SLA AWS hoặc yêu cầu ứng dụng được chứng minh.
Nếu nhóm cần ngưỡng theo một ứng dụng thật, chốt cohort/protocol mới trước khi đo.

Không phải đề tài không có kết luận: hiện đã có chênh lệch quan sát, ENA và
trade-off kiến trúc. Phần cần thêm là một phép xác nhận có thiết kế và độ bất
định, để chuyển từ “phiên này khác nhau” sang “khác biệt lặp lại trong phạm vi
nghiên cứu”. Không đặt mục tiêu chứng minh một dịch vụ tốt hơn trong mọi trường hợp.

## Thiết kế đã chốt trước

Protocol: [protocol.json](../results/confirmation-rtt-v1/protocol.json).
Ngày khởi tạo và thứ tự được lưu trước khi có mẫu mới. Lệnh Init từ chối ghi
đè hoặc xáo lại. Nếu sửa thiết kế phải ghi phiên bản mới và lý do, không sửa
ngầm sau khi thấy p-value.

| Hạng mục | Quy tắc |
|---|---|
| Đơn vị thống kê | Một block ghép cặp, có cả Peering và TGW |
| Số block | 16, cố định trước; không dừng sớm vì p nhỏ |
| Thời gian | Ít nhất 4 ngày địa phương, start của hai block cách ≥2 giờ |
| Mỗi mode trong block | 3 lượt × 100 probe, interval 0.2 s, payload 56 byte, timeout 2 s |
| Endpoint | A/B c6i.large, cùng AMI, us-east-1a, MTU1500, NTP đồng bộ |
| Thứ tự | Xáo một lần 8 block Peering trước, 8 block TGW trước; lưu seed và lịch |
| Chuyển mode | Chỉ đổi route, kiểm AWS A↔B trước và sau phép đo |
| Ổn định | Chờ 30 s sau đổi route; 10 probe warm-up riêng; nghỉ 5 s giữa lượt |
| Workload | Không có TCP benchmark đang kết nối ở cổng 5201–5203 |
| Giới hạn ghép cặp | Toàn block không quá 20 phút |
| Raw | Ping stdout/stderr/exit, CPU trước/sau, route snapshot, kernel, instance IDs, timestamp và hash protocol |

Tổng mới: 16 × 2 × 3 = **96 lượt ping**, 9.600 probe chính. Đây là 16 block
cho suy luận, không phải 9.600 thí nghiệm độc lập. Thời gian ping chính khoảng
32 phút; cộng chuyển route/preflight/warm-up/nghỉ. Phân bố các block theo thời
gian để quan sát độ tái lập, không chạy dồn liên tục rồi gọi là độc lập.
Khoảng cách 2 giờ và 4 ngày là quy tắc lấy mẫu, không chứng minh toán học các
block độc lập; phải xem xét nhiễu chung, hiệu ứng thứ tự và lịch hoạt động.

Hạ tầng đã được dọn để giảm phí. Khi được khôi phục, EC2 có thể ở host vật lý
mới: đó là cohort xác nhận mới. Không gộp nó với baseline cũ để tính p-value.
Trong đợt này giữ nguyên instance IDs và TGW ID giữa 16 block. Có thể stop/start
EC2 nhưng không destroy/recreate rồi âm thầm gộp thành cùng cohort.

## Đại lượng và giả thuyết

Với block b, mode m và lượt j:

$$
\bar x_{m,b}=\frac{x_{m,b,1}+x_{m,b,2}+x_{m,b,3}}{3},\qquad
d_b=\bar x_{TGW,b}-\bar x_{Peering,b}.
$$

x_m,b,j là RTT avg trong summary ping của lượt j, ms; b=1,…,16; m là mode;
d_b>0 nghĩa TGW có RTT cao hơn. Ba lượt là lặp kỹ thuật trong block, không
tăng n của kiểm định từ 16 lên 48. Mean/SD từ summary có độ chính xác hiển thị
của ping; giữ raw. Mất phản hồi ghi riêng; không coi missing như RTT bằng 0.

Đặt δ=0.1 ms, chỉ báo Z_b=1{d_b>δ}, và π=P(d_b>δ) đối với quá trình lấy
block được định nghĩa. Đây là xác suất ở **cấp block**, không phải xác suất
một packet chậm. Ties d_b=δ được tính là không vượt ngưỡng, không bỏ để tăng
tỷ lệ thành công.

$$
K=\sum_{b=1}^{16}Z_b,\qquad H_0:\pi\le0.5,\quad H_1:\pi>0.5.
$$

Với block đủ độc lập và xác suất phù hợp với mô hình binomial, p-value một
phía tại biên H0 π=0.5:

$$
p_{value}=\sum_{j=K}^{16}\binom{16}{j}(0.5)^{16}.
$$

K là số block vượt δ; tổ hợp 16 chọn j đếm cách có j block vượt ngưỡng.
π và p-value không có đơn vị. p-value không phải xác suất H0 đúng. Đây là
kiểm định binomial của sự kiện vượt margin, gần ý tưởng sign test nhưng giữ
ties như non-success; không giả vờ nó là kiểm định chênh lệch mean hai phiên.
[NIST về paired sign test và mô hình dấu binomial](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/signtest.htm).

Chốt α=0.05. Với 16 block: **K≥12** đủ để bác bỏ H0 theo phép thử này;
K=12 cho p=0.0384064, K=11 cho p>0.05. Không dùng p-value trước khi đủ
16 block và đáp ứng quy tắc chất lượng/thời gian. Không kiểm thêm nhiều
ngưỡng rồi chọn p nhỏ nhất; các đầu ra khác là mô tả/phân tích khám phá.

Cận dưới exact một phía 95% của π là π_L thỏa:

$$
\sum_{j=K}^{16}\binom{16}{j}\pi_L^j(1-\pi_L)^{16-j}=0.05
$$

với K>0; K=0 lấy π_L=0. Cận mô tả độ bất định theo mô hình, không là mức
đảm bảo AWS. Script giải bằng bisection và kiểm trường hợp K=16 có nghiệm
π_L=0.05^(1/16). Bác bỏ H0 tương ứng π_L>0.5 trong các trường hợp không ở
biên. Mean, median, min/max d_b và kết quả theo thứ tự được công bố kèm theo.

Script còn xuất cận dưới cho median của d bằng order statistics. Với B=16,
giá trị thứ 5 nhỏ nhất là cận một phía có coverage danh nghĩa 96.1594% trong
mô hình liên tục/độc lập, nên bảo thủ so với 95%; ties có thể làm bảo thủ hơn.
Không gọi đó là CI cho mean hoặc độ chính xác đo được của thiết bị.

## Vì sao 16 block, có chắc sẽ “thành công” không?

Không bảo đảm. Theo mô hình giả định π=0.8, xác suất đạt K≥12 là
P[Binomial(16,0.8)≥12]≈0.798245, gần 80%. **π=0.8 là giả định lập kế hoạch**,
không được suy ra chắc chắn từ baseline cũ. Đây là tính công suất minh họa,
không phải phép đo mới. Nếu hiệu ứng yếu/biến thiên lớn, kết quả có thể không
bác bỏ H0. Công bố đúng kết quả đó; không chạy thêm cho tới khi p đẹp.

## Tiêu chí và câu kết luận sau khi đo

Nếu đủ 16 block, không có vi phạm dữ liệu, K≥12, cận π_L>0.5 và median d
theo cả hai thứ tự đều >δ, có thể viết:

> Trong cohort bốn VPC/cặp EC2 A–B c6i.large cùng AZ và các khung thời gian
> được lấy mẫu, kết quả xác nhận ủng hộ rằng lợi thế RTT idle của Peering vượt
> 0.1 ms ở đa số block. Có …/16 block vượt margin, p-value một phía …, cận dưới
> exact của xác suất vượt margin …; chênh lệch trung bình … ms.

Thay dấu … bằng số thực tế; chưa có câu kết luận này ở hiện trạng 2/16.
Các giả định về block và nhiễu chung phải nêu cùng kết luận. Điều kiện hai
thứ tự là kiểm tra mô tả bổ sung; không lấy p-value của từng nhóm để chọn kết
quả. Nếu hai thứ tự khác nhiều, điều tra carryover/thời điểm, không bỏ một nhóm.

Nếu K<12: “Chưa đủ bằng chứng xác nhận lợi thế vượt margin theo thiết kế này”,
không viết hai dịch vụ tương đương. Có mất phản hồi: giữ raw, công bố tỷ lệ,
không bỏ lượt để lấy latency đẹp; script chưa tự chốt kết luận vì vấn đề chọn
mẫu phản hồi. Lỗi kỹ thuật giữ nguyên attempt và lý do; không tự retry vì RTT
cao. Nhiều attempt hoàn tất cho một block cần adjudication, không chọn tốt nhất.

## Sau đó: RTT khi tải có kiểm soát

Đã chuẩn bị worker và lệnh Load, nhưng chưa có dữ liệu. Đây là một phiên
khám phá riêng, không nhập 18 lượt của nó vào K/B ở trên. Cùng A/B/MTU1500,
mode thứ tự đã ghi, các mức đặt TCP P1 là 0, 250 và 500 Mbps; mỗi mức 3 lượt
ping mỗi mode. Tổng 18 lượt ping: 6 idle, 12 có tải. Không tạo UDP hoặc đổi SG.

TCP dùng -O5 -t30; chờ 10 giây kể từ launch rồi ping 100 probe, kiểm TCP còn
sống cả đầu/cuối cửa sổ ping. Lưu JSON iperf, ping timestamp, CPU A và ENA A;
goodput thực đạt có thể khác mức -b đặt. Đọc receiver rate và interval thật,
không gọi -b là tải được đảm bảo. Mốc wrapper/khởi động không chứng minh căn
chính xác thời gian iperf; giữ trace và ghi giới hạn đo.

Phân tích sau thu: P50/P95/ECDF, loss, ΔP95=P95_load−P95_idle (ms), rate
thực đạt, CPU và delta ENA. Rate đặt nhỏ hơn baseline nhằm quan sát latency
khi tải vừa, không phải thử max throughput. Không coi RTT TCP_INFO bằng RTT
ICMP. Không suy ra vị trí hàng đợi hoặc λ/μ của TGW từ các đại lượng này.
Nếu cần kết luận suy luận cho loaded RTT, phải thiết kế các block loaded riêng.

## Chạy và bảo vệ dữ liệu

```powershell
# Chạy từ D:\NT531-DanhGiaHieuNang; dùng state vận hành, không chạy từ clone Git.
.\scripts\Run-RTTConfirmation.ps1 -Action SelfTest
.\scripts\Run-RTTConfirmation.ps1 -Action Analyze

# Sau khi hạ tầng được khôi phục/SSM chuẩn bị: một lệnh cho một block.
.\scripts\Run-RTTConfirmation.ps1 -Action Block -Block 1
# Các block 2…16 ở các khung thời gian đã lên lịch, cách >=2 giờ.

# Sau đủ 16 block hợp lệ, mới chạy phiên loaded RTT khám phá:
.\scripts\Run-RTTConfirmation.ps1 -Action Load
```

Init đã chạy một lần và protocol được đóng băng. Không cần tự gõ timestamp
vào bốn máy hoặc tải file thủ công. Runner dùng SSM trên A/B, lưu về results,
đổi route bằng plan chỉ cho aws_route update tới CIDR VPC, và phục hồi mode
ban đầu trong finally. Nó không cấp tài nguyên, không start máy, không hủy
resource. Nếu API/auth lỗi trong lúc phục hồi, kiểm AWS trước khi đo tiếp.

Không dùng screenshot để chứng minh mode: trước/sau mỗi mode có route snapshot
A↔B và analyzer kiểm lại target. Cohort/hash/time/missing/duplicate được kiểm
trước kết luận. Script bảo vệ workflow, không chứng minh cloud không có mọi
nhiễu. Raw trên EC2 cũng được giữ; stdout SSM trả gói gzip/base64 có giới hạn.

## Hiện trạng

**2/16 block hợp lệ**. Ngày 12/10/2026, Terraform đã apply đúng plan
**100 tạo, 0 sửa, 0 xóa**: 4 VPC, 4 EC2/EIP, 6 Peering, 1 TGW/4 attachment
và các tài nguyên mạng/IAM/rule liên quan. Bốn máy Online qua SSM, cùng MTU
1500, có listener iperf3 5201–5203 và đã pass full-mesh ICMP/TCP/smoke test
ở mode TGW.

Block 1 chạy Peering rồi TGW, nhận đủ 300/300 packet mỗi mode. Mean của ba
RTT avg là 0,2113 ms và 0,4417 ms; `d₁=+0,2303 ms>δ`, nên `Z₁=1`. Route đã
phục hồi về TGW. Đây là bằng chứng ban đầu, chưa có kết luận suy diễn trước
khi đủ 16 block.

Block 2 bắt đầu 21:26:56 giờ Việt Nam ngày 12/10, thứ tự TGW rồi Peering.
Peering đạt 0,2067 ms, TGW 0,4463 ms; `d₂=+0,2397 ms`, nhận đủ 300/300
packet mỗi mode. Route phục hồi về TGW. Hiện có `Z₁=Z₂=1` nhưng chưa thực
hiện suy luận; block 3 chỉ được bắt đầu từ 23:26:57 ngày 12/10 hoặc muộn hơn.

Cohort xác nhận: A `i-089bae0de9ec6bc4e`, B `i-0484f42b82795f765`, TGW
`tgw-036e551008b8c0805`. Giữ các ID này giữa 16 block; không destroy/recreate
rồi gộp dữ liệu. EIP mới và toàn bộ ID triển khai nằm trong
[`deployment.json`](../results/confirmation-rtt-v1/deployment.json).

## Dự toán trước khi khôi phục

[Preview và trạng thái apply](../results/confirmation-rtt-v1/recovery-preview.json)
ghi giá Price List API của AWS us-east-1: VPC attachment TGW 0.05 USD/giờ,
SKU 9N2FHGMMCZBKDCGH, version 20260917190528. IPv4/EIP 0.005 USD/giờ theo
[AWS VPC pricing](https://aws.amazon.com/vpc/pricing/).

Với bốn attachment và bốn EIP, phần giữ tài nguyên là
4×0.05 + 4×0.005 = **0.22 USD/giờ**. Nếu giữ đúng 96 giờ, riêng hai khoản này
là **21.12 USD**, chưa tính EC2 chạy, EBS, data processing/transfer, thuế hoặc
ưu đãi/credit. Đây không phải báo giá toàn đồ án hay hóa đơn actual. TGW có
quy tắc tính giờ lẻ; lấy thời lượng billed thực khi tính tổng.

Giảm lưu lượng benchmark không loại phí giữ attachment/EIP. Vì người dùng
đã dọn để giảm phí, không tự apply plan phục hồi khi chưa chốt việc này.
AMI/key pair đã kiểm tra còn dùng được; plan không chứa private key và nằm
trong tmp, bị Git bỏ qua. Sau này tạo plan mới nếu config/state thay đổi.
