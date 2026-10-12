"""Four-host synthetic RPC experiment; open-loop arrivals, explicit deadline failures.

Worker service time is an asynchronous wait representing an I/O task, not CPU work.
Only the eight worker slots are intentionally bounded. No artificial network delay.
"""
import argparse
import asyncio
import contextlib
import datetime as dt
import json
import math
from pathlib import Path
import signal
import time

import aiohttp
from aiohttp import web


def percentile(values, q):
    """Nearest-rank quantile. Empty input has no quantile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def summarize(rows, deadline_ms):
    good = [r['completion_ms'] for r in rows if r['ok']]
    return {
        'scheduled': len(rows), 'sent': sum(r['sent'] for r in rows),
        'successful': len(good), 'failed': sum(not r['ok'] for r in rows),
        'deadline_ms': deadline_ms,
        'deadline_success_count': sum(r['ok'] and r['completion_ms'] <= deadline_ms for r in rows),
        'deadline_success_fraction': sum(r['ok'] and r['completion_ms'] <= deadline_ms for r in rows) / len(rows) if rows else None,
        'successful_completion_p50_ms': percentile(good, .50),
        'successful_completion_p95_ms': percentile(good, .95),
        'successful_completion_p99_ms': percentile(good, .99),
        'dispatch_lag_p95_ms': percentile([r['dispatch_lag_ms'] for r in rows], .95),
        'quantile_scope': 'successful requests only; failures separately retained in deadline denominator',
    }


class Tracing:
    def __init__(self, args):
        self.on = args.trace_file is not None
        self.provider = None
        if not self.on:
            return
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        self.trace = trace
        self.provider = TracerProvider(resource=Resource.create({
            'service.name': 'nt531-' + args.role, 'service.instance.id': args.node,
            'nt531.mode': args.mode, 'nt531.phase': 'application-trace-smoke',
        }))
        args.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self.file = args.trace_file.open('a', encoding='utf-8')
        self.provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(
            out=self.file, formatter=lambda span: span.to_json(indent=None) + '\n')))
        if args.otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            self.provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
                endpoint=args.otlp_endpoint.rstrip('/') + '/v1/traces', timeout=3)))
        trace.set_tracer_provider(self.provider)
        self.tracer = trace.get_tracer('nt531.application-qos', '1.0')

    def span(self, name, headers=None, kind='INTERNAL', **attrs):
        if not self.on:
            return contextlib.nullcontext()
        from opentelemetry.propagate import extract
        return self.tracer.start_as_current_span(name,
            context=extract(headers) if headers is not None else None,
            kind=getattr(self.trace.SpanKind, kind), attributes=attrs)

    def headers(self):
        headers = {}
        if self.on:
            from opentelemetry.propagate import inject
            inject(headers)
        return headers

    def trace_id(self):
        if not self.on:
            return None
        return format(self.trace.get_current_span().get_span_context().trace_id, '032x')

    def close(self):
        if self.provider:
            self.provider.shutdown()
            self.file.close()


async def serve(args, tracing):
    application = web.Application()
    stop = asyncio.Event()
    slots = asyncio.Semaphore(args.worker_slots)
    async def health(_):
        return web.json_response({'role': args.role, 'node': args.node,
            'tracing': tracing.on, 'worker_delay_ms': args.worker_delay_ms,
            'worker_slots': args.worker_slots, 'response_bytes': args.response_bytes})
    application.router.add_get('/health', health)
    if args.test_shutdown:
        if args.bind != '127.0.0.1':
            raise ValueError('Test shutdown is loopback-only')
        async def shutdown(_):
            stop.set()
            return web.Response(text='stopping')
        application.router.add_post('/__test_stop', shutdown)
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=args.timeout),
        connector=aiohttp.TCPConnector(limit=0, limit_per_host=0), trust_env=False)

    async def worker(request):
        with tracing.span('worker.handle', request.headers, 'SERVER', **{'nt531.node': args.node}):
            with tracing.span('worker.queue'):
                await slots.acquire()
            try:
                with tracing.span('worker.process', **{'nt531.synthetic_wait_ms': args.worker_delay_ms}):
                    await asyncio.sleep(args.worker_delay_ms / 1000)
                return web.Response(body=b'x' * args.response_bytes,
                    headers={'X-NT531-Node': args.node})
            finally:
                slots.release()

    async def fetch(url, node):
        with tracing.span('gateway.call.' + node, kind='CLIENT', **{'server.address': url}):
            async with session.get(url + '/work', headers=tracing.headers()) as response:
                body = await response.read()
                if response.status != 200 or len(body) != args.response_bytes or response.headers.get('X-NT531-Node') != node:
                    raise ValueError('Invalid worker result ' + node)
                return len(body)

    async def gateway(request):
        with tracing.span('gateway.handle', request.headers, 'SERVER'):
            tasks = [asyncio.create_task(fetch(url, node)) for node, url in zip(('c', 'd'), args.workers)]
            try:
                sizes = await asyncio.gather(*tasks)
                return web.json_response({'ok': True, 'workers': ['c', 'd'], 'bytes': sizes})
            except Exception as e:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                return web.json_response({'ok': False, 'error': type(e).__name__}, status=502)

    application.router.add_get('/work' if args.role == 'worker' else '/aggregate',
        worker if args.role == 'worker' else gateway)
    runner = web.AppRunner(application, access_log=None)
    try:
        await runner.setup()
        await web.TCPSite(runner, args.bind, args.port).start()
        print(json.dumps({'ready': args.node, 'port': args.port, 'tracing': tracing.on}), flush=True)
        try:
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
        except NotImplementedError:
            pass
        await stop.wait()
    finally:
        await runner.cleanup()
        await session.close()


async def load(args, tracing):
    count = int(args.rate * args.duration)
    rows = []
    inflight = set()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    origin = time.perf_counter() + .2
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=args.timeout),
        connector=aiohttp.TCPConnector(limit=0, limit_per_host=0), trust_env=False) as session:
        async def request(number, due):
            dispatched = time.perf_counter()
            row = {'id': number, 'scheduled_s': number / args.rate,
                'dispatch_lag_ms': max(0, (dispatched - due) * 1000),
                'sent': True, 'ok': False, 'status': None, 'error': None}
            with tracing.span('load.request', kind='CLIENT', **{'nt531.request': number}):
                row['trace_id'] = tracing.trace_id()
                try:
                    async with session.get(args.url + '/aggregate', headers=tracing.headers()) as response:
                        row['status'] = response.status
                        body = await response.json()
                        row['ok'] = response.status == 200 and body.get('ok') is True and body.get('workers') == ['c', 'd'] and body.get('bytes') == [args.response_bytes] * 2
                        if not row['ok']:
                            row['error'] = 'invalid_result_or_http_error'
                except Exception as e:
                    row['error'] = type(e).__name__
                row['completion_ms'] = max(0, (time.perf_counter() - due) * 1000)
                row['wire_and_application_ms'] = (time.perf_counter() - dispatched) * 1000
                rows.append(row)
        for number in range(count):
            due = origin + number / args.rate
            await asyncio.sleep(max(0, due - time.perf_counter()))
            if len(inflight) >= args.maximum_inflight:
                now = time.perf_counter()
                rows.append({'id': number, 'scheduled_s': number / args.rate,
                    'dispatch_lag_ms': max(0, (now - due) * 1000), 'sent': False,
                    'ok': False, 'status': None, 'error': 'generator_inflight_limit',
                    'completion_ms': max(0, (now - due) * 1000),
                    'wire_and_application_ms': None, 'trace_id': None})
                continue
            task = asyncio.create_task(request(number, due))
            inflight.add(task)
            task.add_done_callback(inflight.discard)
        if inflight:
            await asyncio.gather(*inflight)
    rows.sort(key=lambda row: row['id'])
    assert len(rows) == count
    args.out.mkdir(parents=True, exist_ok=False)
    result = {'started_utc': started, 'ended_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'mode': args.mode, 'rate_rps': args.rate, 'duration_seconds': args.duration,
        'tracing': tracing.on, 'summary': summarize(rows, args.deadline_ms),
        'config': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        'generator_valid': not any(r['error'] == 'generator_inflight_limit' for r in rows)
            and percentile([r['dispatch_lag_ms'] for r in rows], .95) <= 5}
    (args.out / 'requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    (args.out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


def parser():
    p = argparse.ArgumentParser()
    p.add_argument('role', choices=['worker', 'gateway', 'load'])
    p.add_argument('--node', required=True, choices=list('abcd'))
    p.add_argument('--mode', required=True, choices=['peering', 'tgw', 'local'])
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8081)
    p.add_argument('--workers', nargs=2, default=['http://10.30.10.212:8081', 'http://10.40.10.155:8081'])
    p.add_argument('--url', default='http://10.20.10.155:8080')
    p.add_argument('--worker-delay-ms', type=float, default=10)
    p.add_argument('--worker-slots', type=int, default=8)
    p.add_argument('--response-bytes', type=int, default=4096)
    p.add_argument('--rate', type=int, default=10)
    p.add_argument('--duration', type=float, default=10)
    p.add_argument('--deadline-ms', type=float, default=50)
    p.add_argument('--timeout', type=float, default=2)
    p.add_argument('--maximum-inflight', type=int, default=2000)
    p.add_argument('--out', type=Path)
    p.add_argument('--trace-file', type=Path)
    p.add_argument('--otlp-endpoint')
    p.add_argument('--test-shutdown', action='store_true', help=argparse.SUPPRESS)
    return p


if __name__ == '__main__':
    args = parser().parse_args()
    if args.rate <= 0 or args.duration <= 0 or args.worker_slots <= 0 or args.response_bytes <= 0 or args.maximum_inflight <= 0 or args.worker_delay_ms < 0 or args.timeout <= 0 or args.deadline_ms <= 0:
        raise SystemExit('All settings must be positive (worker delay may be zero)')
    if args.role == 'load' and (args.out is None or int(args.rate * args.duration) < 1):
        raise SystemExit('Load requires --out and at least one scheduled request')
    tracing = Tracing(args)
    try:
        asyncio.run(load(args, tracing) if args.role == 'load' else serve(args, tracing))
    except KeyboardInterrupt:
        pass
    finally:
        tracing.close()
