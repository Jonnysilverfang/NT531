"""Analytical tiny sample paths, including cancellation and truncation checks."""
import importlib.util
import json
from pathlib import Path
from decimal import Decimal as D

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('queue_audit',ROOT/'scripts/audit-queue-occupancy.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
calls=[dict(request_id='a',entered_s=D(0),service_start_s=D(1),service_end_s=D(3),exit_s=D(3),status='handler_completed'),
       dict(request_id='b',entered_s=D(1),service_start_s=None,service_end_s=None,exit_s=D(2),status='cancelled')]
r=m.account(calls,1)
assert r['mean_wait_ms']==1000 and r['mean_queue_occupancy']==2/3
assert r['mean_worker_lifetime_ms']==2000 and r['mean_system_occupancy']==4/3
assert r['cancelled_calls']==1 and r['peak_active_service_occupancy']==1
assert r['cohort_service_slot_fraction']==2/3
area,peak=m.occupancy([(D(0),D(2)),(D(1),D(3)),(D(1),D(1))],D(0),D(3))
assert area==D(4) and peak==2
try:m.occupancy([(D(0),D(4))],D(0),D(3));raise RuntimeError('Censored interval accepted')
except AssertionError:pass
calls[1]['exit_s']=None
try:m.account(calls,1);raise RuntimeError('Unfinished call accepted')
except AssertionError:pass
invalid=[dict(request_id='bad',entered_s=D(0),service_start_s=D(2),service_end_s=D(1),exit_s=D(3),status='handler_completed')]
try:m.account(invalid,1);raise RuntimeError('Reversed service accepted')
except AssertionError:pass
cancelled=[dict(request_id='cancel-serving',entered_s=D(0),service_start_s=D(1),service_end_s=None,exit_s=D(3),status='cancelled')]
r=m.account(cancelled,1)
assert r['mean_active_service_occupancy']==2/3 and r['mean_wait_ms']==1000
assert r['cancelled_calls']==1 and r['mean_service_completed_ms'] is None
print(json.dumps({'sample_path_checks':'passed','cases':['overlapping_lifetimes','cancelled_wait_retained','slot_accounting','zero_duration_ties','truncated_window_rejected','unfinished_call_rejected','reversed_service_rejected','cancelled_service_retained'],'synthetic_not_measurement':True,'AWS_calls':0}))
