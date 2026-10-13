"""Audit identifiability of common-window receiver goodput from historical files."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    records=[]
    for mode in ['peering','tgw']:
        for file in sorted((ROOT/'results/formal'/mode/'tcp-fanin').glob('*/*/run-*.json')):
            j=json.loads(file.read_text(encoding='utf-8-sig'))
            records.append(dict(path=file.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                mode=mode,client_epoch_seconds=j['start']['timestamp']['timesecs'],
                server_json_present=isinstance(j.get('server_output_json'),dict),
                server_text_present=bool(j.get('server_output_text')),
                client_interval_sums_are_sender=all(i['sum'].get('sender') is True for i in j['intervals']),
                receiver_total_bytes=j['end']['sum_received']['bytes'],receiver_seconds=j['end']['sum_received']['seconds']))
    assert len(records)==30
    assert not any(r['server_json_present'] for r in records)
    assert all(r['server_text_present'] and r['client_interval_sums_are_sender'] for r in records)
    result=dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),files=len(records),receiver_interval_byte_timestamps_available=False,
        conclusion='Existing 30 client JSON files contain sender intervals and receiver total summaries, with server text only. Exact received bytes in a shared wall-clock window are not identifiable from these artifacts.',
        scope='Retain approximate sum of separate receiver-window goodputs. No interpolation of sender bytes as receiver bytes, no new measurement, no protocol or historical metrics modification.',sources=records)
    (ROOT/'results/analysis/fanin-common-window-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sources'}))

if __name__=='__main__':main()
