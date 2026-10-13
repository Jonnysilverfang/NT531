"""Offline waiting guards; synthetic clocks and plans, no AWS or measurement."""
import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT/'scripts/run-confirmation-session.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
initial = dt.datetime(2026, 10, 13, 9, 0, tzinfo=dt.timezone.utc)
clock = [initial]
jobs = [dict(study='synthetic-rtt', block=5, earliest_utc=(initial+dt.timedelta(seconds=65)).isoformat()),
        dict(study='synthetic-slots', block=3, earliest_utc=(initial+dt.timedelta(seconds=95)).isoformat())]
waits, announcements, checks = [], [], []


def sleep(seconds):
    assert 0 < seconds <= 30
    waits.append(seconds); clock[0] += dt.timedelta(seconds=seconds)


def plan(require_due=True):
    if require_due:
        assert clock[0] >= initial+dt.timedelta(seconds=95), 'Started before later block was due'
    return jobs


ready = runner.wait_for_due_jobs(lambda js, t: announcements.append((js, t)),
                                 planner=plan, now=lambda: clock[0], sleeper=sleep)
assert ready == jobs and sum(waits) == 95 and len(announcements) == 1
checks.append('waits_for_later_of_both_blocks_in_short_local_sleeps')
assert announcements[0][1] == initial+dt.timedelta(seconds=95)
checks.append('publishes_not_before_time_before_waiting')


def changed_plan(require_due=True):
    return [dict(j, block=j['block']+1) for j in jobs] if require_due else jobs


try:
    runner.wait_for_due_jobs(lambda js, t: None, planner=changed_plan, now=lambda: clock[0], sleeper=sleep)
    raise RuntimeError('Changed queued block accepted')
except RuntimeError as error:
    assert 'Queued blocks changed' in str(error)
checks.append('changed_blocks_rejected_without_prepare_or_AWS')


def failed_revalidation(require_due=True):
    if require_due:
        raise AssertionError('Synthetic quality guard failure')
    return jobs


try:
    runner.wait_for_due_jobs(lambda js, t: None, planner=failed_revalidation,
                             now=lambda: clock[0], sleeper=sleep)
    raise RuntimeError('Quality failure ignored')
except AssertionError:
    pass
checks.append('full_plan_quality_revalidated_before_start')

clock[0] = initial
waits.clear()
boot_times = []


def prewarm():
    boot_times.append(clock[0])
    clock[0] += dt.timedelta(seconds=10)


ready = runner.wait_for_due_jobs(lambda js, t: None, planner=plan, now=lambda: clock[0],
                                 sleeper=sleep, prewarm=prewarm, prewarm_seconds=60)
assert boot_times == [initial+dt.timedelta(seconds=35)]
assert clock[0] == initial+dt.timedelta(seconds=95) and ready == jobs
checks.append('early_preparation_does_not_start_measurement_before_due')
clock[0] = initial
boot_times.clear()
plan_calls = [0]


def changed_before_boot(require_due=True):
    plan_calls[0] += 1
    return jobs if plan_calls[0] == 1 else [dict(j, block=j['block']+1) for j in jobs]


try:
    runner.wait_for_due_jobs(lambda js, t: None, planner=changed_before_boot, now=lambda: clock[0],
                             sleeper=sleep, prewarm=prewarm, prewarm_seconds=60)
    raise AssertionError('Changed early boot plan accepted')
except RuntimeError as error:
    assert 'before early boot' in str(error)
assert not boot_times
checks.append('plan_revalidated_before_early_resource_action')
print(json.dumps(dict(checks=checks, status='passed', AWS_calls=0, synthetic_inputs_not_measurements=True)))
