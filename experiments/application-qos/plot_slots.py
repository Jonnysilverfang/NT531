"""CPU/ENA diagnostics and scientific figures for an already validated slot block."""
import argparse
import datetime as dt
import gzip
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import diagnostics


def main(folder, figures):
    analysis=json.loads((folder/'analysis.json').read_text(encoding='utf-8'))
    if analysis['issues']:raise ValueError('Resolve raw validation issues before plotting')
    report={'conditions':[], 'scope':'CPU: fully contained one-second intervals in measured client window. ENA: per-condition capture including warmup and draining, not only the measured window.'}
    for row in analysis['rows']:
        path=folder/row['mode']/f"slots-{row['slots']}-rate-{row['rate_rps']}"
        run=json.loads((path/'summary.json').read_text(encoding='utf-8'))
        start,end=[dt.datetime.fromisoformat(run[k]) for k in ['started_utc','ended_utc']]
        hosts=[]
        for node in 'abcd':
            monitor=json.loads(gzip.decompress((path/f'monitor-{node}.json.gz').read_bytes()))
            before,after=[diagnostics.counters(monitor[k]) for k in ['ena-before.txt','ena-after.txt']]
            delta={k:after[k]-before[k] if k in after and k in before else None for k in diagnostics.KEYS}
            hosts.append(dict(node=node,**diagnostics.aligned_cpu(monitor['cpu.txt'],start,end),ena_deltas=delta))
        report['conditions'].append(dict(mode=row['mode'],slots=row['slots'],rate_rps=row['rate_rps'],hosts=hosts))
    (folder/'endpoint-diagnostics.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    figures.mkdir(parents=True,exist_ok=True)
    for rate in [600,800]:
        fig,axes=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
        conditions=[next(r for r in analysis['rows'] if (r['mode'],r['slots'],r['rate_rps'])==(m,s,rate)) for m in ['peering','tgw'] for s in [8,16]]
        labels=[f"{r['mode'].upper()}\n{r['slots']} slots" for r in conditions]
        colors=['#257aa9','#56a7c6','#aa5b21','#e0a553']
        metrics=[([r['deadline_success_fraction']*100 for r in conditions], 'Completed within 50 ms (%)'),
            ([r['successful_completion_p95_ms'] for r in conditions], 'Client P95, successes only (ms)'),
            ([max(w['queue_wait_p95_ms'] for w in r['workers']) for r in conditions], 'Larger of C/D queue-wait P95 (ms)')]
        for ax,(values,title) in zip(axes,metrics):
            ax.bar(labels,values,color=colors)
            for i,v in enumerate(values):ax.text(i,v,f'{v:.2f}',ha='center',va='bottom',fontsize=9)
            ax.set_title(title,fontsize=10);ax.grid(axis='y',alpha=.25);ax.set_axisbelow(True)
            ax.set_ylim(0,110 if title.endswith('(%)') else max(1,max(values))*1.22)
        phase='engineering validation' if analysis['phase']=='engineering_validation_excluded' else 'confirmation block'
        fig.suptitle(f'{rate} requests/s — single {phase}, no inferential CI',fontsize=12)
        for ext in ['png','svg']:fig.savefig(figures/f'slots-{rate}.{ext}',dpi=180)
        plt.close(fig)
    print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--figures',type=Path,required=True)
    args=parser.parse_args();main(args.folder,args.figures)
