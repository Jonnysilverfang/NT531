"""Prepare a local NT531 teaching dashboard from preserved results and traces.

No AWS operations, new measurement, timestamp rebasing or fabricated metrics.
Use --replay to send preserved smoke spans to the local Collector and verify
the provisioned dashboard/trace search through the Grafana datasource proxy.
"""
import argparse
import base64
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    'results/application-qos-pilot-v1/ad93e8d202154733a165eee896fd5e50/trace-smoke',
    'results/application-qos-calibration-v2/1c0d1fb25e544fb0bee95078cbfc265c/trace-smoke',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def text_panel(identifier, title, content, y, height):
    return dict(id=identifier, type='text', title=title,
                gridPos=dict(x=0, y=y, w=24, h=height),
                options=dict(mode='markdown', content=content))


def prepare():
    summary_path = 'results/analysis/reduced-study-summary.json'
    queue_path = 'results/analysis/queue-occupancy-audit.json'
    summary = read_json(summary_path)
    queue = read_json(queue_path)
    assert summary['status'] == 'closed_for_budget' and summary['inference'] is None
    proof = [dict(path=p, sha256=sha(ROOT / p)) for p in [summary_path, queue_path]]
    for path in ['monitoring/compose.yaml', 'monitoring/tempo.yaml',
                 'monitoring/collector-gateway.yaml',
                 'monitoring/grafana/provisioning/datasources/tempo.yaml',
                 'experiments/application-qos/replay_traces.py']:
        proof.append(dict(path=path, sha256=sha(ROOT / path)))
    for study in summary['studies'].values():
        name = ('confirmation-rtt-v1' if study['unit'] == 'ms'
                else 'application-slots-confirmation-v1')
        path = f'results/{name}/analysis.json'
        assert sha(ROOT / path) == study['analysis_sha256']
        proof.append(dict(path=path, sha256=sha(ROOT / path)))
    spans = []
    for folder in SOURCES:
        for node in 'abcd':
            path = ROOT / folder / f'{node}.jsonl'
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            spans.extend(rows)
            proof.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path)))
    traces = {}
    for span in spans:
        identifier = span['context']['trace_id'].removeprefix('0x')
        traces.setdefault(identifier, []).append(span)
    assert len(spans) == 120 and len(traces) == 12
    for rows in traces.values():
        assert len(rows) == 10
        ids = {row['context']['span_id'] for row in rows}
        assert len(ids) == 10
        assert sum(row['parent_id'] is None for row in rows) == 1
        assert all(row['parent_id'] in ids for row in rows if row['parent_id'])
        assert {row['resource']['attributes']['service.instance.id'] for row in rows} == set('abcd')
    earliest = min(dt.datetime.fromisoformat(row['start_time'].replace('Z', '+00:00')) for row in spans)
    latest = max(dt.datetime.fromisoformat(row['end_time'].replace('Z', '+00:00')) for row in spans)
    start = int(earliest.timestamp()) - 60
    end = int(latest.timestamp()) + 60
    observed = ['| Đường mạng | Slots | Đúng hạn / theo lịch | Đúng hạn ≤ 50 ms | P95 từng block (ms) |',
                '|---|---:|---:|---:|---:|']
    for row in summary['slot_conditions']:
        if row['rate_rps'] == 800:
            observed.append(
                f"| {row['mode']} | {row['slots']} | {row['deadline_success_count']:,} / {row['scheduled']:,} "
                f"| {row['observed_deadline_success_percent']:.3f}% "
                f"| {row['minimum_block_successful_completion_p95_ms']:.3f}–"
                f"{row['maximum_block_successful_completion_p95_ms']:.3f} |")
    rtt = summary['studies']['confirmation-rtt-v1']
    effect = summary['studies']['application-slots-confirmation-v1']
    observed.extend([
        '', f"RTT: **{rtt['completed_blocks']} block**, TGW − Peering trung bình **{rtt['mean']:.4f} ms**.",
        f"Ứng dụng: **{effect['completed_blocks']} block**; 8 → 16 slots tại 800 rps tăng đúng hạn trung bình "
        f"**{effect['mean']:.4f} điểm phần trăm** qua hai mode.",
        '', '**Snapshot từ raw đã chốt; không phải số liệu live.** Khoảng P95 là min–max giữa các block, '
        'không phải khoảng tin cậy hay P95 gộp. Thiết kế 16 block đã rút gọn vì ngân sách; '
        'kết luận mô tả trong cấu hình thử nghiệm, không có p-value xác nhận.',
    ])
    study = next(row for row in queue['study_results']
                 if row['phase'] == 'confirmatory_block' and row['block'] == 3)
    condition = next(row for row in study['conditions']
                     if row['mode'] == 'peering' and row['slots'] == 8
                     and row['configured_arrival_rps'] == 800)
    worker = next(row for row in condition['workers'] if row['node'] == 'c')
    assert worker['identity_verified']
    for source in condition['sources']:
        assert sha(ROOT / source['path']) == source['sha256']
        proof.append(dict(path=source['path'], sha256=source['sha256']))
    product = worker['cohort_count_rate_per_second'] * worker['mean_wait_ms'] / 1000
    assert abs(product - worker['mean_queue_occupancy']) < 1e-8
    little = ("**Lq = λ × Wq** — Arrival Processes and Queuing Systems, trang 62–66.\n\n"
              "Lq: số lời gọi chờ trung bình; λ: lời gọi/s; Wq: thời gian chờ trung bình, giây.\n\n"
              f"Worker C, Peering, 8 slots, cấu hình 800 rps, block 3: **"
              f"{worker['cohort_count_rate_per_second']:.3f} × {worker['mean_wait_ms']/1000:.6f} "
              f"= {worker['mean_queue_occupancy']:.3f} lời gọi chờ**.\n\n"
              "Cửa sổ gồm toàn bộ đuôi xử lý của cùng nhóm request ID trên một worker. "
              "λ tính từ số lời gọi / thời lượng cửa sổ đó, khác 800 rps cấu hình. "
              "Đây là quan hệ kiểm tra sổ ghi hàng đợi ứng dụng; không đo hàng đợi TGW, "
              "không cần giả định Poisson và không dùng P95 thay cho Wq.")
    trace_panel = dict(id=4, type='table', title='12 trace thật · chọn Trace ID để xem 10 span',
                       gridPos=dict(x=0, y=24, w=24, h=11),
                       datasource=dict(type='tempo', uid='nt531-tempo'),
                       targets=[dict(refId='A', queryType='traceql',
                                     query='{ resource.service.name = "nt531-load" }',
                                     limit=20, tableType='traces', filters=[])],
                       options=dict(showHeader=True))
    panels = [
        text_panel(1, 'Demo NT531 · kết quả và hành trình yêu cầu',
                   "**A tạo yêu cầu → B gọi C và D song song → trả kết quả về A.**\n\n"
                   "Bảng bên dưới là kết quả đã chốt; trace là từ hai phiên smoke thật, nhập lại "
                   "giữ nguyên thời gian/ID. Smoke minh họa luồng gọi, không chứng minh hàng đợi khi tải 800 rps. "
                   "Hostmetrics EC2 chưa bật.\n\n"
                   "Đối chiếu slide: QoS trang 26 (SLI), 34 (trace), 39 (stack), 41–42 (phân vị). "
                   "Tracing đã tắt trong phép đo chính.", 0, 5),
        text_panel(2, '800 yêu cầu/s · hiệu ứng mạng và khả năng phục vụ', '\n'.join(observed), 5, 12),
        text_panel(3, 'Little · thế số từ log đã đo', little, 17, 7),
        trace_panel,
    ]
    dashboard = dict(uid='nt531-study-demo', title='NT531 · Kết quả và công thức trong bài giảng',
                     schemaVersion=41, version=1, tags=['NT531', 'teaching-demo', 'saved-results'],
                     timezone='utc', refresh='', editable=False,
                     time={'from': dt.datetime.fromtimestamp(start, dt.timezone.utc).isoformat(),
                           'to': dt.datetime.fromtimestamp(end, dt.timezone.utc).isoformat()}, panels=panels)
    target = ROOT / 'monitoring/grafana/dashboards/nt531-study-demo.json'
    target.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    url = ('http://localhost:3000/d/nt531-study-demo?'
           + urllib.parse.urlencode(dict(**{'from': start * 1000}, to=end * 1000)))
    proof.append(dict(path=target.relative_to(ROOT).as_posix(), sha256=sha(target)))
    return spans, traces, start, end, url, proof


