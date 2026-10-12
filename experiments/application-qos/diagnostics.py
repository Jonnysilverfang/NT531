"""Align 1-second UTC host CPU records with measured request window.

ENA counters cover the WHOLE mode capture, not individual rate conditions.
"""
import argparse
import datetime as dt
import gzip
import json
from pathlib import Path
import re
import statistics

KEYS = ['bw_in_allowance_exceeded','bw_out_allowance_exceeded','pps_allowance_exceeded',
    'conntrack_allowance_exceeded','linklocal_allowance_exceeded']


def counters(text):
    return {name:int(value) for name,value in re.findall(r'^\s*(\w+):\s*(\d+)\s*$',text,re.M)}


def aligned_cpu(text, start, end):
    rows = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 12 or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', fields[0]) or fields[1] not in ['all','0','1']:
            continue
        candidates = [dt.datetime.combine(start.date()+dt.timedelta(days=d), dt.time.fromisoformat(fields[0]), tzinfo=dt.timezone.utc) for d in [-1,0,1]]
        stamp = min(candidates, key=lambda s:abs((s-start).total_seconds()))
        # A row reports the preceding second: use only fully contained intervals.
        if start <= stamp-dt.timedelta(seconds=1) and stamp <= end:
            rows.append({'cpu':fields[1], 'non_idle_percent':100-float(fields[-1])})
    aggregate = [r['non_idle_percent'] for r in rows if r['cpu']=='all']
    cores = [r['non_idle_percent'] for r in rows if r['cpu']!='all']
    return {'one_second_aggregate_samples':len(aggregate),
        'mean_host_non_idle_percent':statistics.mean(aggregate) if aggregate else None,
        'peak_logical_cpu_non_idle_percent':max(cores) if cores else None,
        'metric':'100 - %idle; includes I/O wait; host-level, not application-only'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    args = p.parse_args()
    record = json.loads((args.folder/'attempt.json').read_text(encoding='utf-8'))
    result = {'cpu_windows':[], 'ena_by_mode':[],
        'ena_scope':'Whole mode including warmup, load, waits and downloads; not per rate',
        'interpretation':'No change in allowance counters is not proof of unlimited network capacity; CPU/ENA do not isolate the cause of application latency.'}
    for mode in record['order']:
        for node in 'abcd':
            monitor = json.loads(gzip.decompress((args.folder/mode/f'monitor-{node}.json.gz').read_bytes()))
            before,after = counters(monitor['ena-before.txt']),counters(monitor['ena-after.txt'])
            delta = {key:after[key]-before[key] if key in before and key in after else None for key in KEYS}
            result['ena_by_mode'].append({'mode':mode,'node':node,'counter_deltas':delta})
            for run in record['runs']:
                if run['mode'] != mode:
                    continue
                start,end = [dt.datetime.fromisoformat(run[k]) for k in ['started_utc','ended_utc']]
                result['cpu_windows'].append({'mode':mode,'node':node,'rate_rps':run['rate_rps'],
                    'start_utc':start.isoformat(),'end_utc':end.isoformat(), **aligned_cpu(monitor['cpu.txt'],start,end)})
    (args.folder/'endpoint-diagnostics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'ENA':result['ena_by_mode'], 'CPU_B':[r for r in result['cpu_windows'] if r['node']=='b']}))


if __name__=='__main__':
    main()
