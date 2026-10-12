"""Publication artifacts from VERIFIED raw pilot analysis, never fabricated points."""
import argparse
import datetime as dt
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    args = p.parse_args()
    analysis = json.loads((args.folder / 'analysis.json').read_text())
    assert not analysis['issues'], 'Do not render an invalid pilot as verified results'
    destination = Path(__file__).resolve().parents[2] / 'docs/images/application'
    destination.mkdir(parents=True, exist_ok=True)
    calibration = args.folder.parent.name == 'application-qos-calibration-v2'
    first = '03-calibration' if calibration else '01-pilot'
    second = '04-calibration-trace' if calibration else '02-trace-waterfall'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout='constrained')
    for mode, color in [('peering','#2876b8'),('tgw','#d07526')]:
        rows = sorted([r for r in analysis['rows'] if r['mode'] == mode], key=lambda r:r['rate_rps'])
        rates = [r['rate_rps'] for r in rows]
        axes[0].plot(rates, [r['successful_completion_p95_ms'] for r in rows], 'o-', color=color, label=mode.upper())
        axes[1].plot(rates, [100*r['deadline_success_fraction'] for r in rows], 'o-', color=color, label=mode.upper())
    axes[0].set_ylabel('P95 completion time, successful requests (ms)')
    axes[0].set_ylim(bottom=0)
    axes[1].set_ylabel('Correct and completed within 50 ms (%)')
    axes[1].set_ylim(0, 105)
    for ax in axes:
        ax.set_xlabel('Scheduled arrival rate (requests/s)')
        ax.grid(alpha=.2)
        ax.legend()
    fig.suptitle('Four-EC2 application ' + ('calibration' if calibration else 'pilot') + ' · one paired session · tracing OFF')
    fig.savefig(destination / (first+'.png'), dpi=180)
    fig.savefig(destination / (first+'.svg'))
    plt.close(fig)
    spans = [json.loads(line) for node in 'abcd'
        for line in (args.folder / 'trace-smoke' / (node+'.jsonl')).read_text().splitlines()]
    root = next(s for s in spans if s['name']=='load.request')
    selected = [s for s in spans if s['context']['trace_id']==root['context']['trace_id']]
    instant = lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
    start = instant(root['start_time'])
    selected.sort(key=lambda s:(s['resource']['attributes']['service.instance.id'], s['start_time']))
    fig, ax = plt.subplots(figsize=(10, 5.5), layout='constrained')
    colors = dict(a='#607d8b',b='#2876b8',c='#39a07d',d='#d07526')
    for index, span in enumerate(selected):
        node = span['resource']['attributes']['service.instance.id']
        left = 1000*(instant(span['start_time'])-start)
        width = 1000*(instant(span['end_time'])-instant(span['start_time']))
        ax.barh(index, width, left=left, color=colors[node], alpha=.8)
    ax.set_yticks(range(len(selected)), [s['resource']['attributes']['service.instance.id'].upper()+' · '+s['name'] for s in selected])
    ax.invert_yaxis()
    ax.set_xlabel('Time relative to root span (ms) · cross-host NTP clocks')
    ax.set_title('Real distributed trace · separate smoke run · not a network-only latency measurement')
    ax.grid(axis='x', alpha=.2)
    fig.savefig(destination / (second+'.png'), dpi=180)
    fig.savefig(destination / (second+'.svg'))
    plt.close(fig)
    print(json.dumps({'artifacts': str(destination), 'trace_id': root['context']['trace_id']}))


if __name__ == '__main__':
    main()
