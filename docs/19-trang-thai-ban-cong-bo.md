# Trạng thái bản công bố — 07/10/2026

Đây là bản lưu tiến độ để giảng viên và thành viên nhóm đọc code, kiểm chứng số liệu
và biết việc còn lại. Không quy đổi số file hoặc số bài đo thành phần trăm điểm số.
Không có phép đo AWS mới trong lần chuẩn bị công bố này.

## Đã hoàn thành và đưa vào bản Git

| Hạng mục | Bằng chứng và nơi đọc |
|---|---|
| Hạ tầng bốn VPC, bốn EC2/EIP, sáu Peering, một TGW/bốn attachment | [Terraform](../infra/terraform/README.md), [kiến trúc](03-bon-vpc.md) |
| Chuyển 12 route liên VPC giữa hai mode trên cùng endpoint | Code Terraform, route snapshot trong results/verification-20261005 và results/formal |
| RTT khi rảnh A→B→A: 5 lượt mỗi mode | [Số liệu gốc và bảng từng lượt](18-so-lieu-de-kiem-chung.md) |
| TCP một luồng A→B: 5 lượt mỗi mode, CPU/ENA hai máy | [Kết quả một cặp](07-ket-qua-tcp-mot-cap.md) |
| TCP fan-in A/C/D→B: 5 lượt mỗi mode, CPU/ENA | [Peering](10-ket-qua-fan-in-peering.md), [TGW và so sánh](12-ket-qua-fan-in-tgw-va-so-sanh.md) |
| Chương kết quả 19 trang, ba sơ đồ và bốn biểu đồ | [DOCX](13-chuong-ket-qua.docx), [hướng dẫn đọc](13-tong-hop-ket-qua.md) |
| 18 công thức có ký hiệu, đơn vị, ví dụ và điều kiện áp dụng | [Công thức](14-cong-thuc-va-ky-hieu.md) |
| Khái niệm và kết luận lựa chọn theo tiêu chí | [Khái niệm và kết luận](15-khai-niem-va-ket-luan-so-sanh.md) |
| Đối chiếu bài giảng và kế hoạch trước 26/10 | [Bài giảng](17-doi-chieu-bai-giang-va-cong-cu.md), [kế hoạch](16-ke-hoach-hoan-thien-den-26-10.md) |
| Tính lại từ raw bằng script độc lập | 434 kiểm tra đạt trên 307 file nguồn duy nhất; [JSON kiểm chứng](../results/analysis/independent-review.json) |

Kiểm tra khi chuẩn bị bản này: `terraform fmt -check`, `terraform validate`
và ba test `terraform test` dùng mock AWS đều đạt. Mock test không gọi AWS,
không tạo tài nguyên và không thay thế bằng chứng connectivity thực tế.

Sáu bộ chính là ba bài × hai mode, mỗi bộ năm lượt. Bài hai cặp độc lập
A→B và C→D qua Peering đã có như phần bổ sung; không coi nó là bộ so sánh
đầy đủ khi chưa có dữ liệu TGW đối ứng được kiểm chứng.

## Kết quả hiện có

| Chỉ số | Peering | TGW |
|---|---:|---:|
| RTT khi rảnh, trung bình năm RTT avg (ms) | 0.2078 | 0.5630 |
| TCP một luồng, goodput phía nhận (Gbps) | 4.782804 | 4.608265 |
| Fan-in, tổng goodput trung bình xấp xỉ (Gbps) | 11.611009 | 11.590520 |
| CPU busy B khi fan-in (%) | 59.1802 | 56.8751 |

Peering có RTT thấp hơn và goodput một luồng cao hơn khoảng 3.79% trong các
phiên này. TGW có lợi thế về kiến trúc kết nối nhiều VPC và định tuyến tập trung.
Tổng fan-in gần nhau và ENA trên B cho thấy chạm giới hạn endpoint; chưa thể
xếp hạng năng lực tối đa của hai dịch vụ. Hai mode được đo nối tiếp, chưa phải
các đợt cân bằng thứ tự. Tổng fan-in vẫn theo cửa sổ riêng từng nguồn, chưa
phải tổng chính xác trên cùng cửa sổ. Không suy ra tương đương thống kê.

## Việc tiếp theo, chưa hoàn thành

1. Phân tích log đã có: P50/P95/ECDF RTT, TCP cwnd/RTT theo thời gian và kiểm tra
   khả năng căn chỉnh interval fan-in. Phương pháp và quy tắc lấy cửa sổ phải ghi rõ.
2. Related work, giải thích mã công cụ đo, mô hình chi phí có nguồn và giả định.
3. Đề xuất bốn đợt lặp RTT/TCP cân bằng thứ tự: 24 lượt ping và 24 lượt TCP bổ sung.
   Chỉ thực hiện sau khi chốt thiết kế và dự toán; hiện chưa có số liệu các đợt này.
4. RTT khi có tải: đề xuất 18 lượt RTT, gồm sáu idle và 12 có tải; chưa thực hiện.
5. Ghép báo cáo toàn bộ, slide, demo và video dự phòng; rà số liệu trước ngày 26/10.

Chi tiết công thức CI theo đợt, tổng goodput cửa sổ chung và chi phí nằm trong
[kế hoạch](16-ke-hoach-hoan-thien-den-26-10.md). Công thức hoặc bài dự kiến không
đồng nghĩa đã có kết quả. Không tính CI ghép theo đợt từ hai phiên cũ bằng cách
ghép tùy ý lượt có cùng số thứ tự.

## Kiểm chứng và phân biệt nguồn

Từ gốc repo, với Python 3.10 trở lên:

```powershell
python scripts/verify-results-for-review.py
```

Script chỉ đọc các phép đo chuẩn, tính lại số liệu và cập nhật gói kiểm chứng
`results/analysis/independent-review.json` cùng `docs/18-so-lieu-de-kiem-chung.md`.
Không gọi AWS, không tạo tải. Raw trùng, smoke test và log phụ được giữ để truy vết;
chỉ các đường dẫn được chỉ ra trong gói kiểm chứng tham gia bảng kết quả chính.

Thiết kế cũ và dữ liệu mô phỏng nằm trong `legacy/pre-four-vpc/` trên GitHub.
Chúng không phải phép đo AWS hiện tại. `docs/05-trang-thai-trien-khai.md` là nhật ký
theo thời gian; các đoạn trạng thái cũ không phải giám sát tài nguyên đang chạy.

Repo không chứa private key, credentials, Terraform state/plan, file biến thật
hoặc ZIP backup. Clone repo không mang theo state hoặc quyền truy cập AWS.
