"""One authorized session, with an exclusive local lock and cleanup in finally.

Operational wrapper only: never changes the frozen app/protocol, retries a
measurement, or generates inferential results before the existing validators.
Word rendering and Git publication remain review steps for the heartbeat.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('session', ROOT/'scripts/start-confirmation-session.py')
session = importlib.util.module_from_spec(spec); spec.loader.exec_module(session)
VENV = ROOT/'tmp/application-venv/Scripts/python.exe'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def command(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def assert_valid(study, expected):
    result = read(ROOT/'results'/study/'analysis.json')
    if result['issues'] or result['completed_blocks'] != expected:
        raise RuntimeError('Raw validation failed for '+study+'; inspect before any further block')


def measure(profile, jobs):
    for job in jobs:
        study, block = job['study'], job['block']
        if study == 'confirmation-rtt-v1':
            command([sys.executable, 'scripts/rtt-confirmation.py', '--block', block, '--profile', profile])
            command([sys.executable, 'scripts/rtt-confirmation.py', '--analyze'])
        else:
            command([sys.executable, 'scripts/application-slots.py', 'block', '--block', block, '--profile', profile])
            attempts = [p.parent for p in (ROOT/'results'/study/f'block-{block:02d}').glob('*/attempt.json')
                        if read(p)['status'] == 'complete']
            if len(attempts) != 1:
                raise RuntimeError('Expected exactly one complete slots attempt')
            folder = attempts[0]
            command([sys.executable, 'scripts/verify-slots-transfer.py', folder])
            command([VENV, 'experiments/application-qos/analyze_slots.py', '--study'])
            assert_valid(study, block)
            command([VENV, 'experiments/application-qos/plot_slots.py', folder,
                     '--figures', ROOT/'docs/images/application/confirmation'/f'block-{block:02d}'])
            # Generated SVG whitespace only; raw evidence is immutable.
            for path in (ROOT/'docs/images/application/confirmation'/f'block-{block:02d}').glob('*.svg'):
                path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
        assert_valid(study, block)
    command([sys.executable, 'scripts/update-confirmation-status.py'])


def finish(profile):
    try:
        command([sys.executable, 'scripts/pause-ec2.py', '--profile', profile])
        return {'stopped_verified': True, 'method': 'pause-ec2.py'}
    except Exception as original:
        # SSM may be unavailable: EC2 stop must not depend on SSM availability.
        command([sys.executable, 'scripts/save-session-backup.py'])
        def aws(args):
            return session.confirmation.cli(['aws', *args, '--profile', profile, '--region', 'us-east-1',
                                             '--output', 'json', '--no-cli-pager'], True)
        if aws(['sts', 'get-caller-identity'])['Account'] != '620306387033':
            raise RuntimeError('Cannot verify account for emergency stop')
        ids = list(session.EXPECTED.values())
        response = aws(['ec2', 'describe-instances', '--instance-ids', *ids])
        hosts = [h for r in response['Reservations'] for h in r['Instances']]
        if {h['InstanceId'] for h in hosts} != set(ids) or not all(
                any(t['Key']=='Project' and t['Value']=='NT531' for t in h.get('Tags', [])) for h in hosts):
            raise RuntimeError('Unexpected cohort for emergency stop')
        active = [h['InstanceId'] for h in hosts if h['State']['Name'] in ['pending', 'running']]
        if active:
            aws(['ec2', 'stop-instances', '--instance-ids', *active])
        command(['aws', 'ec2', 'wait', 'instance-stopped', '--instance-ids', *ids,
                 '--profile', profile, '--region', 'us-east-1'])
        response = aws(['ec2', 'describe-instances', '--instance-ids', *ids])
        states = {h['InstanceId']:h['State']['Name'] for r in response['Reservations'] for h in r['Instances']}
        if set(states) != set(ids) or set(states.values()) != {'stopped'}:
            raise RuntimeError('Four stopped instances not verified')
        result = {'stopped_verified': True, 'method': 'verified_ec2_stop_without_SSM',
                  'original_cleanup_error': str(original), 'states': states}
        key = ROOT/'tmp/ssh-download-private/nt531.pem'
        try:
            if key.exists():
                key.unlink()
            result['temporary_download_key_removed'] = not key.exists()
        except OSError as e:
            result['temporary_key_cleanup_error'] = str(e)
        return result


def retain_running(profile):
    """User selected manual EC2 stop: quiesce workloads and save evidence only."""
    # Local evidence must survive an expired AWS login during workload cleanup.
    backup = read_backup()
    spec = importlib.util.spec_from_file_location('deployment', ROOT/'scripts/application-qos.py')
    deployment = importlib.util.module_from_spec(spec); spec.loader.exec_module(deployment)
    exp = deployment.Experiment(profile)
    exp.stop()
    ids = list(session.EXPECTED.values())
    response = exp.aws(['ec2', 'describe-instances', '--instance-ids', *ids])
    states = {h['InstanceId']: h['State']['Name'] for r in response['Reservations'] for h in r['Instances']}
    if set(states) != set(ids):
        raise RuntimeError('Retained cohort state incomplete')
    key = ROOT/'tmp/ssh-download-private/nt531.pem'
    if key.exists():
        key.unlink()
    return {'method': 'user_selected_manual_EC2_stop', 'stopped_verified': False,
            'states': states, 'backup': backup, 'workloads_stopped': True,
            'temporary_download_key_removed': not key.exists()}


def read_backup():
    output = subprocess.check_output([sys.executable, str(ROOT/'scripts/save-session-backup.py')],
                                     cwd=ROOT, text=True)
    result = json.loads(output)
    if not result['verified']:
        raise RuntimeError('Backup not verified')
    return result


def wait_for_due_jobs(publish, planner=None, now=None, sleeper=None,
                      prewarm=None, prewarm_seconds=1865):
    """Wait locally without AWS calls; revalidate the same blocks before start."""
    planner = planner or session.plan
    now = now or (lambda: dt.datetime.now(dt.timezone.utc))
    sleeper = sleeper or time.sleep
    jobs = planner(require_due=False)
    target = max(session.utc(job['earliest_utc']) for job in jobs)
    publish(jobs, target)
    if prewarm is not None:
        warm_at = target - dt.timedelta(seconds=prewarm_seconds)
        while now() < warm_at:
            sleeper(min(30, max(0, (warm_at - now()).total_seconds())))
        # Guard failures or a changed block must be caught before any early boot.
        before_boot = planner(require_due=False)
        if [(j['study'], j['block'], j['earliest_utc']) for j in before_boot] != [
                (j['study'], j['block'], j['earliest_utc']) for j in jobs]:
            raise RuntimeError('Queued plan changed before early boot')
        prewarm()
    while now() < target:
        sleeper(min(30, max(0, (target - now()).total_seconds())))
    ready = planner()
    if [(j['study'], j['block']) for j in ready] != [(j['study'], j['block']) for j in jobs]:
        raise RuntimeError('Queued blocks changed; inspect rather than start a different measurement')
    return ready


def run(profile, planner=None, prepare=None, collect=None, cleanup=None, wait_until_due=False,
        prewarm_before_due=False, leave_ec2_running=False):
    planner = planner or session.plan
    prepare = prepare or session.start
    collect = collect or measure
    cleanup = cleanup or (retain_running if leave_ec2_running else finish)
    if prewarm_before_due and not wait_until_due:
        raise ValueError('Early boot requires --wait-until-due')
    lock = ROOT/'tmp/confirmation-session.lock'
    lock.parent.mkdir(exist_ok=True)
    # Refuse a stale lock too: inspect it, do not automatically retry or overlap.
    with lock.open('x', encoding='utf-8') as file:
        json.dump({'pid': os.getpid(), 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat()}, file)
    out = ROOT/'results/session-lifecycle'/('session-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    record = {'status': 'planning', 'pid': os.getpid(), 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'cleanup_mode': 'manual_EC2_stop' if leave_ec2_running else 'automatic_EC2_stop'}
    may_be_running = False
    prepared = False
    def save():
        out.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    try:
        if wait_until_due:
            def publish_wait(jobs, target):
                record.update(status='waiting_for_spacing', jobs=jobs, not_before_utc=target.isoformat())
                if prewarm_before_due:
                    record['prewarm_not_before_utc'] = (target-dt.timedelta(seconds=1865)).isoformat()
                save()
                print(json.dumps({'status': 'waiting_for_spacing', 'pid': os.getpid(),
                                  'not_before_utc': target.isoformat(), 'AWS_calls_while_waiting': 0,
                                  'session': str(out)}), flush=True)
            def prewarm():
                nonlocal may_be_running, prepared
                if not VENV.exists():
                    raise RuntimeError('Verified analysis runtime missing; do not start EC2')
                record['status'] = 'preparing'; save()
                may_be_running = True
                prepare(profile, require_due=False)
                prepared = True
                record['status'] = 'waiting_for_spacing_after_prewarm'; save()
            record['jobs'] = wait_for_due_jobs(publish_wait, planner=planner,
                                              prewarm=prewarm if prewarm_before_due else None)
        else:
            record['jobs'] = planner()
        if not VENV.exists():
            raise RuntimeError('Verified analysis runtime missing; do not start EC2')
        if not prepared:
            record['status'] = 'preparing'; save()
            may_be_running = True
            prepare(profile)
        record['status'] = 'measuring'; save()
        collect(profile, record['jobs'])
        record['status'] = 'validated_pending_report_review'
    except BaseException as e:
        record.update(status='failed', error=str(e), error_type=type(e).__name__)
        raise
    finally:
        if may_be_running:
            try:
                record['cleanup'] = cleanup(profile)
            except BaseException as e:
                record.update(status='manual_cleanup_failed_requires_attention' if leave_ec2_running else
                              'stop_unverified_requires_attention', cleanup_error=str(e))
        record['ended_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save()
        lock.unlink()
        print(json.dumps({'session': str(out), 'status': record['status'], 'cleanup': record.get('cleanup')}), flush=True)
        if record['status'] in ('stop_unverified_requires_attention', 'manual_cleanup_failed_requires_attention'):
            raise RuntimeError('Stop not verified; inspect session and AWS immediately' if not leave_ec2_running else
                               'Backup/workload cleanup failed; inspect session and AWS immediately')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--profile', default='nt533-lab')
    parser.add_argument('--wait-until-due', action='store_true',
                        help='Reserve one session and wait locally until both next blocks are eligible')
    parser.add_argument('--prewarm-before-due', action='store_true',
                        help='Boot the retained cohort about 31 minutes before due; never measure early')
    parser.add_argument('--leave-ec2-running', action='store_true',
                        help='User will stop EC2 manually; stop workloads and verify backup without EC2 stop calls')
    args = parser.parse_args()
    run(args.profile, wait_until_due=args.wait_until_due, prewarm_before_due=args.prewarm_before_due,
        leave_ec2_running=args.leave_ec2_running)
