"""Recompute slot-intervention outcomes and worker timing from complete raw logs."""
import argparse
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import statistics as st
import datetime as dt

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('app',HERE/'app.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
spec=importlib.util.spec_from_file_location('rtt',ROOT/'scripts/rtt-confirmation.py');rtt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rtt)


def raw(path):return [json.loads(line) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def inference(blocks,p):
    if len(blocks)!=p['blocks']:raise ValueError('All prespecified blocks required')
    effects=[Decimal(b['improvement']) for b in blocks]
    k=sum(effect>Decimal(str(p['improvement_margin_fraction'])) for effect in effects)
    vectors={'slot_improvement_at_800': [float(v)*100 for v in effects]}
    for slots in [8,16]:
        for rate in [600,800]:
            values=[]
            for block in blocks:
                pair={r['mode']:100*r['deadline_success_count']/r['scheduled'] for r in block['rows'] if r['slots']==slots and r['rate_rps']==rate}
                values.append(pair['tgw']-pair['peering'])
            vectors[f'tgw_minus_peering_slots_{slots}_rate_{rate}']=values
    rng=random.Random(p['seed']);samples={key:[] for key in vectors}
    for _ in range(20000):
        indices=[rng.randrange(len(blocks)) for _ in blocks]
        for key,values in vectors.items():samples[key].append(st.mean(values[i] for i in indices))
    return dict(n=len(blocks),above_margin_blocks=k,one_sided_exact_p=rtt.tail(len(blocks),k),
        probability_lower_one_sided_95=rtt.lower_probability(len(blocks),k),
        majority_improvement_supported=k>=p['primary_critical_successes'],
        mean_slot_improvement_percentage_points=float(st.mean(effects)*100),
        descriptive_whole_block_bootstrap_95_ci={key:dict(mean_percentage_points=st.mean(values),
            lower=app.percentile(samples[key],.025),upper=app.percentile(samples[key],.975)) for key,values in vectors.items()},
        bootstrap_replicates=20000,bootstrap_scope='Resample entire blocks using identical indices across contrasts; secondary descriptive, not equivalence/extra significance tests')


def analyze(folder):
    record=json.loads((folder/'attempt.json').read_text(encoding='utf-8'))
    p=record['protocol'];issues=[];rows=[]
    recovery=None
    if (folder/'download-recovery.json').exists():
        recovery=json.loads((folder/'download-recovery.json').read_text(encoding='utf-8'))
        if recovery['failed_attempt_sha256']!=sha(folder/'attempt.json') or any(sha(folder/f['path'])!=f['sha256'] for f in recovery['recovered_files']):issues.append('Download recovery hash mismatch')
    recovered=record['phase']=='engineering_validation_excluded' and record['status']=='failed' and recovery is not None and recovery['status']=='verified_download_only' and len(record['runs'])==8 and '429' in record.get('error','')
    if (record['status']!='complete' and not recovered) or record['cleanup_errors']:issues.append('Attempt/cleanup incomplete')
    for name,key in [('app.py','application_sha256'),('protocol.json','protocol_sha256'),('runner-source.py','runner_sha256'),('deployment-source.py','deployment_sha256')]:
        if sha(folder/name)!=record[key]:issues.append('Source mismatch '+name)
    if record['application_sha256']!=p['application_sha256']:issues.append('Application changed after freeze')
    if sha(folder/'requirements.txt')!=p['runtime_requirements_sha256']:issues.append('Runtime requirements mismatch')
    packages=[sorted(line for line in (folder/f'preflight-{n}.txt').read_text(encoding='utf-8').splitlines() if '==' in line) for n in 'abcd']
    if any(packages[0]!=x for x in packages):issues.append('Dependency versions differ across hosts')
    if len(record['runs'])!=8:issues.append('Expected all 8 conditions')
    expected={(m,s,r) for m in ['peering','tgw'] for s in [8,16] for r in [600,800]}
    observed=[(r['mode'],r['condition']['slots'],r['condition']['rate']) for r in record['runs']]
    if set(observed)!=expected or len(set(observed))!=len(observed):issues.append('Missing/duplicate condition')
    if record['phase']=='confirmatory_block':
        if (dt.datetime.fromisoformat(record['ended_utc'])-dt.datetime.fromisoformat(record['started_utc'])).total_seconds()>p['maximum_block_span_seconds']:issues.append('Block exceeded time span')
        if set(record.get('boots',{}))!=set('abcd') or any(b['uptime']<p['minimum_uptime_seconds'] for b in record.get('boots',{}).values()):issues.append('Boot/settle metadata invalid')
    for mode in record['schedule']['mode_order']:
        for filename in ['routes-before.json','routes-after.json']:
            state=json.loads((folder/mode/filename).read_text(encoding='utf-8'));routing=record['routing_context']
            for source,target in [('a','b'),('b','a'),('b','c'),('c','b'),('b','d'),('d','b')]:
                table=next(t for t in state['RouteTables'] if t['RouteTableId']==routing[f'route_table_{source}_id'])
                route=next(r for r in table['Routes'] if r.get('DestinationCidrBlock')==f"10.{dict(a=10,b=20,c=30,d=40)[target]}.0.0/16")
                pair=''.join(sorted([source,target]));peer=routing['peering_id'] if pair=='ab' else routing['cross_peering_ids'][pair]
                if route['State']!='active' or route.get('TransitGatewayId' if mode=='tgw' else 'VpcPeeringConnectionId')!=(routing['transit_gateway_id'] if mode=='tgw' else peer):issues.append('Route mismatch '+source+target)
        for condition in record['schedule']['conditions']:
            slots,rate=condition['slots'],condition['rate'];path=folder/mode/f'slots-{slots}-rate-{rate}'
            result=json.loads((path/'summary.json').read_text(encoding='utf-8'));requests=raw(path/'requests.jsonl.gz')
            if len(requests)!=rate*p['duration_seconds'] or [r['id'] for r in requests]!=list(range(len(requests))):issues.append('Missing/duplicate request IDs')
            if app.summarize(requests,p['deadline_ms'])!=result['summary']:issues.append('Raw summary mismatch')
            generator_valid=not any(r['error']=='generator_inflight_limit' for r in requests) and app.percentile([r['dispatch_lag_ms'] for r in requests],.95)<=5
            if not result['generator_valid'] or not generator_valid or result['tracing']:issues.append('Generator invalid/tracing on')
            if result['mode']!=mode or result['config']['rate']!=rate:issues.append('Condition label mismatch')
            settings=dict(duration=p['duration_seconds'],deadline_ms=p['deadline_ms'],timeout=p['request_timeout_seconds'],
                maximum_inflight=p['maximum_inflight'],response_bytes=p['worker_response_bytes'],node='a',role='load')
            if any(result['config'].get(k)!=v for k,v in settings.items()):issues.append('Load settings differ from protocol')
            if any(r['request_id']!=f"{result['config']['run_id']}:{r['id']}" for r in requests):issues.append('Request ID/run mismatch')
            if record['phase']=='confirmatory_block':
                health=json.loads((path/'health-before.json').read_text(encoding='utf-8'))
                for node in 'cd':
                    if health[node]['worker_slots']!=slots or not health[node]['queue_logging'] or health[node]['active'] or health[node]['queued']:issues.append('Worker setting/backlog invalid')
            ids={r['request_id']:r for r in requests}
            if len(ids)!=len(requests):issues.append('Duplicate global request ID')
            worker_summary=[]
            for node in 'cd':
                logs=raw(path/f'queue-{node}.jsonl.gz')
                selected=[r for r in logs if r['request_id'] in ids]
                unique={r['request_id']:r for r in selected}
                if len(unique)!=len(selected):issues.append('Duplicate worker ID '+node)
                if any(r['node']!=node or r['exit_s'] is None or r['status']=='entered' for r in selected):issues.append('Worker timing log incomplete '+node)
                good=[r for r in selected if r['status']=='handler_completed']
                if any(not(r['entered_s']<=r['service_start_s']<=r['service_end_s']<=r['exit_s']) for r in good):issues.append('Worker timing order invalid')
                if any(request['ok'] and (rid not in unique or unique[rid]['status']!='handler_completed') for rid,request in ids.items()):issues.append('Successful client result lacks completed worker '+node)
                waits=[1000*(r['service_start_s']-r['entered_s']) for r in selected if r['service_start_s'] is not None]
                services=[1000*(r['service_end_s']-r['service_start_s']) for r in good]
                worker_summary.append(dict(node=node,entered=len(selected),not_entered=len(ids)-len(selected),
                    handler_completed=len(good),cancelled=sum(r['status']=='cancelled' for r in selected),
                    incomplete_or_error=sum(r['status'] not in ['handler_completed','cancelled'] for r in selected),
                    client_failed_but_handler_completed=sum(not ids[r['request_id']]['ok'] for r in good),
                    queue_wait_p50_ms=app.percentile(waits,.5),queue_wait_p95_ms=app.percentile(waits,.95),
                    service_p50_ms=app.percentile(services,.5),service_p95_ms=app.percentile(services,.95),
                    peak_queued_before=max((r['queued_before'] for r in selected),default=0),
                    peak_active_before=max((r['active_before'] for r in selected),default=0),
                    raw_count_including_warmup=len(logs),scope='Matched measured request IDs; all worker calls including client failures retained. Handler completion is not receipt by A.'))
            for node in 'abcd':
                monitor=json.loads(gzip.decompress((path/f'monitor-{node}.json.gz').read_bytes()))
                if not all(monitor.get(k) for k in ['cpu.txt','ena-before.txt','ena-after.txt']):issues.append('CPU/ENA missing')
            rows.append(dict(mode=mode,slots=slots,rate_rps=rate,workers=worker_summary,**result['summary']))
    def fraction(mode,slots,rate):
        row=next(r for r in rows if (r['mode'],r['slots'],r['rate_rps'])==(mode,slots,rate))
        return Decimal(row['deadline_success_count'])/Decimal(row['scheduled'])
    improvement=sum((fraction(m,16,800)-fraction(m,8,800)) for m in ['peering','tgw'])/2
    sources=[dict(path=str(f.relative_to(folder)).replace('\\','/'),sha256=sha(f)) for f in sorted(folder.rglob('*')) if f.is_file() and f.name not in ['analysis.json','endpoint-diagnostics.json']]
    output=dict(phase=record['phase'],issues=issues,rows=rows,collection_recovery=recovery,primary_slot_improvement_fraction=str(improvement),
        primary_block_above_margin=improvement>Decimal(str(p['improvement_margin_fraction'])),
        inferential_result=None,sources=sources,scope='One block; no inferential conclusion. Engineering validation excluded from confirmatory study.')
    (folder/'analysis.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(phase=record['phase'],issues=issues,primary_slot_improvement_fraction=str(improvement),
        rows=[dict(mode=r['mode'],slots=r['slots'],rate=r['rate_rps'],deadline=r['deadline_success_fraction'],p95=r['successful_completion_p95_ms'],
         worker_queue_p95=[w['queue_wait_p95_ms'] for w in r['workers']],worker_service_p95=[w['service_p95_ms'] for w in r['workers']]) for r in rows])))
    return output


