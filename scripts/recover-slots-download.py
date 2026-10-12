"""Recover missing engineering artifacts only; never retry a measured condition."""
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('deployment',ROOT/'scripts/application-qos.py')
deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)


def main(folder,profile):
    folder=folder.resolve()
    assert folder.parent==ROOT/'results/application-slots-engineering-v1'
    record=json.loads((folder/'attempt.json').read_text(encoding='utf-8'))
    assert record['phase']=='engineering_validation_excluded' and record['status']=='failed'
    assert len(record['runs'])==8 and not record['cleanup_errors'] and '429' in record['error']
    exp=deployment.Experiment(profile)
    assert [exp.instances[n]['id'] for n in 'abcd']==record['cohort_ids']
    assert exp.routing['transit_gateway_id']==record['tgw_id'] and exp.original==record['original_mode']=='tgw'
    assert record['schedule']['mode_order'][-1]=='tgw'
    recovery=dict(status='started',started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        failed_attempt_sha256=deployment.sha(folder/'attempt.json'),recovered_files=[],
        scope='Read-only recovery after AWS OAuth 429; no remeasurement/start/route changes. Original failed attempt.json retained. TGW after-snapshot is taken after successful original cleanup restored TGW.')
    destination=folder/'download-recovery.json'
    assert not destination.exists(), 'Inspect previous recovery; do not overwrite'
    destination.write_text(json.dumps(recovery,indent=2)+'\n',encoding='utf-8')
    try:
        for node in 'cdb':
            exp.remote(node,['test "$(systemctl is-active nt531-app.service || true)" != active'])
        for condition in record['runs']:
            mode=condition['mode'];slots=condition['condition']['slots'];rate=condition['condition']['rate']
            path=folder/mode/f'slots-{slots}-rate-{rate}'
            for node in 'cd':
                target=path/f'queue-{node}.jsonl.gz'
                if target.exists():continue
                # Per-host queue filenames were reused only when a new condition starts.
                # Only the LAST measured condition can safely be recovered this way.
                assert condition is record['runs'][-1], 'Older remote queue file may have been overwritten'
                exp.fetch(node,f"{deployment.REMOTE}/queue-{record['attempt']}-{node}.jsonl.gz",target)
                recovery['recovered_files'].append(dict(path=target.relative_to(folder).as_posix(),sha256=deployment.sha(target)))
                destination.write_text(json.dumps(recovery,indent=2)+'\n',encoding='utf-8')
        target=folder/'tgw/routes-after.json'
        assert not target.exists()
        exp.snapshot('tgw',target)
        recovery['recovered_files'].append(dict(path=target.relative_to(folder).as_posix(),sha256=deployment.sha(target)))
        assert deployment.sha(folder/'attempt.json')==recovery['failed_attempt_sha256']
        recovery.update(status='verified_download_only',ended_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    except Exception as e:
        recovery.update(status='failed',error=str(e));raise
    finally:
        destination.write_text(json.dumps(recovery,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(recovery),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--profile',default='nt533-lab')
    args=parser.parse_args();main(args.folder,args.profile)
