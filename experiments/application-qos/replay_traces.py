"""Send preserved SDK spans to LOCAL OTLP/HTTP collector (JSON protocol).

Offline replay preserves original IDs/timestamps; not a live latency measurement.
"""
import argparse
import base64
import datetime as dt
import json
from pathlib import Path
import urllib.parse
import urllib.request


def nanoseconds(value):
    # Console exporter emits fixed 9-digit fractional seconds. Avoid float rounding.
    seconds, frac = value.removesuffix('Z').split('.')
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    stamp = dt.datetime.fromisoformat(seconds).replace(tzinfo=dt.timezone.utc)
    return str(int((stamp - epoch).total_seconds()) * 10**9 + int(frac.ljust(9, '0')))


def attributes(values):
    result = []
    for key, value in values.items():
        kind = 'boolValue' if isinstance(value, bool) else 'intValue' if isinstance(value, int) else 'doubleValue' if isinstance(value, float) else 'stringValue'
        result.append({'key': key, 'value': {kind: str(value) if kind == 'intValue' else value}})
    return result


def convert(span):
    # OTLP JSON IDs are hexadecimal (unlike Protobuf bytes), per OTLP spec.
    context = span['context']
    result = {'traceId': context['trace_id'].removeprefix('0x'),
        'spanId': context['span_id'].removeprefix('0x'), 'name': span['name'],
        'kind': {'INTERNAL': 1, 'SERVER': 2, 'CLIENT': 3, 'PRODUCER': 4, 'CONSUMER': 5}[span['kind'].split('.')[-1]],
        'startTimeUnixNano': nanoseconds(span['start_time']),
        'endTimeUnixNano': nanoseconds(span['end_time']),
        'attributes': attributes(span.get('attributes', {}))}
    if span.get('parent_id'):
        result['parentSpanId'] = span['parent_id'].removeprefix('0x')
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    p.add_argument('--endpoint', default='http://127.0.0.1:4318/v1/traces')
    args = p.parse_args()
    url = urllib.parse.urlparse(args.endpoint)
    assert url.hostname in ['127.0.0.1', 'localhost'] and url.scheme == 'http', 'Replay only to local collector'
    grouped = {}
    for node in 'abcd':
        for line in (args.folder / (node + '.jsonl')).read_text(encoding='utf-8').splitlines():
            span = json.loads(line)
            resource = span['resource']['attributes']
            grouped.setdefault(json.dumps(resource, sort_keys=True), []).append(convert(span))
    payload = {'resourceSpans': [{'resource': {'attributes': attributes(json.loads(resource))},
        'scopeSpans': [{'scope': {'name': 'nt531.application-qos', 'version': '1.0'}, 'spans': spans}]}
        for resource, spans in grouped.items()]}
    request = urllib.request.Request(args.endpoint, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        reply = response.read().decode()
    print(json.dumps({'spans_replayed': sum(map(len, grouped.values())), 'response': reply,
        'original_timestamps_preserved': True, 'not_live_measurement': True}))


if __name__ == '__main__':
    main()
