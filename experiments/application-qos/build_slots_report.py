"""Write engineering report only from verified raw analysis and endpoint diagnostics."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main(folder):
    folder=folder.resolve()
    analysis=json.loads((folder/'analysis.json').read_text(encoding='utf-8'))
    assert not analysis['issues'] and analysis['phase']=='engineering_validation_excluded'
    record=json.loads((folder/'attempt.json').read_text(encoding='utf-8'))
    diagnostics=json.loads((folder/'endpoint-diagnostics.json').read_text(encoding='utf-8'))
    assert not record['cleanup_errors'] and (record['status']=='complete' or analysis['collection_recovery']['status']=='verified_download_only')
    rows=sorted(analysis['rows'],key=lambda r:(r['rate_rps'],r['mode'],r['slots']))
    rawpath=folder.relative_to(ROOT).as_posix()
    lines=['# Kết quả kiểm tra kỹ thuật can thiệp slots', '',
        'Đây là **một phiên engineering**, tách khỏi 16 block xác nhận. Dữ liệu',
        'cho thấy hiệu ứng quan sát trong phiên này; chưa có p-value hoặc CI liên',
        'block, chưa xác nhận khả năng lặp lại giữa các ngày.', '',
        f"Nguồn: [raw, source và metadata](../{rawpath}/attempt.json);",
        f"[analysis tính lại mọi request](../{rawpath}/analysis.json);",
        f"[CPU/ENA theo điều kiện](../{rawpath}/endpoint-diagnostics.json).", '',
        f"Bắt đầu UTC: `{record['started_utc']}`; kết thúc: `{record['ended_utc']}`.",
        f"Thứ tự mạng thực chạy: {' → '.join(record['schedule']['mode_order'])}.",
        f"Tổng **{sum(r['scheduled'] for r in rows):,} yêu cầu đo** (không cộng warm-up).", '',
        'A → B → C/D; hai RPC song song. MTU 1500, cùng EC2/AMI/AZ, tác vụ I/O',
        'mô phỏng 10 ms, 4096 bytes/worker. Deadline 50 ms, timeout 2 s; mỗi tổ',
        'hợp warm-up 5 s, drain backlog, đo 15 s. Tracing đầy đủ tắt; log hàng',
        'đợi bật giống nhau. Thay đồng thời số slots của C và D; fresh server',
        'mỗi tổ hợp. Giữ dữ liệu lỗi/timeout trong mẫu số.', '',
        'Thu log cuối gặp AWS OAuth 429. Dấu vết `attempt.json` failed được giữ',
        'nguyên; [download-recovery.json](../'+rawpath+'/download-recovery.json)',
        'ghi việc chỉ tải lại hai queue logs còn thiếu, không đo lại. TGW',
        'after-snapshot lấy sau cleanup đã khôi phục TGW. Các số liệu phía A',
        'và bảy tổ hợp trước không bị ghi đè. Phạm vi route snapshot này được',
        'công bố để không mô tả recovery như một phiên chạy sạch lỗi.', '',
        '## Outcome phía A', '',
        '| Mạng | Slots/worker | Yêu cầu/s | N | Đúng hạn (%) | Thành công HTTP/JSON (%) | P95 thành công (ms) |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['mode']} | {r['slots']} | {r['rate_rps']} | {r['scheduled']} | {100*r['deadline_success_fraction']:.3f} | {100*r['successful']/r['scheduled']:.3f} | {r['successful_completion_p95_ms']:.3f} |")
    lines+=['', 'P95 chỉ dùng request thành công; đúng hạn chia cho toàn bộ yêu cầu theo',
        'lịch. Thành công HTTP/JSON không tự đồng nghĩa đạt deadline.', '',
        '## Thời gian chờ và phục vụ tại worker', '',
        '| Mạng | Slots | rps | Node | Đã vào / N | P95 chờ (ms) | P95 phục vụ (ms) | A lỗi nhưng handler hoàn tất |',
        '|---|---:|---:|---|---:|---:|---:|---:|']
    for r in rows:
        for w in r['workers']:
            lines.append(f"| {r['mode']} | {r['slots']} | {r['rate_rps']} | {w['node'].upper()} | {w['entered']}/{r['scheduled']} | {w['queue_wait_p95_ms']:.4f} | {w['service_p95_ms']:.3f} | {w['client_failed_but_handler_completed']} |")
    lines+=['', 'Các mốc chờ/phục vụ lấy từ cùng đồng hồ monotonic của từng worker.',
        'Request ID ghép A, C và D; warm-up có ID riêng. Không cộng hai P95',
        'worker thành P95 end-to-end. Xem analysis để biết cancelled/missing/error',
        'và số mẫu dùng cho từng quantile; handler hoàn tất không chứng minh A đã nhận.', '',
        '## So sánh can thiệp trong phiên', '']
    for mode in ['peering','tgw']:
        before=next(r for r in rows if (r['mode'],r['slots'],r['rate_rps'])==(mode,8,800))
        after=next(r for r in rows if (r['mode'],r['slots'],r['rate_rps'])==(mode,16,800))
        lines.append(f"- {mode.upper()}, 800 rps: đúng hạn {100*before['deadline_success_fraction']:.3f}% → {100*after['deadline_success_fraction']:.3f}% (**+{100*(after['deadline_success_fraction']-before['deadline_success_fraction']):.3f} điểm phần trăm**); P95 thành công {before['successful_completion_p95_ms']:.3f} → {after['successful_completion_p95_ms']:.3f} ms.")
    lines+=['', 'Diễn giải: nếu đúng hạn tăng cùng với chờ hàng đợi giảm mà phục vụ',
        'vẫn cùng cỡ 10–11 ms, điều này hỗ trợ vai trò của giới hạn đồng thời',
        'worker trong workload đã đặt. So sánh slot trước/sau không đổi mode',
        'mạng. Cần các block với thứ tự cân bằng để tách biến động thời gian;',
        'phiên đơn này không xếp hạng mạng tổng quát hay chứng minh một nguyên',
        'nhân duy nhất. Các P95 nhỏ có thể khác giữa hai mode dù cả hai đạt SLA.', '',
        'Tỷ lệ đúng hạn đạt 100% là outcome chạm trần của ngưỡng 50 ms;',
        'không chứng minh hai mạng tương đương về latency. Trong phiên này,',
        'đổi đường mạng ở 8 slots/800 rps vẫn để phần lớn yêu cầu trễ hạn;',
        'tăng slots trong từng mode giải quyết trễ hạn quan sát được. Không',
        'tuyên bố 16 slots là cấu hình tối ưu; chỉ hai mức slots đã được thử.', '',
        '## CPU/ENA và chất lượng dữ liệu', '',
        '| Mạng | Slots | rps | CPU B trung bình (%) | Mẫu CPU B (1 s) |',
        '|---|---:|---:|---:|---:|']
    for condition in sorted(diagnostics['conditions'],key=lambda r:(r['rate_rps'],r['mode'],r['slots'])):
        b=next(h for h in condition['hosts'] if h['node']=='b')
        value=b['mean_host_non_idle_percent']
        lines.append(f"| {condition['mode']} | {condition['slots']} | {condition['rate_rps']} | {value:.3f} | {b['one_second_aggregate_samples']} |")
    ena=[value for condition in diagnostics['conditions'] for host in condition['hosts'] for value in host['ena_deltas'].values()]
    lines+=['', f"Delta năm bộ đếm allowance ENA trên cả bốn node/tám tổ hợp: **{'đều bằng 0' if set(ena)=={0} else 'xem diagnostics, có tăng hoặc missing'}**.",
        'Cửa sổ ENA gồm warm-up/drain/đo/thu log; CPU chỉ lấy các interval một',
        'giây nằm hoàn toàn trong cửa sổ client. CPU host = 100 − %idle, gồm',
        'I/O wait; không phải CPU riêng ứng dụng. Không suy ra công suất AWS',
        'vô hạn từ delta ENA bằng 0.', '',
        'Analyzer kiểm tra source/hash, thư viện bốn node, route hai đầu, đủ',
        'tám tổ hợp, generator, từng request, worker ID/timestamp và CPU/ENA.',
        '**Không có issue theo các kiểm tra trên.** Engineering chạy phiên runner',
        'được lưu cùng raw; bản formal bổ sung health-before để xác minh trực tiếp',
        'slots/queue_logging/backlog và kiểm tra thời lượng block. Không tự nhập',
        'engineering vào formal sau khi đã thấy kết quả.', '',
        '## Biểu đồ', '',
        '![Can thiệp tại 600 rps](images/application/slots-600.png)', '',
        '![Can thiệp tại 800 rps](images/application/slots-800.png)', '',
        '## Việc tiếp theo', '',
        '[Protocol slots đã khóa](27-can-thiep-slots-va-hang-doi.md) yêu cầu',
        '16 block trên ít nhất bốn ngày, cách nhau ít nhất hai giờ. Hiện phiên',
        'này đóng góp **0 block xác nhận**. Kiểm định chính cần ít nhất 12/16',
        'block có mức tăng >10 điểm phần trăm; không dừng khi vừa đạt ngưỡng.',
        'Đợt RTT chạy riêng. [Cách dừng và mở lại](28-tam-dung-va-tiep-tuc-xac-nhan.md).', '']
    out=ROOT/'docs/29-ket-qua-engineering-slots.md'
    out.write_text('\n'.join(lines),encoding='utf-8')
    print(str(out))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);main(parser.parse_args().folder)