def verify(spans, traces, start, end):
    config = {}
    for line in (ROOT / 'monitoring/.env').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            config[key] = value.strip()
    auth = base64.b64encode(('nt531:' + config['GRAFANA_ADMIN_PASSWORD']).encode()).decode()

    def get(path):
        request = urllib.request.Request('http://127.0.0.1:3000' + path,
                                         headers={'Authorization': 'Basic ' + auth})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    module_path = ROOT / 'experiments/application-qos/replay_traces.py'
    spec = importlib.util.spec_from_file_location('nt531_replay', module_path)
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    grouped = {}
    for span in spans:
        resource = json.dumps(span['resource']['attributes'], sort_keys=True)
        grouped.setdefault(resource, []).append(replay.convert(span))
    payload = dict(resourceSpans=[dict(resource=dict(attributes=replay.attributes(json.loads(resource))),
                                     scopeSpans=[dict(scope=dict(name='nt531.application-qos', version='1.0'),
                                                      spans=rows)]) for resource, rows in grouped.items()])
    request = urllib.request.Request('http://127.0.0.1:4318/v1/traces', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        reply = json.load(response)
    assert not reply.get('partialSuccess', {}).get('rejectedSpans', 0), 'Collector rejected spans'
    query = '{ resource.service.name = "nt531-load" }'
    search_path = '/api/datasources/proxy/uid/nt531-tempo/api/search?' + urllib.parse.urlencode(
        dict(q=query, start=start, end=end, limit=50))
    deadline = time.monotonic() + 75
    while True:
        try:
            search = get(search_path)
            dashboard = get('/api/dashboards/uid/nt531-study-demo')
            # Tempo search may omit a leading zero in hexadecimal trace IDs.
            if set(traces) <= {row['traceID'].zfill(32) for row in search.get('traces', [])}:
                break
        except urllib.error.HTTPError as error:
            if error.code not in [404, 502, 503]:
                raise
        if time.monotonic() >= deadline:
            raise TimeoutError('Preserved traces or provisioned dashboard not ready')
        time.sleep(3)
    assert dashboard['dashboard']['uid'] == 'nt531-study-demo'
    counts = {}
    for identifier in sorted(traces):
        trace = get('/api/datasources/proxy/uid/nt531-tempo/api/traces/' + identifier)
        scopes = [scope for batch in trace.get('batches', trace.get('resourceSpans', []))
                  for scope in batch.get('scopeSpans', [])]
        received = [span for scope in scopes for span in scope.get('spans', [])]
        ids = [span['spanId'] for span in received]
        assert len(ids) == len(set(ids)) == 10, (identifier, len(ids))
        counts[identifier] = len(ids)
    with urllib.request.urlopen('http://127.0.0.1:19090/api/v1/query?' + urllib.parse.urlencode(
            dict(query='system_cpu_time{nt531_phase="observability-demo"}')), timeout=10) as response:
        metrics = json.load(response)
    assert metrics['status'] == 'success'
    return dict(pipeline_verified=True, dashboard_uid='nt531-study-demo',
                traces_found=len(traces), spans_by_trace=counts, unique_spans_verified=sum(counts.values()),
                original_ids_timestamps_preserved=True, not_live_measurement=True,
                hostmetrics_series_now=len(metrics['data']['result']),
                hostmetrics_agents_installed=False, local_prometheus_port=19090)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    spans, traces, start, end, url, proof = prepare()
    result = dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(), no_AWS_calls=True,
                  traces_in_saved_sources=len(traces), spans_in_saved_sources=len(spans),
                  trace_window_utc=dict(start=start, end=end), dashboard_url=url, sources=proof,
                  primary_results_unchanged=True, runtime_verified=False)
    if args.replay:
        result.update(verify(spans, traces, start, end))
        result['runtime_verified'] = True
    # No edits to the original smoke proof or frozen raw files.
    out = ROOT / 'results/observability-demo/current-demo.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in [
        'runtime_verified', 'traces_in_saved_sources', 'spans_in_saved_sources', 'dashboard_url', 'no_AWS_calls']}))


if __name__ == '__main__':
    main()
