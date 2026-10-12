"""Synthetic unit checks for inference and AWS mutation guards. No AWS calls."""
import importlib.util,json,copy
from pathlib import Path
path=Path(__file__).with_name('rtt-confirmation.py')
spec=importlib.util.spec_from_file_location('rtt_confirmation',path)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def rejected(fn,*args):
    try:fn(*args)
    except (AssertionError,ValueError,StopIteration):return
    raise AssertionError('Invalid input was accepted')

r.self_test()
def capture(avg):
    return {'runs':[{'exit_code':0,'stdout':f'100 packets transmitted, 100 received, 0% packet loss\nrtt min/avg/max/mdev = 0.1/{avg}/0.9/0.1 ms\n'} for _ in range(3)]}
t,_=r.parse_capture(capture('0.300'));p,_=r.parse_capture(capture('0.200'))
assert float(t-p)==.1
assert r.statistics([float(t-p)]*16)['above_margin_blocks']==0
rejected(r.parse_capture,{'runs':[{'exit_code':2,'stdout':'failed'}]*3})
plan={'resource_changes':[{'mode':'managed','type':'aws_route','change':{'actions':['update'],
      'before':{'route_table_id':'rt-a','destination_cidr_block':'10.20.0.0/16'},
      'after':{'route_table_id':'rt-a','destination_cidr_block':'10.20.0.0/16'}}}]}
r.validate_route_plan(plan,{'rt-a'})
for typ,actions in [('aws_instance',['create']),('aws_route',['delete']),('aws_eip',['update'])]:
    changed=copy.deepcopy(plan);changed['resource_changes'][0]['type']=typ;changed['resource_changes'][0]['change']['actions']=actions
    rejected(r.validate_route_plan,changed,{'rt-a'})
changed=copy.deepcopy(plan)
for phase in ['before','after']:changed['resource_changes'][0]['change'][phase]['destination_cidr_block']='0.0.0.0/0'
rejected(r.validate_route_plan,changed,{'rt-a'})
rejected(r.validate_route_plan,plan,{'another-table'})
context={'route_table_a_id':'rt-a','route_table_b_id':'rt-b','peering_id':'pcx-ab','transit_gateway_id':'tgw'}
state={'RouteTables':[{'RouteTableId':f'rt-{node}','Routes':[{'DestinationCidrBlock':target,'State':'active','VpcPeeringConnectionId':'pcx-ab'}]}
       for node,target in [('a','10.20.0.0/16'),('b','10.10.0.0/16')]]}
r.verify_routes(state,'peering',context);rejected(r.verify_routes,state,'tgw',context)
state['RouteTables'][0]['Routes'][0]['State']='blackhole';rejected(r.verify_routes,state,'peering',context)
print(json.dumps({'inference_guards_and_decimal_ties':'passed','route_only_mutation_guards':'passed',
                  'route_label_and_blackhole_checks':'passed','data':'synthetic_test_cases_only_not_measurements'}))
