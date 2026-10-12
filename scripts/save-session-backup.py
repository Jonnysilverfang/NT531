"""Private local snapshot with full byte verification; never upload Terraform state."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    payload=[]
    for name in ['results','docs','scripts','experiments']:
        payload.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    payload.append(ROOT/'README.md')
    tf=ROOT/'infra/terraform'
    payload.extend(p for p in tf.iterdir() if p.is_file() and (p.suffix=='.tf' or p.name in ['README.md','.terraform.lock.hcl','nt531.tfstate','nt531.tfstate.backup']))
    payload=sorted(set(payload))
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT/'backups'/f'nt531-private-session-{stamp}.zip';out.parent.mkdir(exist_ok=True)
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in payload]
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path,item in zip(payload,manifest):archive.write(path,item['path'])
        archive.writestr('MANIFEST.json',json.dumps(dict(created_utc=stamp,private=True,files=manifest),indent=2))
    with zipfile.ZipFile(out) as archive:
        for item in manifest:
            raw=archive.read(item['path'])
            assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],item['path']
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(digest+'  '+out.name+'\n',encoding='utf-8')
    print(json.dumps(dict(private_backup=str(out),payload_files=len(manifest),bytes=out.stat().st_size,sha256=digest,verified=True,
        scope='All local results/docs/scripts/experiments plus Terraform code, lock and current state; no credentials, keys, tfvars, tmp or monitoring password. Keep ZIP private.')))


if __name__=='__main__':main()
