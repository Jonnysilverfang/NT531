"""Verify real saved smoke traces through the local Grafana/Tempo datasource."""
import argparse
import base64
import datetime as dt
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    args = p.parse_args()
    spans = [json.loads(line) for line in (args.folder/'trace-smoke/a.jsonl').read_text(encoding='utf-8').splitlines()]
    trace_id = next(s for s in spans if s['name']=='load.request')['context']['trace_id'].removeprefix('0x')
    config = {}
    for line in (ROOT/'monitoring/.env').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith('#'):
            key,value = line.split('=',1)
            config[key]=value.strip()
    auth = base64.b64encode(('nt531:'+config['GRAFANA_ADMIN_PASSWORD']).encode()).decode()

    def get(path):
        request = urllib.request.Request('http://127.0.0.1:3000'+path, headers={'Authorization':'Basic '+auth})
        with urllib.request.urlopen(request,timeout=15) as response:
            return json.load(response)

    trace = get('/api/datasources/proxy/uid/nt531-tempo/api/traces/'+trace_id)
    count = sum(len(scope.get('spans',[])) for batch in trace.get('batches',trace.get('resourceSpans',[])) for scope in batch.get('scopeSpans',[]))
    assert count==10, count
    query = '{ resource.service.name = "nt531-load" }'
    search = get('/api/datasources/proxy/uid/nt531-tempo/api/search?'+urllib.parse.urlencode(dict(q=query,start=int(time.time())-86400,end=int(time.time()),limit=50)))
    assert trace_id in [t['traceID'] for t in search['traces']], 'Trace absent from dashboard search'
    dashboard = get('/api/dashboards/uid/nt531-application-traces')
    assert dashboard['dashboard']['uid']=='nt531-application-traces'
    saved_count = sum(len((args.folder/'trace-smoke'/f'{node}.jsonl').read_text(encoding='utf-8').splitlines()) for node in 'abcd')
    result = dict(verified_utc=dt.datetime.now(dt.timezone.utc).isoformat(),collector_spans_replayed=saved_count,
        tempo_trace_id=trace_id,span_count_via_grafana_proxy=count,grafana_datasource_proxy_status=200,
        source='real AWS smoke spans replayed with original timestamps',not_live_measurement=True,
        hostmetrics_agents_installed=False,dashboard_provisioned=True,
        grafana_dashboard_search=dict(query=query,path='Grafana frontend datasource proxy /api/search',status=200,traces_returned=len(search['traces'])))
    (args.folder/'observability-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
