"""Run via SSM on EC2 A only. Save raw locally and return compressed JSON."""
import argparse,base64,datetime as dt,gzip,json,pathlib,re,subprocess,time,os
os.environ['LC_ALL']='C'
os.environ['TZ']='UTC'

def command(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(f'{args[0]} failed: {p.stderr[:300]}')
    return p.stdout

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--mode',choices=['peering','tgw'],required=True)
    ap.add_argument('--block',type=int,required=True)
    ap.add_argument('--protocol-hash',required=True)
    ap.add_argument('--attempt',required=True)
    a=ap.parse_args()
    assert re.fullmatch('[a-f0-9]{64}',a.protocol_hash)
    assert re.fullmatch('[a-f0-9]{32}',a.attempt)
    assert 1<=a.block<=16
    root=pathlib.Path('/home/ec2-user/nt531-results/rtt-confirmation-v1')/f'block-{a.block:02d}'/a.mode/a.attempt
    root.mkdir(parents=True,exist_ok=False)
    ip=command(['ip','-4','-o','addr','show','dev','ens5'])
    assert '10.10.10.212/' in ip,'Must run on A'
    assert pathlib.Path('/sys/class/net/ens5/mtu').read_text().strip()=='1500'
    assert command(['timedatectl','show','-p','NTPSynchronized','--value']).strip()=='yes'
    sockets=command(['ss','-Htn','state','established'])
    assert not re.search(r':520[123]\b',sockets),'Another TCP benchmark is running'
    result={'mode':a.mode,'block':a.block,'protocol_hash':a.protocol_hash,'attempt':a.attempt,
            'remote_folder':str(root),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'metadata':{'ip':ip,'kernel':command(['uname','-r']),
                        'ping_version':command(['ping','-V']),
                        'cpu_before':command(['mpstat','-P','ALL','1','1'])},'runs':[]}
    warm=subprocess.run(['ping','-n','-c','10','-i','.2','-W','2','10.20.10.155'],capture_output=True,text=True)
    (root/'warmup.txt').write_text(warm.stdout+warm.stderr)
    result['warmup']={'exit_code':warm.returncode,'stdout':warm.stdout,'stderr':warm.stderr}
    if warm.returncode:raise RuntimeError('Warm-up connectivity failed; no formal samples collected')
    for n in range(1,4):
        start=dt.datetime.now(dt.timezone.utc).isoformat()
        p=subprocess.run(['ping','-n','-c','100','-i','.2','-W','2','-s','56','10.20.10.155'],capture_output=True,text=True)
        row={'run':n,'started_utc':start,'ended_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
             'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
        (root/f'run-{n}.json').write_text(json.dumps(row,indent=2))
        result['runs'].append(row)
        if p.returncode not in (0,1):raise RuntimeError('Ping execution failed; raw remains on EC2')
        if n<3:time.sleep(5)
    result['metadata']['cpu_after']=command(['mpstat','-P','ALL','1','1'])
    result['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode()
    (root/'capture.json').write_bytes(raw)
    encoded=base64.b64encode(gzip.compress(raw)).decode()
    assert len(encoded)<20000,'Return too large for SSM; raw remains on EC2'
    print(encoded)

if __name__=='__main__':main()
