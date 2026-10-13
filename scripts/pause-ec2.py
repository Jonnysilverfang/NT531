"""User-authorized end-of-session stop; preserve all networking and volumes."""
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('deployment',ROOT/'scripts/application-qos.py')
deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)


def main(profile):
    exp=deployment.Experiment(profile)
    ids=[exp.instances[n]['id'] for n in 'abcd']
    # Experiment checks AWS account, exact private addresses and all SSM identities.
    before=exp.aws(['ec2','describe-instances','--instance-ids',*ids])
    hosts=[h for r in before['Reservations'] for h in r['Instances']]
    assert len(hosts)==4 and all(any(t['Key']=='Project' and t['Value']=='NT531' for t in h.get('Tags',[])) for h in hosts)
    exp.stop()
    backup=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/save-session-backup.py')],text=True))
    assert backup['verified']
    folder=ROOT/'results/session-lifecycle';folder.mkdir(exist_ok=True)
    out=folder/(dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-stop.json')
    record=dict(action='stop_only',user_decision='Stop four EC2; keep infrastructure for next confirmation sessions',
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),instances=exp.instances,
        retained_tgw_id=exp.routing['transit_gateway_id'],backup=backup,status='stopping')
    out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    record['stop_response']=exp.aws(['ec2','stop-instances','--instance-ids',*ids])
    deployment.cli(['aws','ec2','wait','instance-stopped','--instance-ids',*ids,'--profile',profile,'--region','us-east-1'])
    after=exp.aws(['ec2','describe-instances','--instance-ids',*ids])
    record['states']={h['InstanceId']:h['State']['Name'] for r in after['Reservations'] for h in r['Instances']}
    assert set(record['states'])==set(ids) and set(record['states'].values())=={'stopped'}
    record.update(status='stopped_verified',ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        scope='No terminate/destroy/delete calls. EBS, EIP and TGW retained and may continue to incur fees.')
    # No transfer can be active after the cohort is stopped. Delete only our
    # temporary ACL-protected copy; the user's original SSH key is untouched.
    key=ROOT/'tmp/ssh-download-private/nt531.pem'
    try:
        if key.exists():key.unlink()
        record['temporary_download_key_removed']=not key.exists()
    except OSError as e:
        record['temporary_key_cleanup_error']=str(e)
    out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(proof=str(out),status=record['status'],instances=record['states'],backup=backup)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--profile',default='nt533-lab')
    main(parser.parse_args().profile)
