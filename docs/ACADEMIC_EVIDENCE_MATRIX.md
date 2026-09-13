# Ma trận Bằng chứng Học thuật và Kỹ thuật

## 1. Phạm vi xác nhận

Hồ sơ hiện ở **Chế độ A – Calibrated Synthetic Reference Benchmark & Methodology Prototype**. Quality gate ngoại tuyến chứng minh tính toàn vẹn dữ liệu, tính đúng đắn của pipeline, các invariant kiến trúc trong mã và khả năng tái lập kết quả. Nó **không** chứng minh tài nguyên đã được triển khai hoặc các con số đã được đo trực tiếp trên AWS.

Ba mức bằng chứng được sử dụng:

- **A1 – Static contract**: được xác nhận từ mã nguồn/cấu hình.
- **A2 – Offline executable evidence**: được kiểm tra bằng automated test hoặc pipeline trên dataset Chế độ A.
- **B – Live AWS evidence required**: chỉ được xác nhận sau khi chạy protocol Chế độ B; hiện không tuyên bố đã đạt.

## 2. Ma trận truy xuất tuyên bố → bằng chứng

| Tuyên bố | Mức | Bằng chứng có thẩm quyền | Negative gate | Giới hạn |
|---|---|---|---|---|
| Raw Chế độ A tái tạo được từ recipe | A2 | `generate_reference_dataset.py`; seed riêng TC-01..04; model parameters trong manifest | Generator từ chối overwrite ngầm; quality gate so sánh cả năm SHA256 | Tham số là giả định minh họa, không fitted từ AWS telemetry |
| Năm raw files không bị thay đổi | A2 | `results/raw/checksums.sha256`; `verify_checksum_manifest()` | Thiếu entry hoặc hash mismatch làm pipeline thất bại | Không chứng minh nguồn AWS của dữ liệu |
| TC-01 có 6.000 observations cân bằng | A2 | `validate_raw_dataset()`; `RawSemanticValidationTests` | Timestamp trùng, sequence thiếu/trùng, path/run sai bị từ chối | Dataset là synthetic reference |
| TC-02/03/04 đúng schema và miền giá trị | A2 | `validate_raw_dataset()` | Run/second thiếu, metric ngoài miền, P99<P50 bị từ chối | Không thay thế raw stdout của công cụ Chế độ B |
| Hiệu ứng chính TC-01..04 dùng independent run | A2 | Các trường `hierarchical_*_effect` và `run_level_results` trong summary | Test bootstrap kiểm tra ghép cặp run và dấu effect | N=3 chỉ là pilot; Welch gộp là exploratory |
| Bootstrap tái lập được | A2 | Seed 42, 10.000 resamples, quality gate so sánh toàn bộ summary | Summary sinh lại khác repository → gate fail | Không loại bỏ hạn chế của synthetic model |
| P-value không được biểu diễn bằng 0 | A2 | `student_t_two_sided_p_value()` | Underflow test yêu cầu `p_value=null`, `<1e-300` | Không biến p-value thành bằng chứng thực tiễn |
| SoftIRQ delta dùng đúng công thức | A2 | `calculate_softirq_delta.py`; positive/negative tests | Sai identity, duration, counter reset → fail | Chưa có snapshot live AWS trong repository |
| TC-04 điều khiển DUT qua SSM mặc định | A1 | `benchmark_runner.sh`: default `aws-remote`, bắt buộc instance ID/CLI | Không có điều kiện → exit; local mode phải explicit | Chưa gọi SSM trong audit ngoại tuyến |
| SSM command có audit trail | A1 | Invocation/stdout/stderr/metadata artifacts theo command ID | ResponseCode khác 0 → fail | Artifact chỉ xuất hiện khi Chế độ B chạy |
| Snapshot được vận chuyển DUT → controller | A1 | Sentinel JSON + `get-command-invocation` parser | Thiếu marker/file rỗng → fail | Chưa có live artifact để xác minh end-to-end |
| XDP bắt buộc native/driver hook | A1 | Positive native regex; reject generic; mandatory `bpftool net` | Generic, thiếu attachment/dependency → fail | Native support thực tế phụ thuộc ENA/kernel/MTU |
| Hai BPF maps bắt buộc tồn tại | A1 | `xdp_config_map`, `xdp_stats_map` trong C và DUT verifier | Thiếu một map → fail | Map counters cần live dump ở Chế độ B |
| Exporter không che giấu lỗi nguồn | A2 | `validate_stats_schema()` và HTTP 503 path | Thiếu nested field → schema test fail | Dashboard là replay của reference summary |
| Dashboard không phải production telemetry | A1/A2 | Watermark, `data_source="synthetic_calibrated_reference"` | Contract test kiểm tra Mode A title/label | Không dùng để kết luận SLA production |
| B1/B2 giảm thiểu confounding đã nhận diện | A1 | Terraform: cùng AZ-a/type/SG, không PG | Static architecture review | Không thể loại bỏ noisy-neighbor và host variance |

## 3. Quality gate tái lập

Từ thư mục gốc dự án:

```powershell
uv run --no-cache --python 3.12 python scripts/run_quality_gate.py
```

Quality gate chỉ được coi là đạt khi:

1. Toàn bộ positive và negative tests thành công.
2. Dashboard JSON parse thành công.
3. Recipe sinh lại đúng SHA256 của cả năm raw files.
4. SHA256 manifest của đúng năm raw files hợp lệ.
5. Raw schema/semantic invariants hợp lệ.
6. Pipeline chạy 10.000 hierarchical bootstrap với seed cố định.
7. Summary sinh lại bằng toàn bộ JSON đang lưu trong repository.

## 4. Bằng chứng bắt buộc khi chuyển sang Chế độ B

Không được đổi nhãn sang empirical nếu chưa có đủ:

- Terraform plan/validate và inventory tài nguyên thực tế.
- SSM invocation JSON, stdout, stderr, ResponseCode cho từng action.
- `ip -details link`, `bpftool net show`, `bpftool map show/dump` từ DUT.
- Snapshot before/after và SoftIRQ delta cho từng condition/run.
- Raw `sockperf`, `iperf3`, `ethtool -S` không chỉnh sửa.
- Manifest AMI/kernel/ENA/instance/AZ/interface cùng SHA256.
- Tối thiểu 10–30 randomized crossover runs cho kết luận production.

Thiếu bất kỳ nhóm bằng chứng nào ở trên thì kết quả vẫn phải giữ nhãn **Methodology Prototype**, không được trình bày như live AWS benchmark.
