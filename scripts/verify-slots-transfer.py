"""Verify the after-capture SCP evidence; publishes public host-key provenance only."""
import argparse,datetime as dt,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(folder):
    folder=folder.resolve();assert (ROOT/'results/application-slots-confirmation-v1').resolve() in folder.parents
    record=read(folder/'attempt.json');assert record['status']=='complete' and not record['cleanup_errors']
    temp=ROOT/'tmp/application-qos'/record['attempt']
    provenance={}
    for node in 'abcd':
        host=record['instances'][node]['public_ip'];known=temp/('known-hosts-'+node)
        match=[]
        for request in temp.glob(node+'-*.json'):
            if request.name.endswith('.result.json'):continue
            req=read(request)
            if 'cat /etc/ssh/ssh_host_ed25519_key.pub' not in req.get('Parameters',{}).get('commands',[]):continue
            result=request.with_suffix('.result.json');reply=read(result)
            assert reply['Status']=='Success' and reply['InstanceId']==record['instances'][node]['id']
            pub=reply['StandardOutputContent'].split();assert pub[0]=='ssh-ed25519'
            assert known.read_text(encoding='utf-8')==host+' '+pub[0]+' '+pub[1]+'\n'
            match.append(dict(instance_id=reply['InstanceId'],public_ip=host,public_host_key=pub[0]+' '+pub[1],
                known_hosts_sha256=sha(known),ssm_result_sha256=sha(result),ssm_result={k:reply.get(k) for k in ['CommandId','InstanceId','DocumentName','Status','ResponseCode','ExecutionStartDateTime','ExecutionEndDateTime','StandardOutputContent']}))
        assert len(match)==1,'Expected one authenticated public host-key capture per node'
        provenance[node]=match[0]
    expected={}
    for mode in ['peering','tgw']:
        for slots in [8,16]:
            for rate in [600,800]:
                path=folder/mode/f'slots-{slots}-rate-{rate}'
                for name,node in [('requests.jsonl.gz','a'),('queue-c.jsonl.gz','c'),('queue-d.jsonl.gz','d')]+[(f'monitor-{n}.json.gz',n) for n in 'abcd']:
                    expected[path/name]=node
    assert len(expected)==56
    proofs=list(folder.rglob('*.transport.json'));assert len(proofs)==56
    files=[]
    for file,node in sorted(expected.items()):
        proof=read(file.with_suffix(file.suffix+'.transport.json'))
        assert proof['transport']=='scp_after_capture' and proof['node']==node
        assert proof['strict_host_key_checking'] is True
        assert proof['known_hosts_sha256']==provenance[node]['known_hosts_sha256']
        assert file.stat().st_size==proof['verified_size'] and sha(file)==proof['verified_sha256']
        files.append(dict(path=file.relative_to(folder).as_posix(),node=node,bytes=file.stat().st_size,sha256=sha(file)))
    out=folder/'transport-validation.json'
    out.write_text(json.dumps(dict(verified_utc=dt.datetime.now(dt.timezone.utc).isoformat(),status='verified',files=files,host_key_provenance=provenance,
        scope='56 after-capture files; hashes match remote SSM checks and pinned public host keys. No private key, credentials or original-key hash published.'),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='verified',files=len(files),public_host_keys=4,proof=str(out))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);main(p.parse_args().folder)