def study():
    folder=ROOT/'results/application-slots-confirmation-v1'
    p=json.loads((folder/'protocol.json').read_text(encoding='utf-8'));blocks=[];issues=[]
    for file in sorted(folder.glob('block-*/*/attempt.json')):
        record=json.loads(file.read_text(encoding='utf-8'))
        if record['status']!='complete':continue
        if record['phase']!='confirmatory_block':
            issues.append('Non-confirmatory data in study directory');continue
        if record['schedule']!=p['schedule'][record['block']-1]:
            issues.append('Prespecified block schedule changed');continue
        result=analyze(file.parent)
        if result['issues']:issues.extend(result['issues']);continue
        blocks.append(dict(block=record['block'],attempt=record['attempt'],started_utc=record['started_utc'],
            cohort_ids=record['cohort_ids'],tgw_id=record['tgw_id'],protocol_sha256=record['protocol_sha256'],
            improvement=result['primary_slot_improvement_fraction'],success=result['primary_block_above_margin'],rows=result['rows']))
    if len({b['block'] for b in blocks})!=len(blocks):issues.append('Multiple complete attempts for one block')
    if sorted(b['block'] for b in blocks)!=list(range(1,len(blocks)+1)):issues.append('Block numbering gap')
    dates={dt.datetime.fromisoformat(b['started_utc']).astimezone(dt.timezone(dt.timedelta(hours=7))).date().isoformat() for b in blocks}
    for first,second in zip(blocks,blocks[1:]):
        if (dt.datetime.fromisoformat(second['started_utc'])-dt.datetime.fromisoformat(first['started_utc'])).total_seconds()<p['minimum_gap_seconds']:issues.append('Blocks too close')
    if any(b['protocol_sha256']!=sha(folder/'protocol.json') for b in blocks):issues.append('Protocol changed')
    if blocks and any((b['cohort_ids'],b['tgw_id'])!=(blocks[0]['cohort_ids'],blocks[0]['tgw_id']) for b in blocks):issues.append('Cohort changed')
    eligible=len(blocks)==p['blocks'] and len(dates)>=p['minimum_distinct_local_dates'] and not issues
    result=dict(completed_blocks=len(blocks),target_blocks=p['blocks'],local_dates=sorted(dates),issues=issues,rows=blocks,
        inferential_result=None,scope='No conclusion before all prespecified blocks/date/quality criteria; engineering data excluded')
    if eligible:
        result['inferential_result']=inference(blocks,p)
    (folder/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path,nargs='?');p.add_argument('--study',action='store_true');args=p.parse_args()
    study() if args.study else analyze(args.folder)
