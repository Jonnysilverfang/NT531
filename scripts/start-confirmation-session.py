"""Start only the retained cohort after offline protocol and overlap guards.

Does not collect outcomes, change routes, retry measurements, or allocate resources.
Run with the user's AWS/network permission. Caller must stop the cohort in finally.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('confirmation',ROOT/'scripts/rtt-confirmation.py')
confirmation=importlib.util.module_from_spec(spec);spec.loader.exec_module(confirmation)
EXPECTED=dict(a='i-089bae0de9ec6bc4e',b='i-0484f42b82795f765',c='i-0a3f3e2e9d7185970',d='i-0abcc8853cee750e7')
PROTOCOLS={'confirmation-rtt-v1':'741d20c14d7fec43f58615c09ba84e8ae982d85e42d965cf648a7830e2f21f89',
    'application-slots-confirmation-v1':'65c69162a62cfd81c8531b9e9fea8480cd664bcddc4d1c78c4bb2b09e46cda0b'}

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def utc(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(dt.timezone.utc)

def plan(require_due=True):
    now=dt.datetime.now(dt.timezone.utc);jobs=[]
    for name,digest in PROTOCOLS.items():
        folder=ROOT/'results'/name
        assert hashlib.sha256((folder/'protocol.json').read_bytes()).hexdigest()==digest,'Protocol changed'
        analysis=read(folder/'analysis.json');assert not analysis['issues'],'Quality issue unresolved'
        for file in folder.glob('block-*/*/attempt.json'):
            attempt=read(file)
            assert attempt['status']!='started' or (file.parent/'complete.json').exists(), 'Unfinished attempt: inspect before starting another session'
        count=analysis['completed_blocks']
        if count==16:
            assert analysis['inferential_result'] is not None,'All blocks collected but eligibility unmet; no extra unplanned blocks'
            continue
        assert 0<=count<16
        next_folder=folder/f'block-{count+1:02d}'
        assert not list(next_folder.glob('*/attempt.json')),'Upcoming block has an earlier attempt; adjudicate rather than automatically retry'
        rows=analysis['rows']
        due=max((utc(row['started_utc'])+dt.timedelta(hours=2) for row in rows),default=now)
        jobs.append(dict(study=name,block=count+1,earliest_utc=due.isoformat(),due=due<=now))
    assert jobs,'Confirmation complete; do not start EC2 for this phase'
    if require_due:assert all(job['due'] for job in jobs),'Not yet two hours since preceding block; wait for a later scheduled session'
    return jobs

def start(profile):
    jobs=plan()
    def aws(args):return confirmation.cli(['aws',*args,'--profile',profile,'--region','us-east-1','--output','json','--no-cli-pager'],True)
    assert aws(['sts','get-caller-identity'])['Account']=='620306387033'
    outputs=confirmation.cli(['terraform','-chdir='+str(ROOT/'infra/terraform'),'output','-json'],True)
    instances=outputs['instances']['value'];routing=outputs['routing']['value']
    assert {n:instances[n]['id'] for n in 'abcd'}==EXPECTED,'Cohort changed; refuse new allocation or pooling'
    assert routing['transit_gateway_id']=='tgw-036e551008b8c0805'
    ids=list(EXPECTED.values())
    before=aws(['ec2','describe-instances','--instance-ids',*ids])
    hosts=[h for r in before['Reservations'] for h in r['Instances']]
    assert {h['InstanceId'] for h in hosts}==set(ids)
    for h in hosts:
        assert h['State']['Name'] in ['stopped','running']
        assert h['InstanceType']=='c6i.large' and h['ImageId']=='ami-0d27e0fb3bac4d724' and h['Placement']['AvailabilityZone']=='us-east-1a'
        assert any(t['Key']=='Project' and t['Value']=='NT531' for t in h.get('Tags',[]))
        node=next(n for n,i in EXPECTED.items() if i==h['InstanceId'])
        assert h['PrivateIpAddress']==instances[node]['private_ip']
    folder=ROOT/'results/session-lifecycle';folder.mkdir(exist_ok=True)
    path=folder/(dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-start.json')
    record=dict(action='start_retained_cohort_only',started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),jobs=jobs,instances=instances,retained_tgw_id=routing['transit_gateway_id'],status='starting')
    def save():path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        stopped=[h['InstanceId'] for h in hosts if h['State']['Name']=='stopped']
        if stopped:record['start_response']=aws(['ec2','start-instances','--instance-ids',*stopped]);save()
        confirmation.cli(['aws','ec2','wait','instance-running','--instance-ids',*ids,'--profile',profile,'--region','us-east-1'])
        deadline=time.monotonic()+600
        while True:
            online=aws(['ssm','describe-instance-information'])['InstanceInformationList']
            if all(any(x['InstanceId']==i and x['PingStatus']=='Online' for x in online) for i in ids):break
            if time.monotonic()>deadline:raise TimeoutError('SSM not Online; stop retained cohort, inspect before retry')
            time.sleep(20)
        # No application changes or reinstall; retained disks must match frozen app.
        spec=importlib.util.spec_from_file_location('deployment',ROOT/'scripts/application-qos.py')
        deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)
        exp=deployment.Experiment(profile);exp.stop()
        boots={}
        for node in 'abcd':
            boot=json.loads(exp.remote(node,['ip link set dev ens5 mtu 1500',"python3 -c 'import pathlib,json;print(json.dumps(dict(boot_id=pathlib.Path(\"/proc/sys/kernel/random/boot_id\").read_text().strip(),uptime=float(pathlib.Path(\"/proc/uptime\").read_text().split()[0]))))'"]))
            boots[node]=boot
        record['boots']=boots;save()
        wait=max(0,1805-min(b['uptime'] for b in boots.values()))
        print(f'Existing cohort Online; waiting {wait:.0f}s for >=30min uptime. No measurement underway.',flush=True)
        until=time.monotonic()+wait
        while time.monotonic()<until:time.sleep(min(30,max(0,until-time.monotonic())))
        subprocess.run([r'C:\Users\MSI\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe','-NoProfile','-File',str(ROOT/'scripts/Prepare-DownloadKey.ps1')],check=True)
        record.update(status='ready',ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());save()
        print(json.dumps(dict(status='ready',jobs=jobs,proof=str(path))),flush=True)
    except Exception as e:
        record.update(status='failed_requires_stop',error=str(e),ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',default='nt533-lab');p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.check:print(json.dumps(dict(jobs=plan(require_due=False),read_only=True)))
    else:start(args.profile)
