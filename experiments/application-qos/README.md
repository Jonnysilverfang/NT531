# Thí nghiệm ứng dụng NT531

Đọc [kiến trúc, công thức và phạm vi kết luận](../../docs/25-ung-dung-phan-tan-va-qos.md).
Kết quả đã chạy nằm ở [báo cáo hai phiên](../../docs/26-ket-qua-pilot-ung-dung.md);
[study-plan.md](study-plan.md) dẫn tới [thiết kế can thiệp slots đã khóa](../../docs/27-can-thiep-slots-va-hang-doi.md).

- `app.py`: A tạo yêu cầu open-loop; B fan-out HTTP; C/D worker I/O tổng hợp.
- `pilot.json`: tải, thời lượng và ngân sách đặt trước đợt thăm dò đầu tiên.
- `calibration.json`: phiên tải cao riêng, giữ workload/deadline; không gộp
  vào pilot hay nghiên cứu xác nhận.
- `test_app.py`: kiểm tra lỗi/timeout không biến mất khỏi mẫu số, hai RPC
  thực sự chồng nhau, quá tải làm tăng thời gian chờ, trace cha/con qua bốn vai trò.
- `analyze.py`: tính lại từ mọi request, kiểm tra route, package, hash, CPU/ENA
  và 6 trace hoàn chỉnh; không tính p-value cho pilot.
- `replay_traces.py`: nhập lại span thật vào Collector local, timestamp gốc.
- `verify_observability.py`: kiểm tra trace và dashboard qua Grafana proxy,
  đọc mật khẩu local từ file `.env` đã ignore, không ghi vào bằng chứng.
- `diagnostics.py`: căn cửa sổ CPU theo UTC, delta ENA toàn mode.
- `plot_pilot.py`: hai hình báo cáo từ analysis đã kiểm tra.
- `analyze_slots.py`: ghép request ID với log hàng đợi C/D; chỉ suy luận sau
  đủ 16 block hợp lệ. Dữ liệu engineering tách riêng, không nhập nghiên cứu.
- `plot_slots.py`: CPU theo cửa sổ UTC, delta ENA từng điều kiện và biểu đồ slots.
- `test_slots.py`: kiểm tra biên kiểm định exact và không kết luận sớm.
- `requirements.txt`: môi trường runtime ghim thư viện chính; `pip freeze`
  bốn máy được so sánh và lưu để biết mọi phiên bản phụ thuộc đã thực dùng.

```powershell
py -m venv tmp/application-venv
tmp/application-venv/Scripts/python.exe -m pip install -r experiments/application-qos/requirements.txt
tmp/application-venv/Scripts/python.exe experiments/application-qos/test_app.py
py scripts/application-qos.py setup
py scripts/application-qos.py pilot
```

`setup` chỉ thêm ba rule HTTP /32 và cài venv trên EC2 đang có; MTU được đặt
1500. Dịch vụ không tự bật theo boot; `pilot` dừng chúng và khôi phục route
ban đầu. `py scripts/application-qos.py stop` dùng khi cần tắt sau ngắt kết nối.
Logs/raw giữ cả lần lỗi; không tự lặp vì kết quả xấu.
