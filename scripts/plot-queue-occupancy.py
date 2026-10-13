"""Time-averaged measured-cohort queue curves, 100ms bins, one formal block."""
from decimal import Decimal as D
import importlib.util
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('queue_audit',ROOT/'scripts/audit-queue-occupancy.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def bins(calls,step=D('.1')):
    start=min(r['entered_s'] for r in calls);end=max(r['exit_s'] for r in calls)
    events={start:0,end:0}
    for r in calls:
        right=r['service_start_s'] if r['service_start_s'] is not None else r['exit_s']
        events[r['entered_s']]=events.get(r['entered_s'],0)+1
        events[right]=events.get(right,0)-1
    items=sorted(events.items());index=0;population=0;previous=start;left=start;x=[];y=[]
    while left<end:
        edge=min(left+step,end);area=D(0)
        while index<len(items) and items[index][0]<=edge:
            instant,change=items[index];area+=population*(instant-previous)
            population+=change;previous=instant;index+=1
        area+=population*(edge-previous);previous=edge
        x.append(float((left+edge)/2-start));y.append(float(area/(edge-left)));left=edge
    return x,y


def main():
    report=json.loads((ROOT/'results/analysis/queue-occupancy-audit.json').read_text())
    formal=[r for r in report['study_results'] if r['phase']=='confirmatory_block']
    if not formal:raise RuntimeError('No validated formal block')
    block=max(formal,key=lambda r:r['block'])
    folder=ROOT/'results/application-slots-confirmation-v1'/f"block-{block['block']:02d}"/block['attempt']
    assert audit.sha(folder/'analysis.json')==block['validated_analysis_sha256']
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for row_index,slots in enumerate([8,16]):
        for column,mode in enumerate(['peering','tgw']):
            condition=next(c for c in block['conditions'] if (c['mode'],c['slots'],c['configured_arrival_rps'])==(mode,slots,800))
            path=folder/mode/f'slots-{slots}-rate-800'
            request_proof=next(p for p in condition['sources'] if p['path'].endswith('requests.jsonl.gz'))
            assert audit.sha(path/'requests.jsonl.gz')==request_proof['sha256']
            ids={r['request_id'] for r in audit.raw(path/'requests.jsonl.gz')}
            ax=axes[row_index,column]
            for node,color in zip('cd',['#257aa9','#bd5f25']):
                file=path/f'queue-{node}.jsonl.gz'
                proof=next(p for p in condition['sources'] if p['path'].endswith(f'queue-{node}.jsonl.gz'))
                assert audit.sha(file)==proof['sha256']
                calls=[r for r in audit.raw(file) if r['request_id'] in ids]
                x,y=bins(calls);ax.plot(x,y,label='Worker '+node.upper(),color=color,linewidth=1.6)
            ax.set_title(f'{mode.upper()}, {slots} slots / worker')
            ax.set_xlabel('Seconds since first measured entry on each worker')
            ax.set_ylabel('Mean queued calls in 100 ms bin')
            ax.set_ylim(bottom=0);ax.grid(alpha=.25);ax.legend(fontsize=9)
    fig.suptitle(f'800 requests/s — formal block {block["block"]}\nFull cohort tail included; separate vertical scales; descriptive, no steady-state assumption',fontsize=12)
    out=ROOT/'docs/images/application/queue-occupancy';out.mkdir(parents=True,exist_ok=True)
    for extension in ['png','svg']:
        file=out/f'block-{block["block"]:02d}-queue.{extension}'
        fig.savefig(file,dpi=180)
        if extension=='svg':file.write_text('\n'.join(s.rstrip() for s in file.read_text().splitlines())+'\n',encoding='utf-8')
    plt.close(fig)
    print(json.dumps({'block':block['block'],'figure_directory':str(out),'bin_seconds':.1,'raw_changed':False}))


if __name__=='__main__':main()
