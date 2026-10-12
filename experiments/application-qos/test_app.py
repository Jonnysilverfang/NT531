"""Behavioral checks: parallel calls, overload, failure accounting, W3C traces."""
import importlib.util
import gzip
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('application', HERE / 'app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class ApplicationTests(unittest.TestCase):
    def test_failures_remain_in_deadline_denominator(self):
        rows = [dict(ok=True, sent=True, completion_ms=10, dispatch_lag_ms=0),
                dict(ok=True, sent=True, completion_ms=80, dispatch_lag_ms=0),
                dict(ok=False, sent=True, completion_ms=2000, dispatch_lag_ms=0),
                dict(ok=False, sent=False, completion_ms=0, dispatch_lag_ms=0)]
        summary = app.summarize(rows, 50)
        self.assertEqual(summary['deadline_success_fraction'], .25)
        self.assertEqual(summary['failed'], 2)
        self.assertEqual(summary['successful_completion_p95_ms'], 80)
        self.assertIsNone(app.percentile([], .95))

    def test_parallel_workers_overload_and_trace_propagation(self):
        with tempfile.TemporaryDirectory(dir=HERE.parents[1] / 'tmp') as temp:
            directory = Path(temp)
            processes = []
            urls = []
            try:
                for node in 'cd':
                    number = port()
                    urls.append(f'http://127.0.0.1:{number}')
                    processes.append(subprocess.Popen([sys.executable, str(HERE / 'app.py'), 'worker',
                        '--node', node, '--mode', 'local', '--port', str(number), '--worker-delay-ms', '30',
                        '--worker-slots', '1', '--test-shutdown', '--trace-file', str(directory / (node + '.jsonl')),
                        '--queue-file', str(directory / (node + '-queue.jsonl.gz'))],
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
                number = port()
                gateway = f'http://127.0.0.1:{number}'
                processes.append(subprocess.Popen([sys.executable, str(HERE / 'app.py'), 'gateway',
                    '--node', 'b', '--mode', 'local', '--port', str(number), '--workers', *urls,
                    '--test-shutdown', '--trace-file', str(directory / 'b.jsonl')], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
                for url in [*urls, gateway]:
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            urllib.request.urlopen(url + '/health', timeout=1).read()
                            break
                        except Exception:
                            if time.monotonic() > deadline:
                                self.fail('Local service did not start')
                            time.sleep(.1)
                # One slow single request plus an overloaded open-loop run.
                for label, rate, duration in [('one', '1', '1'), ('overload', '100', '.3')]:
                    subprocess.run([sys.executable, str(HERE / 'app.py'), 'load', '--node', 'a',
                        '--mode', 'local', '--url', gateway, '--rate', rate, '--duration', duration,
                        '--out', str(directory / label), '--trace-file', str(directory / 'a.jsonl')],
                        check=True, stdout=subprocess.DEVNULL, timeout=20)
                first = json.loads((directory / 'one/summary.json').read_text())
                overload = json.loads((directory / 'overload/summary.json').read_text())
                self.assertEqual(first['summary']['successful'], 1)
                self.assertEqual(overload['summary']['scheduled'], 30)
                self.assertLess(overload['summary']['deadline_success_fraction'], .5)
                self.assertGreater(overload['summary']['successful_completion_p95_ms'], 300)
                # Await batched exporter, then inspect a complete distributed trace.
                time.sleep(6)
                spans = [json.loads(line) for node in 'abcd'
                    for line in (directory / (node + '.jsonl')).read_text().splitlines()]
                root = next(s for s in spans if s['name'] == 'load.request')
                traceid = root['context']['trace_id']
                trace = [s for s in spans if s['context']['trace_id'] == traceid]
                self.assertEqual(len(trace), 10)
                names = {s['name'] for s in trace}
                self.assertTrue({'gateway.handle', 'gateway.call.c', 'gateway.call.d', 'worker.queue', 'worker.process'} <= names)
                gateway_span = next(s for s in trace if s['name'] == 'gateway.handle')
                self.assertEqual(gateway_span['parent_id'], root['context']['span_id'])
                calls = [s for s in trace if s['name'].startswith('gateway.call.')]
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(s['parent_id'] == gateway_span['context']['span_id'] for s in calls))
                self.assertLess(max(s['start_time'] for s in calls), min(s['end_time'] for s in calls), 'Worker RPCs should overlap')
                urllib.request.urlopen(urllib.request.Request(urls[1] + '/__test_stop', data=b''), timeout=2).read()
                time.sleep(.2)
                subprocess.run([sys.executable, str(HERE / 'app.py'), 'load', '--node', 'a',
                    '--mode', 'local', '--url', gateway, '--rate', '1', '--duration', '1',
                    '--out', str(directory / 'failed-worker')], check=True,
                    stdout=subprocess.DEVNULL, timeout=10)
                broken = json.loads((directory / 'failed-worker/summary.json').read_text())
                self.assertEqual(broken['summary']['successful'], 0)
                self.assertEqual(broken['summary']['deadline_success_fraction'], 0)
            finally:
                for url in [*urls, gateway]:
                    try:
                        urllib.request.urlopen(urllib.request.Request(url + '/__test_stop', data=b''), timeout=2).read()
                    except Exception:
                        pass
                for process in processes:
                    if process.poll() is None:
                        try:
                            process.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            process.terminate()
                for process in processes:
                    process.wait(timeout=10)
                    process.stderr.close()
            # Worker logs retain all entered calls, including calls whose client failed.
            for node in 'cd':
                rows = [json.loads(line) for line in gzip.decompress((directory/(node+'-queue.jsonl.gz')).read_bytes()).decode().splitlines()]
                self.assertGreaterEqual(len(rows), 31)
                self.assertTrue(all(r['request_id'] is not None and r['exit_s'] is not None for r in rows))
                completed = [r for r in rows if r['status']=='handler_completed']
                self.assertTrue(all(r['entered_s']<=r['service_start_s']<=r['service_end_s']<=r['exit_s'] for r in completed))
                self.assertGreater(max((r['service_start_s']-r['entered_s'])*1000 for r in completed), 200)


if __name__ == '__main__':
    unittest.main()
