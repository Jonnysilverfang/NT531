# Dữ liệu AWS thực nghiệm của đồ án

Ba bài chính (RTT idle, TCP một luồng, TCP fan-in) × hai mode Peering/TGW,
mỗi bộ năm lượt. Các phiên chính diễn ra ngày 05–06/10/2026. Không dùng
dữ liệu mô phỏng trong `legacy/pre-four-vpc/results/` để tính số liệu ở đây.

Nguồn chuẩn từng lượt, đơn vị, cửa sổ tính và SHA256 nằm trong
[gói kiểm chứng độc lập](analysis/independent-review.json), đọc cùng
[bảng số liệu](../docs/18-so-lieu-de-kiem-chung.md).
Chạy lại: `python scripts/verify-results-for-review.py` từ gốc repo.

- RTT Peering: `pilot-peering/rtt-idle-a-b/nt531-results/peering-rtt-idle-a-b-20261005T115510Z-6qX9Gm/`.
- RTT TGW: `formal/tgw/rtt-idle-a-b/nt531-results/tgw-rtt-idle-a-b-20261005T120751Z-mx0lij/`.
- TCP một luồng: `formal/peering/tcp-single-a-b/` và `formal/tgw/tcp-single-a-b/`; dùng các folder A/B được gói kiểm chứng chỉ ra.
- Fan-in Peering chuẩn: `formal/peering/tcp-fanin/`, epoch `1791293390`.
- Fan-in TGW chuẩn: `formal/tgw/tcp-fanin/`, epoch `1791296141`.
- `verification-20261005/` và `resume-20261005/`: route, readiness và smoke test, không phải benchmark bão hòa.
- Bài hai cặp Peering, bản sao trùng, log chuẩn bị và log phụ giữ để truy vết; không cộng thành thêm lượt của sáu bộ chính.

Giữ nguyên byte raw, kể cả khoảng trắng/CRLF và stderr rỗng. Không sửa raw
để làm đẹp diff. File `.gitattributes` ngăn Git tự đổi xuống dòng để SHA256
có thể kiểm tra sau clone. Bảng/chương kết quả giữ nguyên hạn chế: các mode
đo nối tiếp; fan-in theo cửa sổ riêng nên tổng vẫn là xấp xỉ; ENA không phải
tỷ lệ mất gói. Các bài mới trong kế hoạch chưa được thực hiện.
