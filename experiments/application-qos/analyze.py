"""Verify complete pilot raw data and distributed trace topology; no inferential p-values."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('application', HERE / 'app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def analyze(folder):
    record = json.loads((folder / 'attempt.json').read_text(encoding='utf-8'))
    issues, rows, sources = [], [], []
    if record['status'] != 'complete' or record['cleanup_errors']:
        issues.append('Attempt not complete or cleanup failed')
    for filename, key in [('app.py','application_sha256'), ('requirements.txt','requirements_sha256'),
                          ('pilot.json','protocol_sha256'), ('runner-source.py','runner_sha256')]:
        path = folder / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != record[key]:
            issues.append('Archived source hash mismatch: ' + filename)
        sources.append({'path': filename, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    packages = []
    for node in 'abcd':
        text = (folder / f'preflight-{node}.txt').read_text(encoding='utf-8')
        packages.append(sorted(line for line in text.splitlines() if '==' in line))
    if any(p != packages[0] for p in packages):
        issues.append('Dependency versions differ across nodes')
    for mode in record['order']:
        routing = record['routing_context']
        for name in ['routes-before.json', 'routes-after.json']:
            path = folder / mode / name
            state = json.loads(path.read_text(encoding='utf-8'))
            for source, target in [('a','b'),('b','a'),('b','c'),('c','b'),('b','d'),('d','b')]:
                table = next(t for t in state['RouteTables'] if t['RouteTableId'] == routing[f'route_table_{source}_id'])
                route = next(r for r in table['Routes'] if r.get('DestinationCidrBlock') == f"10.{dict(a=10,b=20,c=30,d=40)[target]}.0.0/16")
                pair = ''.join(sorted([source,target]))
                expected = routing['transit_gateway_id'] if mode == 'tgw' else routing['peering_id'] if pair == 'ab' else routing['cross_peering_ids'][pair]
                if route['State'] != 'active' or route.get('TransitGatewayId' if mode == 'tgw' else 'VpcPeeringConnectionId') != expected:
                    issues.append(f'{mode}: wrong route {source} {target}')
            sources.append({'path': str(path.relative_to(folder)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for rate in record['protocol']['rates_rps']:
            path = folder / mode / f'rate-{rate}'
            summary = json.loads((path / 'summary.json').read_text(encoding='utf-8'))
            requests = [json.loads(line) for line in gzip.decompress((path / 'requests.jsonl.gz').read_bytes()).decode().splitlines()]
            if len(requests) != int(rate * record['protocol']['duration_seconds']) or [r['id'] for r in requests] != list(range(len(requests))):
                issues.append(f'{mode} {rate}: missing or duplicate requests')
            calculated = app.summarize(requests, record['protocol']['deadline_ms'])
            if calculated != summary['summary'] or summary['mode'] != mode or summary['tracing']:
                issues.append(f'{mode} {rate}: raw/summary mismatch or tracing in comparison')
            if not summary['generator_valid']:
                issues.append(f'{mode} {rate}: generator timing/inflight invalid')
            rows.append(dict(mode=mode, rate_rps=rate, generator_valid=summary['generator_valid'], **calculated))
            for file in [path / 'summary.json', path / 'requests.jsonl.gz']:
                sources.append({'path': str(file.relative_to(folder)), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    spans = [json.loads(line) for node in 'abcd' for line in (folder / 'trace-smoke' / (node + '.jsonl')).read_text(encoding='utf-8').splitlines()]
    roots = [s for s in spans if s['name'] == 'load.request']
    trace_checks = []
    for root in roots:
        traceid = root['context']['trace_id']
        linked = [s for s in spans if s['context']['trace_id'] == traceid]
        ids = {s['context']['span_id'] for s in linked}
        names = {s['name'] for s in linked}
        valid = (len(linked) == 10 and all(s.get('parent_id') in ids for s in linked if s != root)
            and {'gateway.handle','gateway.call.c','gateway.call.d','worker.queue','worker.process'} <= names
            and {s['resource']['attributes']['service.instance.id'] for s in linked} == set('abcd'))
        trace_checks.append({'trace_id': traceid.removeprefix('0x'), 'spans': len(linked), 'valid': valid})
    if len(trace_checks) != 6 or not all(t['valid'] for t in trace_checks):
        issues.append('Trace smoke missing complete six-request four-node topology')
    for node in 'abcd':
        file = folder / 'trace-smoke' / (node + '.jsonl')
        sources.append({'path': str(file.relative_to(folder)), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        for mode in record['order']:
            file = folder / mode / f'monitor-{node}.json.gz'
            data = json.loads(gzip.decompress(file.read_bytes()))
            if not all(data.get(k) for k in ['cpu.txt', 'ena-before.txt', 'ena-after.txt']):
                issues.append(f'{mode} {node}: missing CPU/ENA')
            sources.append({'path': str(file.relative_to(folder)), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    comparison = []
    for rate in record['protocol']['rates_rps']:
        peering = next(r for r in rows if r['mode'] == 'peering' and r['rate_rps'] == rate)
        tgw = next(r for r in rows if r['mode'] == 'tgw' and r['rate_rps'] == rate)
        p95p, p95t = peering['successful_completion_p95_ms'], tgw['successful_completion_p95_ms']
        comparison.append({'rate_rps': rate, 'tgw_minus_peering_p95_ms': p95t - p95p if p95p is not None and p95t is not None else None,
            'tgw_minus_peering_deadline_success_percentage_points': 100*(tgw['deadline_success_fraction'] - peering['deadline_success_fraction'])})
    result = {'phase': record['protocol']['phase'], 'issues': issues, 'rows': rows, 'comparison': comparison,
        'traces': trace_checks, 'sources': sources, 'inferential_result': None,
        'scope': 'One paired pilot session, deterministic open-loop arrivals. No service capacity, superiority or equivalence conclusion.'}
    (folder / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'issues': issues, 'rows': rows, 'traces_valid': all(t['valid'] for t in trace_checks)}))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    args = p.parse_args()
    analyze(args.folder)
