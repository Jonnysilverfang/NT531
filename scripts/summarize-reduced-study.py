"""Budget-curtailed descriptive snapshot; never change raw/protocol or run AWS."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    decision_path = ROOT/'results/study-scope-decision-20261013.json'
    decision = read(decision_path)
    studies = {}
    for name, limit in decision['maximum_completed_blocks'].items():
        folder = ROOT/'results'/name
        assert sha(folder/'protocol.json') == decision['original_protocol_sha256'][name]
        analysis = read(folder/'analysis.json')
        assert not analysis['issues'] and analysis['completed_blocks'] <= limit
        assert analysis['inferential_result'] is None, 'Original confirmation cannot be declared complete'
        values = ([r['difference_ms'] for r in analysis['rows']] if name == 'confirmation-rtt-v1'
                  else [float(r['improvement'])*100 for r in analysis['rows']])
        studies[name] = dict(completed_blocks=len(values), local_dates=analysis['local_dates'],
            maximum_after_final_session=limit, analysis_sha256=sha(folder/'analysis.json'),
            quantity='TGW minus Peering RTT' if name == 'confirmation-rtt-v1' else '16 minus 8 slots deadline success',
            unit='ms' if name == 'confirmation-rtt-v1' else 'percentage points',
            mean=st.mean(values) if values else None, median=st.median(values) if values else None,
            minimum=min(values) if values else None, maximum=max(values) if values else None,
            inferential_result=None)
    lifecycle = read(ROOT/decision['final_session_lifecycle'])
    ended = 'ended_utc' in lifecycle
    slot_analysis=read(ROOT/'results/application-slots-confirmation-v1/analysis.json')
    conditions=[]
    for rate in [600,800]:
        for mode in ['peering','tgw']:
            for count in [8,16]:
                records=[next(r for r in b['rows'] if (r['rate_rps'],r['mode'],r['slots'])==(rate,mode,count)) for b in slot_analysis['rows']]
                if not records:
                    continue
                scheduled=sum(r['scheduled'] for r in records)
                deadline=sum(r['deadline_success_count'] for r in records)
                p95=[r['successful_completion_p95_ms'] for r in records]
                conditions.append(dict(mode=mode,slots=count,rate_rps=rate,blocks=len(records),
                    scheduled=scheduled,deadline_success_count=deadline,
                    observed_deadline_success_percent=100*deadline/scheduled,
                    failed=sum(r['failed'] for r in records),
                    minimum_block_successful_completion_p95_ms=min(p95),
                    maximum_block_successful_completion_p95_ms=max(p95)))
    snapshot = dict(created_local=dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).isoformat(),
        status='closed_for_budget' if ended else 'awaiting_one_final_session',
        decision_sha256=sha(decision_path), final_session_status=lifecycle['status'], studies=studies,
        slot_conditions=conditions,
        inference=None, scope='Descriptive observed blocks only; original 16-block confirmation curtailed for budget, not completed. No post-hoc confirmatory p-values.',
        no_AWS_calls=True)
    out = ROOT/'results/analysis/reduced-study-summary.json'
    out.write_text(json.dumps(snapshot, indent=2)+'\n', encoding='utf-8')
    rows = ['| Nghiên cứu | Block đã kiểm tra | Mean hiệu ứng | Median | Khoảng từng block |',
            '|---|---:|---:|---:|---:|']
    for name, s in studies.items():
        rows.append(f"| {'RTT' if name == 'confirmation-rtt-v1' else 'Slots'} | {s['completed_blocks']} | {s['mean']:.6f} {s['unit']} | {s['median']:.6f} | {s['minimum']:.6f}–{s['maximum']:.6f} {s['unit']} |")
    condition_lines=['| Mạng | Slots | rps | Request theo lịch | Đúng hạn % | Khoảng P95 từng block ms |',
        '|---|---:|---:|---:|---:|---:|']
    for r in conditions:
        condition_lines.append(f"| {r['mode'].upper()} | {r['slots']} | {r['rate_rps']} | {r['scheduled']} | {r['observed_deadline_success_percent']:.4f} | {r['minimum_block_successful_completion_p95_ms']:.3f}–{r['maximum_block_successful_completion_p95_ms']:.3f} |")
    text = '''# Phạm vi rút gọn và cách chốt kết luận

Ngày 13/10/2026, người dùng yêu cầu giảm credit và không tiếp tục yêu cầu
bốn ngày. Đây là quyết định ngân sách sau khi đã quan sát các block đầu;
không phải dừng vì p-value. Lịch thu 16 block được hủy, chỉ giữ một phiên
cuối đã xếp, tối đa RTT block 5 và slots block 3. Nếu phiên đó lỗi, giữ lỗi
và dữ liệu hợp lệ hiện có; không tự đo lại hoặc mở phiên mới.

Protocol gốc, mã ứng dụng và raw giữ nguyên để kiểm chứng. Không sửa
16 thành 5/3 hay bốn ngày thành một ngày để biến dữ liệu thành xác nhận
đạt chuẩn. Đợt xác nhận gốc được ghi là **rút ngắn vì ngân sách, chưa hoàn
thành thiết kế**; kết luận mới chỉ mô tả các block đã quan sát.

## Dữ liệu hiện có

''' + f"Snapshot {snapshot['created_local']}. Trạng thái: `{snapshot['status']}`; phiên cuối: `{lifecycle['status']}`.\n\n" + '\n'.join(rows) + '''

RTT: mỗi hiệu ứng là trung bình RTT TGW trừ trung bình RTT Peering trong
cùng block, đơn vị ms. Slots: hiệu tỷ lệ đúng hạn 16 trừ 8 slots tại
800 rps, trung bình qua hai mode, rồi nhân 100 để ra điểm phần trăm.
Mean/median/range tổng hợp các block; request hoặc probe không biến thành
block độc lập. Với rất ít block, không công bố p-value xác nhận hay CI
liên block có vẻ chính xác giả; mean và range không chứng minh hiệu ứng
đúng trong mọi ngày, mọi cấu hình hoặc mọi hệ thống AWS.

## Đồ án vẫn đóng góp gì?

- So sánh RTT và TCP trên cùng topology/cohort trong các phiên đã đo;
  tách dữ liệu lịch sử với đợt mới, giữ routes và điều kiện thí nghiệm.
- Can thiệp 8 → 16 slots cho thấy cải thiện deadline trong các phiên
  quan sát; queue/service logs, CPU/ENA hỗ trợ giải thích cơ chế.
- Kiểm tra định luật Little bằng sample path hữu hạn từ raw, có ký hiệu
  và đơn vị; đây là nhất quán toán học của log, không kiểm định độc lập.
- Giữ kiến trúc, code, raw, công thức, related work và giới hạn diễn giải
  để nhóm tái tạo và bảo vệ kết quả thực đã làm.

## Việc còn lại trong phạm vi mới

Chỉ để phiên cuối đang xếp kết thúc, kiểm chứng raw, rồi tổng hợp báo cáo,
biểu đồ và Word **một lần**. Heartbeat được đổi từ tám lần/ngày sang một
lần chốt lúc 19:00 ngày 13/10; sau bàn giao xóa heartbeat. Nếu runner còn
chạy, chỉ theo dõi đến hoàn tất, không mở nghiên cứu mới. RTT khi tải được
hoãn và không ghi là đã đo. Không thêm tool hoặc đổi workload để làm đồ án
trông lớn hơn. Người dùng tự dừng EC2; runner sao lưu và dừng workload.

Các mục 16 block/bốn ngày trong tài liệu cũ là **kế hoạch gốc đã được thay
thế**, không còn là danh sách bắt buộc phải đo tiếp. Phương pháp kiểm định
ở đó là phương pháp đã thiết kế, không phải kết quả kiểm định đạt được.

[Quyết định phạm vi](../results/study-scope-decision-20261013.json) ·
[Snapshot mô tả](../results/analysis/reduced-study-summary.json) ·
[Báo cáo tổng hợp](34-bao-cao-tong-hop.md)
'''
    pooled='## Thống kê mô tả toàn bộ request đã đo\n\n'+'\n'.join(condition_lines)+'\n\nTỷ lệ đúng hạn bằng tổng request đúng hạn chia tổng request theo lịch. Đây là tần suất thực nghiệm trong dữ liệu đã thu, không coi mọi request độc lập. Cột P95 là min–max của P95 từng block; không phải P95 gộp hoặc trung bình P95.\n\n'
    text=text.replace('## Đồ án vẫn đóng góp gì?',pooled+'## Đồ án vẫn đóng góp gì?')
    if ended:
        text=text.replace('Chỉ để phiên cuối đang xếp kết thúc, kiểm chứng raw, rồi tổng hợp báo cáo,\nbiểu đồ và Word **một lần**.',
            'Phiên đo cuối đã kết thúc; không mở phiên mới. Kiểm chứng raw và tổng hợp báo cáo,\nbiểu đồ và Word **một lần**, rồi kiểm tra trực quan và công bố bản bàn giao.')
    if lifecycle.get('report_review',{}).get('heartbeat_deleted'):
        begin=text.index('Heartbeat được đổi')
        finish=text.index('RTT khi tải được',begin)
        text=text[:begin]+'Báo cáo và Word đã qua rà soát; lịch đo tự động đã xóa sau phiên cuối. Không mở nghiên cứu mới. '+text[finish:]
    (ROOT/'docs/35-pham-vi-rut-gon-va-ket-luan.md').write_text(text, encoding='utf-8')
    print(json.dumps(snapshot))


if __name__ == '__main__':
    main()
