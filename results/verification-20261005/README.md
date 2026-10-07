# Bằng chứng kiểm tra hạ tầng — 05/10/2026

Các file ở đây là kiểm tra chức năng, **không phải benchmark hiệu năng chính thức**.

- `peering.txt`, `tgw.txt`: kiểm tra ban đầu sau setup.
- `readiness.json`: cả bốn máy cùng iperf3 3.19.1, kernel/ENA, MTU 1500,
  NTP đồng bộ và ba service active.
- `peering-mtu1500.txt`, `tgw-mtu1500.txt`: kiểm tra cuối sau chuẩn hóa MTU;
  mỗi chế độ 12 ping PASS, 36 TCP PASS, 12 IPERF PASS, 0 FAIL.
- `peering-routes.json`, `tgw-routes.json`: route AWS thu lúc từng mode đang active.

Smoke test giới hạn 1 Mbit/s trong 2 giây. Không dùng tốc độ smoke test để so sánh
hiệu năng Peering/TGW. Trạng thái bàn giao: Peering, EC2 đang chạy, TGW còn tồn tại.
