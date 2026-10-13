"""Read-only, descriptive sample-path accounting of validated worker calls.

All measured calls (including cancelled calls) are included, warmup excluded
by request ID. The cohort window includes its final exit, rather than clipping
unfinished calls at the 15-second arrival boundary. No new statistical test.
"""
import datetime as dt
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZERO = Decimal(0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(path):
    return [json.loads(line, parse_float=Decimal) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]


def occupancy(intervals, start, end):
    events = {start:0, end:0}
    for left, right in intervals:
        assert start <= left <= right <= end, 'Censored or invalid interval'
        events[left] = events.get(left, 0)+1
        events[right] = events.get(right, 0)-1
    previous = start; population = 0; peak = 0; area = ZERO
    for instant, change in sorted(events.items()):
        area += population*(instant-previous)
        population += change
        assert population >= 0, 'Negative occupancy'
        peak = max(peak, population); previous = instant
    assert population == 0
    total = sum((right-left for left, right in intervals), ZERO)
    assert area == total, 'Event sweep and per-call duration sums disagree'
    return area, peak


def account(calls, slots):
    assert calls and len({r['request_id'] for r in calls}) == len(calls)
    assert all(r['exit_s'] is not None and r['status'] in ['handler_completed', 'cancelled'] for r in calls)
    start = min(r['entered_s'] for r in calls); end = max(r['exit_s'] for r in calls)
    duration = end-start; assert duration > 0
    waiting = []; serving = []; lifetimes = []
    for row in calls:
        entry, exit_time = row['entered_s'], row['exit_s']
        service_start, service_end = row['service_start_s'], row['service_end_s']
        assert entry <= exit_time
        assert service_end is None or service_start is not None, 'Service end without service start'
        if service_start is not None:
            assert entry <= service_start <= exit_time, 'Service start outside handler lifetime'
        if service_end is not None:
            assert service_start <= service_end <= exit_time, 'Invalid service chronology'
        if row['status'] == 'handler_completed':
            assert service_start is not None and service_end is not None
        waiting_end = service_start if service_start is not None else exit_time
        waiting.append((entry, waiting_end)); lifetimes.append((entry, exit_time))
        if service_start is not None:
            serving.append((service_start, service_end if service_end is not None else exit_time))
    queue_area, queue_peak = occupancy(waiting, start, end)
    active_area, active_peak = occupancy(serving, start, end)
    system_area, system_peak = occupancy(lifetimes, start, end)
    assert active_peak <= slots, 'Observed service concurrency exceeds configured slots'
    assert queue_area+active_area <= system_area
    n = len(calls); rate = Decimal(n)/duration
    mean_wait = queue_area/n; mean_system = system_area/n
    # Account using independently integrated time area, not a P95 substituted for a mean.
    residual_q = queue_area/duration-rate*mean_wait
    residual_system = system_area/duration-rate*mean_system
    assert abs(residual_q) < Decimal('1e-20') and abs(residual_system) < Decimal('1e-20')
    good = [r for r in calls if r['status'] == 'handler_completed']
    mean_service = sum((r['service_end_s']-r['service_start_s'] for r in good), ZERO)/len(good) if good else None
    return dict(entered_calls=n,completed_handlers=len(good),cancelled_calls=n-len(good),
        cohort_window_seconds=float(duration),window_definition='Earliest measured worker entry to latest measured worker exit, one worker clock; tail included',
        cohort_count_rate_per_second=float(rate),mean_wait_ms=float(mean_wait*1000),mean_worker_lifetime_ms=float(mean_system*1000),
        mean_service_completed_ms=float(mean_service*1000) if mean_service is not None else None,
        mean_queue_occupancy=float(queue_area/duration),peak_queue_occupancy=queue_peak,
        mean_active_service_occupancy=float(active_area/duration),peak_active_service_occupancy=active_peak,
        mean_system_occupancy=float(system_area/duration),peak_system_occupancy=system_peak,
        cohort_service_slot_fraction=float(active_area/(slots*duration)),
        queue_area_call_seconds=str(queue_area),system_area_call_seconds=str(system_area),
        queue_identity_residual=str(residual_q),system_identity_residual=str(residual_system),
        identity_verified=True,scope='Finite fully observed call cohort, descriptive algebra; count rate is not the configured arrival rate, not a steady-state estimate or end-to-end latency')


def main():
    folders = []
    for name in ['application-slots-engineering-v1','application-slots-confirmation-v1']:
        folders.extend(p.parent for p in (ROOT/'results'/name).rglob('analysis.json') if (p.parent/'attempt.json').exists())
    results = []
    for folder in sorted(folders):
        analysis = json.loads((folder/'analysis.json').read_text(encoding='utf-8'))
        assert not analysis['issues'], 'Use only raw already validated by the primary analyzer'
        sources = {x['path']:x['sha256'] for x in analysis['sources']}
        record = json.loads((folder/'attempt.json').read_text(encoding='utf-8'))
        conditions = []
        for row in analysis['rows']:
            path = folder/row['mode']/f"slots-{row['slots']}-rate-{row['rate_rps']}"
            inputs = [path/'requests.jsonl.gz', path/'queue-c.jsonl.gz', path/'queue-d.jsonl.gz']
            proofs = []
            for file in inputs:
                relative = file.relative_to(folder).as_posix()
                digest = sha(file); assert sources[relative] == digest, 'Raw file changed after validation'
                proofs.append({'path':file.relative_to(ROOT).as_posix(), 'sha256':digest})
            requests = raw(inputs[0]); ids = {r['request_id'] for r in requests}
            assert len(ids) == len(requests)
            workers = []
            for node, file in zip('cd', inputs[1:]):
                calls = [r for r in raw(file) if r['request_id'] in ids]
                assert all(r['node']==node for r in calls)
                workers.append({'node':node,'client_requests_without_entry':len(ids)-len(calls),**account(calls, row['slots'])})
            conditions.append({'mode':row['mode'],'slots':row['slots'],'configured_arrival_rps':row['rate_rps'],
                               'workers':workers,'sources':proofs})
        results.append({'phase':record['phase'],'block':record['block'],'attempt':record['attempt'],
                        'validated_analysis_sha256':sha(folder/'analysis.json'),'conditions':conditions})
    out = ROOT/'results/analysis/queue-occupancy-audit.json'
    report = {'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'study_results':results,
              'worker_conditions':sum(2*len(r['conditions']) for r in results),
              'scope':'Descriptive secondary analysis only; no pooling phases, no additional primary test, no proof of queue stationarity or AWS capacity',
              'method':'Request-ID matched measured cohort; full monotonic entry-to-exit window; separate event sweep of waiting, service and lifetime intervals; exact Decimal area-duration agreement'}
    out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output':str(out),'worker_conditions':report['worker_conditions'],'identity_checks':'passed','AWS_calls':0}))


if __name__ == '__main__':
    main()
