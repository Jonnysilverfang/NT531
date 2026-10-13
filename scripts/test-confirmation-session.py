"""Synthetic offline guard checks; never copied into measured results or AWS."""
import importlib.util,json,shutil,tempfile,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('session',ROOT/'scripts/start-confirmation-session.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='planning-tests-') as t:
    m.ROOT=Path(t)
    for name in m.PROTOCOLS:
        folder=m.ROOT/'results'/name;folder.mkdir(parents=True)
        shutil.copyfile(ROOT/'results'/name/'protocol.json',folder/'protocol.json')
        (folder/'analysis.json').write_text(json.dumps(dict(completed_blocks=0,issues=[],rows=[],inferential_result=None)))
    assert [j['block'] for j in m.plan()]==[1,1];checks.append('eligible_initial_plan')
    folder=m.ROOT/'results/application-slots-confirmation-v1'
    outstanding=folder/'block-01/example';outstanding.mkdir(parents=True)
    file=outstanding/'attempt.json';file.write_text(json.dumps(dict(status='started')))
    try:m.plan();raise RuntimeError('Overlap accepted')
    except AssertionError as e:assert 'Unfinished' in str(e)
    checks.append('unfinished_attempt_rejected_before_AWS')
    file.write_text(json.dumps(dict(status='failed')))
    try:m.plan();raise RuntimeError('Automatic retry accepted')
    except AssertionError as e:assert 'adjudicate' in str(e)
    checks.append('automatic_measurement_retry_rejected')
    file.unlink()
    rtt=m.ROOT/'results/confirmation-rtt-v1'
    (rtt/'analysis.json').write_text(json.dumps(dict(completed_blocks=1,issues=[],rows=[dict(started_utc=dt.datetime.now(dt.timezone.utc).isoformat())],inferential_result=None)))
    try:m.plan();raise RuntimeError('Spacing violation accepted')
    except AssertionError as e:assert 'two hours' in str(e)
    checks.append('spacing_guard_uses_aware_UTC')
    (rtt/'analysis.json').write_text(json.dumps(dict(completed_blocks=0,issues=[],rows=[],inferential_result=None)))
    (rtt/'protocol.json').write_text('{}')
    try:m.plan();raise RuntimeError('Protocol edit accepted')
    except AssertionError as e:assert 'Protocol changed' in str(e)
    checks.append('frozen_protocol_edit_rejected')
print(json.dumps(dict(guard_checks='passed',checks=checks,AWS_calls=0,synthetic_inputs_not_measurements=True)))
