# Tóm tắt hardening Mode B

## Thay đổi chính

1. `scripts/calculate_softirq_delta.py`
   - Tính CPU busy bằng delta total/idle/iowait jiffies.
   - Giữ SoftIRQ delta và thêm validation cho counter reset.

2. `scripts/evaluate_saturation.py`
   - Parse legitimate-flow loss/P99, CPU delta và achieved sender PPS.
   - Fail-closed khi evidence thiếu hoặc sai schema.

3. `scripts/analyze_mode_b.py`
   - Phân tích đầy đủ TC-01, TC-02, TC-03 và TC-04.
   - Kiểm tra checksum coverage, run count, config drift và design-cell completeness.
   - Xuất schema thống nhất `mode_b_summary.json`.
   - Dùng đúng tên `paired_run_level_bootstrap`; không overclaim hierarchical bootstrap.

4. Runner và provenance
   - Manifest lưu target identity/path cho TC-01 và TC-03.
   - TC-03 bắt buộc direct/PrivateLink cùng backend khi phân tích.
   - Local emulation được phân biệt với empirical AWS.

5. Tests và tài liệu
   - Thêm fixture positive/negative cho saturation và analyzer Mode B.
   - Sửa contract test SSM theo cấu trúc module hiện tại.
   - README/protocol/readiness report giới hạn đúng claim TC-01 và trạng thái chưa có AWS evidence.

## Trạng thái bằng chứng

- Mode A: synthetic reference, reproducible, không phải AWS telemetry.
- Mode B framework: có thể kiểm tra offline bằng quality gate.
- Mode B empirical results: chưa tồn tại trong repo.
- AWS deployment/readiness: chưa được xác minh trong phạm vi này.

Không có tài nguyên AWS nào được tạo hoặc thay đổi trong đợt hardening này.
