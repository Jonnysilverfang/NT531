# Báo cáo readiness Mode B

## Kết luận hiện tại

**OFFLINE FRAMEWORK GATE: PASS sau khi chạy quality gate. AWS EXECUTION: CHƯA XÁC MINH.**

Repo có framework thu thập và phân tích Mode B, nhưng chưa có bằng chứng `terraform apply`, AWS preflight, pilot hay final run trong checkout. Vì vậy không được gọi trạng thái hiện tại là “AWS ready” hoặc “empirical study complete”.

## Các điểm đã khóa trong mã nguồn

- TC-04 tính tổng CPU busy và SoftIRQ từ delta hai snapshot `/proc/stat` trong cùng measurement window.
- Saturation evaluator fail-closed khi thiếu probe, CPU delta hoặc iperf3 sender summary.
- Target PPS và achieved PPS là hai trường riêng; achieved PPS lấy từ số packet/thời lượng sender thực tế.
- Analyzer Mode B có bốn nhánh `analyze_tc01()` đến `analyze_tc04()` và một schema `mode_b_summary.json` thống nhất.
- Analyzer từ chối checksum sai, thiếu run/cell, config drift, TC-03 khác backend và chuỗi TC-04 không phải prefix hợp lệ đến saturation.
- Mode B dùng `paired_run_level_bootstrap`. Repo không gọi đây là hierarchical bootstrap vì artifact Mode B hiện chỉ có summary theo run.
- TC-01 ghi host/path assignment. Với topology hai backend hiện tại, claim bị giới hạn ở association có điều kiện theo host assignment.
- Local emulation được gắn `empirical=false`; analyzer empirical không chấp nhận nó.

## Gate còn mở

- [ ] Quyết định thiết kế causal cho TC-01: cùng backend hoặc crossover host-path cân bằng.
- [ ] Tách TC-03F functional validation khỏi TC-03P performance nếu phần overlapping CIDR được đưa vào báo cáo.
- [ ] `terraform validate` và plan-only phải PASS trong môi trường có Terraform/Bash phù hợp.
- [ ] AWS preflight phải PASS trên inventory thật.
- [ ] Pilot N=3 phải hoàn tất, checksum và completeness gate PASS.
- [ ] Final N≥10 phải hoàn tất trước kết luận empirical.
- [ ] Báo cáo/biểu đồ Mode B phải được sinh lại từ artifact đã niêm phong.

## Lệnh kiểm tra offline

```bash
uv run --no-cache --python 3.12 python scripts/run_quality_gate.py
bash scripts/benchmark_runner.sh --plan-only --profile final --experiment-id review-final
```

Hai lệnh này không deploy AWS. Không chạy `terraform apply` hoặc `--execute` trong phạm vi audit offline.
