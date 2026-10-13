"""Offline operational failure tests: no AWS calls or measurement data."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT/'scripts/run-confirmation-session.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
with tempfile.TemporaryDirectory(dir=ROOT/'tmp', prefix='cleanup-tests-') as temp:
    m.ROOT = Path(temp)
    calls = []
    planner = lambda: [{'study':'synthetic', 'block':1}]
    cleanup = lambda profile: calls.append('stop') or {'stopped_verified':True}
    def failed(profile):
        calls.append('prepare'); raise RuntimeError('Synthetic preparation failure')
    try:
        m.run('synthetic', planner=planner, prepare=failed, cleanup=cleanup)
    except RuntimeError:
        pass
    assert calls == ['prepare', 'stop']
    checks.append('preparation_failure_still_stops')
    calls.clear()
    def collect_failed(profile, jobs):
        calls.append('collect'); raise RuntimeError('Synthetic measurement failure')
    try:
        m.run('synthetic', planner=planner, prepare=lambda p:calls.append('prepare'), collect=collect_failed, cleanup=cleanup)
    except RuntimeError:
        pass
    assert calls == ['prepare', 'collect', 'stop']
    checks.append('measurement_failure_stops_without_retry')
    calls.clear()
    def bad_plan():
        raise RuntimeError('Synthetic not due')
    try:
        m.run('synthetic', planner=bad_plan, prepare=failed, cleanup=cleanup)
    except RuntimeError:
        pass
    assert calls == []
    checks.append('failed_offline_plan_never_touches_AWS')
    lock = m.ROOT/'tmp/confirmation-session.lock'
    lock.write_text('{}')
    try:
        m.run('synthetic', planner=planner, prepare=failed, cleanup=cleanup)
        raise AssertionError('Overlap accepted')
    except FileExistsError:
        pass
    assert calls == [] and lock.exists()
    checks.append('existing_lock_prevents_any_resource_action')
    lock.unlink()
    def cleanup_failed(profile):
        raise RuntimeError('Synthetic expired AWS login')
    try:
        m.run('synthetic', planner=planner, prepare=lambda p:None, collect=lambda p,j:None, cleanup=cleanup_failed)
        raise AssertionError('Cleanup failure hidden')
    except RuntimeError as e:
        assert 'Stop not verified' in str(e)
    records = [json.loads(p.read_text()) for p in (m.ROOT/'results/session-lifecycle').glob('session-*.json')]
    assert sum(r['status']=='stop_unverified_requires_attention' for r in records) == 1
    checks.append('cleanup_failure_reported_without_false_stopped_claim')
print(json.dumps({'offline_cleanup_checks':'passed','checks':checks,'AWS_calls':0,'synthetic_inputs_not_measurements':True}))
