"""Worker-slot intervention; engineering validation is never pooled with confirmation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import importlib.util
import json
import random
import secrets
import shlex
import shutil
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'experiments/application-qos'
STUDY=ROOT/'results/application-slots-confirmation-v1'
PROTOCOL=STUDY/'protocol.json'
spec=importlib.util.spec_from_file_location('deployment',ROOT/'scripts/application-qos.py')
deploy=importlib.util.module_from_spec(spec);spec.loader.exec_module(deploy)


def initialize():
    if PROTOCOL.exists():raise ValueError('Protocol already frozen; do not overwrite')
    STUDY.mkdir(parents=True,exist_ok=True)
    seed=secrets.randbits(64);rng=random.Random(seed)
    first=['peering']*8+['tgw']*8;rng.shuffle(first)
    conditions=[dict(slots=s,rate=r) for s in [8,16] for r in [600,800]]
    # Balanced cyclic rotations, shuffled allocation to blocks. Same order in both modes.
    rotations=list(range(4))*4;rng.shuffle(rotations)
    protocol=dict(id='application-slots-confirmation-v1',created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        question='Does 8->16 worker slots improve deadline success at 800 rps by over 10 percentage points, averaged over both routes, in a majority of paired blocks?',
        primary='P(block mean_over_routes(p16-p8) > 0.10) > 0.5',alpha=.05,improvement_margin_fraction=.10,
        blocks=16,minimum_distinct_local_dates=4,minimum_gap_seconds=7200,maximum_block_span_seconds=3600,
        expected_instance_type='c6i.large',expected_ami='ami-0d27e0fb3bac4d724',expected_az='us-east-1a',minimum_uptime_seconds=1800,
        worker_delay_ms=10,worker_response_bytes=4096,worker_slots=8,
        deadline_ms=50,request_timeout_seconds=2,maximum_inflight=4000,queue_logging=True,
        warmup_seconds=5,duration_seconds=15,settle_seconds=20,seed=seed,
        stopping_rule='All 16 valid blocks, no significance-based stop; technical failures retained, no automatic retry',
        randomization='Balanced mode-first and four condition-order cyclic rotations; each condition has fresh servers, same order in the paired modes',
        primary_critical_successes=12,primary_null_tail_at_12=deploy.confirmation.tail(16,12),
        power_if_block_success_probability_0_8=deploy.confirmation.tail(16,12,.8),
        precision_note='Power refers to binary block success under assumed 0.8, not known empirical effect; no promised CI width',
        queue_measurement='All entered worker calls buffered, timestamps from one monotonic worker clock; handler completion is not client receipt; cancelled and missing calls retained',
        scope='Same EC2/TGW cohort across confirmation; stop/start allowed with boot ID and uptime recorded, >=30min uptime. New identities require a separate study, never pooling.',
        secondary='Paired network differences and queue/service diagnostics are descriptive with whole-block bootstrap CIs; no equivalence claim or additional confirmatory tests',
        independence='Blocks are not requests; spacing/randomization do not prove independence. Engineering/pilot/calibration excluded.',
        application_sha256=deploy.sha(APP/'app.py'),runtime_requirements_sha256=deploy.sha(APP/'requirements.txt'),
        schedule=[dict(block=i+1,mode_order=[m,'tgw' if m=='peering' else 'peering'],
          conditions=conditions[rotations[i]:]+conditions[:rotations[i]]) for i,m in enumerate(first)])
    PROTOCOL.write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(protocol=str(PROTOCOL),sha256=deploy.sha(PROTOCOL),status='frozen_no_confirmatory_data')))


def run(profile,block=None):
    protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    assert protocol['application_sha256']==deploy.sha(APP/'app.py'), 'Application changed since freeze'
    assert protocol['runtime_requirements_sha256']==deploy.sha(APP/'requirements.txt')
    exp=deploy.Experiment(profile)
    engineering=block is None
    now=dt.datetime.now(dt.timezone.utc)
    previous=list(STUDY.glob('block-*/*/attempt.json'))
    completed=[json.loads(p.read_text(encoding='utf-8')) for p in previous if json.loads(p.read_text(encoding='utf-8'))['status']=='complete']
    if not engineering:
        assert 1<=block<=protocol['blocks']
        assert not any(p['block']==block for p in completed),'Block already complete'
        assert block==len(completed)+1, 'Collect in protocol block order'
        for p in completed:
            assert (now-dt.datetime.fromisoformat(p['started_utc'])).total_seconds()>=protocol['minimum_gap_seconds']
            assert [exp.instances[n]['id'] for n in 'abcd']==p['cohort_ids'] and exp.routing['transit_gateway_id']==p['tgw_id'], 'Cohort changed; separate study'
        for file in previous:
            prior=json.loads(file.read_text(encoding='utf-8'))
            if prior['status']=='complete':
                verified=json.loads((file.parent/'analysis.json').read_text(encoding='utf-8'))
                assert not verified['issues'], 'Verify previous raw block before continuing'
    schedule=protocol['schedule'][(block or 1)-1]
    if engineering:
        schedule=dict(schedule)
        schedule['mode_order']=secrets.SystemRandom().sample(['peering','tgw'],2)
    base=ROOT/'results/application-slots-engineering-v1' if engineering else STUDY/f'block-{block:02d}'
    out=base/exp.attempt;out.mkdir(parents=True)
    for src,name in [(Path(__file__),'runner-source.py'),(ROOT/'scripts/application-qos.py','deployment-source.py'),
                     (APP/'app.py','app.py'),(APP/'requirements.txt','requirements.txt'),(PROTOCOL,'protocol.json')]:
        shutil.copyfile(src,out/name)
    record=dict(attempt=exp.attempt,block=block,phase='engineering_validation_excluded' if engineering else 'confirmatory_block',
      started_utc=now.isoformat(),protocol_sha256=deploy.sha(PROTOCOL),application_sha256=deploy.sha(APP/'app.py'),
      runner_sha256=deploy.sha(Path(__file__)),deployment_sha256=deploy.sha(ROOT/'scripts/application-qos.py'),
      cohort_ids=[exp.instances[n]['id'] for n in 'abcd'],tgw_id=exp.routing['transit_gateway_id'],
      original_mode=exp.original,instances=exp.instances,routing_context=exp.routing,
      protocol=protocol,schedule=schedule,status='started',runs=[],cleanup_errors=[])
    def save():(out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        exp.preflight(out)
        ec2=exp.aws(['ec2','describe-instances','--instance-ids',*record['cohort_ids']])
        env=[i for r in ec2['Reservations'] for i in r['Instances']]
        assert all(i['ImageId']==protocol['expected_ami'] for i in env)
        boots={}
        def boot(node):
            value=json.loads(exp.remote(node,["python3 -c 'import pathlib,json;print(json.dumps(dict(boot_id=pathlib.Path(\"/proc/sys/kernel/random/boot_id\").read_text().strip(),uptime=float(pathlib.Path(\"/proc/uptime\").read_text().split()[0]))))'"]))
            assert value['uptime']>=protocol['minimum_uptime_seconds'], 'Wait 30min after boot'
            return node,value
        with ThreadPoolExecutor(max_workers=4) as pool:boots=dict(pool.map(boot,'abcd'))
        record['boots']=boots;save()
        for mode in schedule['mode_order']:
            exp.stop();exp.switch(mode)
            folder=out/mode;folder.mkdir()
            exp.snapshot(mode,folder/'routes-before.json');time.sleep(protocol['settle_seconds'])
            for condition in schedule['conditions']:
                slots,rate=condition['slots'],condition['rate']
                print(f'{mode} slots={slots} rate={rate}: fresh servers, warmup 5s + measure 15s',flush=True)
                exp.stop()
                settings=dict(protocol,worker_slots=slots)
                health=exp.start(mode,protocol=settings);exp.monitor_start(mode)
                run_id=f'{exp.attempt}-{mode}-s{slots}-r{rate}'
                folder_run=folder/f'slots-{slots}-rate-{rate}';folder_run.mkdir()
                (folder_run/'health-before.json').write_text(json.dumps(health,indent=2)+'\n',encoding='utf-8')
                stem=f'{deploy.REMOTE}/results/{run_id}'
                cmd=f'{deploy.REMOTE}/venv/bin/python {deploy.REMOTE}/app.py load --node a --mode {mode} --rate {rate} --maximum-inflight 4000 --timeout 2 --deadline-ms 50 --response-bytes 4096'
                exp.remote('a',[f'runuser -u ec2-user -- {cmd} --run-id {run_id}-warm --duration 5 --out {stem}-warm > /dev/null'])
                # Warmup may leave processing after its client timeouts. Drain before measured window.
                for node in 'cd':
                    ip=exp.instances[node]['private_ip']
                    drain="import json,time,urllib.request; end=time.monotonic()+15\nwhile time.monotonic()<end:\n d=json.load(urllib.request.urlopen('http://"+ip+":8081/health'));\n if d['queued']==0 and d['active']==0: break\n time.sleep(.1)\nelse: raise RuntimeError('Backlog did not drain')"
                    exp.remote(node,['python3 -c '+shlex.quote(drain)])
                result=json.loads(exp.remote('a',[f'runuser -u ec2-user -- {cmd} --run-id {run_id} --duration 15 --out {stem}']))
                record['runs'].append(dict(condition=condition,mode=mode,summary=result));save()
                (folder_run/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
                exp.remote('a',['python3 -c '+shlex.quote(f"import pathlib,gzip;p=pathlib.Path({stem!r});(p/'requests.jsonl.gz').write_bytes(gzip.compress((p/'requests.jsonl').read_bytes(),mtime=0))")])
                # Stop before downloads: flush complete worker logs; CPU captures are per condition.
                with ThreadPoolExecutor(max_workers=3) as pool:
                    list(pool.map(lambda node:exp.remote(node,['systemctl stop nt531-app.service']), 'cdb'))
                exp.monitor_save(mode,folder_run)
                downloads=[('a',stem+'/requests.jsonl.gz',folder_run/'requests.jsonl.gz')]
                downloads.extend((node,f'{deploy.REMOTE}/queue-{exp.attempt}-{node}.jsonl.gz',folder_run/f'queue-{node}.jsonl.gz') for node in 'cd')
                with ThreadPoolExecutor(max_workers=3) as pool:
                    list(pool.map(lambda item:exp.fetch(*item),downloads))
                # Every service is stopped and queues are discarded before next condition.
            exp.snapshot(mode,folder/'routes-after.json')
        record['status']='complete'
        if not engineering and (dt.datetime.now(dt.timezone.utc)-now).total_seconds()>protocol['maximum_block_span_seconds']:
            raise RuntimeError('Block exceeded prespecified time span')
    except Exception as e:
        record['status']='failed';record['error']=str(e);raise
    finally:
        for name,action in [('stop_services',exp.stop),('restore_routes',lambda:exp.switch(exp.original))]:
            try:action()
            except Exception as e:record['cleanup_errors'].append(name+': '+str(e))
        record['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        if record['cleanup_errors']:record['status']='cleanup_failed'
        save();print(json.dumps(dict(folder=str(out),status=record['status'],cleanup_errors=record['cleanup_errors'])),flush=True)
    if record['status']!='complete':
        raise RuntimeError('Attempt cleanup failed; inspect attempt.json before another run')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['init','engineering','block'])
    p.add_argument('--profile',default='nt533-lab');p.add_argument('--block',type=int)
    args=p.parse_args()
    if args.action=='init':initialize()
    else:
        if args.action=='block' and args.block is None:p.error('--block required')
        run(args.profile,args.block if args.action=='block' else None)
