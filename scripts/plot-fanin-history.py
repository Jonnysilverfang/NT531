"""Sender interval diagnostics from the 30 existing fan-in JSONs, not new trials."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    audit_path = ROOT / 'results/analysis/fanin-common-window-audit.json'
    audit = json.loads(audit_path.read_text())
    assert audit['files'] == 30 and not audit['receiver_interval_byte_timestamps_available']
    out = ROOT / 'docs/images/application/historical-fanin'
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for mode in ['peering', 'tgw']:
        fig, axes = plt.subplots(5, 3, figsize=(12, 13), layout='constrained')
        for run in range(1, 6):
            for node, color in zip('ACD', ['#257aa9', '#bd5f25', '#674b97']):
                source = next(s for s in audit['sources'] if s['mode'] == mode
                              and f'/tcp-fanin/{node}/' in s['path'] and s['path'].endswith(f'/run-{run}.json'))
                path = ROOT / source['path']; assert sha(path) == source['sha256']
                raw = json.loads(path.read_text(encoding='utf-8-sig'))
                assert raw['start']['test_start']['num_streams'] == 1
                intervals = [i for i in raw['intervals'] if not i['sum']['omitted']]
                assert intervals and all(i['sum']['sender'] and len(i['streams']) == 1 for i in intervals)
                times = [(i['sum']['start'] + i['sum']['end']) / 2 for i in intervals]
                values = [[i['sum']['bits_per_second'] / 1e9 for i in intervals],
                          [i['streams'][0]['rtt'] / 1000 for i in intervals],
                          [i['sum']['retransmits'] / i['sum']['seconds'] for i in intervals]]
                for col, data in enumerate(values):
                    axes[run - 1, col].plot(times, data, color=color, label=node, linewidth=1.4)
                records.append(dict(path=source['path'], sha256=source['sha256'], mode=mode, run=run, node=node,
                                    sender_intervals=len(intervals), omitted_intervals=len(raw['intervals']) - len(intervals),
                                    plotted_retransmit_count=sum(i['sum']['retransmits'] for i in intervals),
                                    sender_summary_retransmits=raw['end']['sum_sent']['retransmits'],
                                    receiver_run_goodput_Gbps=raw['end']['sum_received']['bits_per_second'] / 1e9))
            for col, label in enumerate(['Sender payload Gbps', 'Sender TCP RTT ms', 'Retransmits per second']):
                ax = axes[run - 1, col]
                ax.set_title(f'Run {run}: {label}', fontsize=10)
                ax.set_xlabel('Own iperf elapsed seconds after omit reset', fontsize=9)
                ax.grid(alpha=.2); ax.set_ylim(bottom=0); ax.legend(fontsize=8, ncol=3)
                ax.tick_params(labelsize=9)
        fig.suptitle(f'{mode.upper()} historical TCP fan-in, A/C/D to B\nSender diagnostics, warm-up omitted; separate clocks/windows, not aligned receiver goodput', fontsize=12)
        for suffix in ['png', 'svg']:
            file = out / f'{mode}-sender-intervals.{suffix}'
            fig.savefig(file, dpi=180)
            if suffix == 'svg':
                file.write_text('\n'.join(line.rstrip() for line in file.read_text().splitlines()) + '\n', encoding='utf-8')
        plt.close(fig)
    proof = dict(files=len(records), source_audit_sha256=sha(audit_path),
                 total_non_omitted_sender_intervals=sum(r['sender_intervals'] for r in records),
                 sender_retransmit_sums_match_summaries=all(r['plotted_retransmit_count'] == r['sender_summary_retransmits'] for r in records),
                 scope='Historical descriptive sender diagnostics only. Separate source elapsed clocks, no interval-aligned receiver total or new statistical samples.',
                 sources=records, figures=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in sorted(out.glob('*'))])
    (ROOT / 'results/analysis/fanin-sender-interval-figures.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in proof.items() if k not in ['sources', 'figures']}))


if __name__ == '__main__':
    main()
