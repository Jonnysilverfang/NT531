"""Freeze, collect and analyze a fresh 16-block paired RTT confirmation study.

Uses standard library. AWS collection needs local Terraform state and AWS CLI.
No resource allocation; route-only plans, Online A/B required, original mode restored.
"""
from pathlib import Path
from decimal import Decimal
import argparse,base64,datetime as dt,gzip,hashlib,json,math,os,random,re,statistics as st,subprocess,time,uuid

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/confirmation-rtt-v1'
PROTOCOL=STUDY/'protocol.json'
TF=ROOT/'infra/terraform'
ALPHA=.05

def tail(n,k,p=.5):
    return sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k,n+1))

def lower_probability(n,k):
    if k==0:return 0.
    lo,hi=0.,1.
    for _ in range(90):
        middle=(lo+hi)/2
        if tail(n,k,middle)<ALPHA:lo=middle
        else:hi=middle
    return (lo+hi)/2

def init():
    if PROTOCOL.exists():raise ValueError('Protocol already frozen; do not overwrite or reshuffle')
    STUDY.mkdir(parents=True,exist_ok=True)
    seed=int.from_bytes(os.urandom(8),'big')
    order=['peering','tgw']*8
    random.Random(seed).shuffle(order)
    protocol={'id':'rtt-confirmation-v1','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
              'primary':'P(block RTT_TGW - RTT_Peering > 0.1 ms) exceeds 0.5',
              'alpha':ALPHA,'minimum_relevant_difference_ms':.1,'blocks':16,'runs_per_mode':3,
              'packets_per_run':100,'interval_seconds':.2,'payload_bytes':56,'timeout_seconds':2,
              'settle_seconds':30,'warmup_packets':10,'rest_seconds':5,
              'minimum_gap_between_block_starts_seconds':7200,'minimum_distinct_local_dates':4,
              'maximum_pair_span_seconds':1200,'timezone':'Asia/Saigon','seed':seed,
              'schedule':[{'block':i+1,'order':[mode,'tgw' if mode=='peering' else 'peering']} for i,mode in enumerate(order)],
              'stopping_rule':'Collect all 16 valid paired blocks. No significance-based early stop.',
              'technical_retry_rule':'Retain failed attempts. No automatic retry; whole block repeated only for documented technical failure, not RTT/outlier magnitude.',
              'scope':'Same c6i.large A/B, us-east-1a, MTU1500, no benchmark load. Historical sessions excluded.',
              'assumptions':'Inference conditional on sufficiently independent blocks and suitable sampling process; spacing does not prove independence.'}
    PROTOCOL.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'protocol':str(PROTOCOL),'sha256':digest(PROTOCOL),'status':'frozen_no_measurements'}))

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def instant(text):return dt.datetime.fromisoformat(text.replace('Z','+00:00'))

def verify_routes(state,mode,routing):
    for node,target in [('a','10.20.0.0/16'),('b','10.10.0.0/16')]:
        table=next(t for t in state['RouteTables'] if t['RouteTableId']==routing[f'route_table_{node}_id'])
        r=next(r for r in table['Routes'] if r.get('DestinationCidrBlock')==target)
        assert r['State']=='active'
        key='VpcPeeringConnectionId' if mode=='peering' else 'TransitGatewayId'
        assert r.get(key)==(routing['peering_id'] if mode=='peering' else routing['transit_gateway_id'])

def parse_capture(j):
    assert len(j['runs'])==3
    values=[];lost=0
    for row in j['runs']:
        assert row['exit_code'] in (0,1)
        s=re.search(r'(\d+) packets transmitted, (\d+) received, ([\d.]+)% packet loss',row['stdout'])
        r=re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms',row['stdout'])
        assert s and int(s[1])==100 and r,'Missing summary or all replies lost'
        lost+=100-int(s[2]);values.append(Decimal(r[2]))
    return st.mean(values),lost

def statistics(differences,delta=.1):
    n=len(differences);k=sum(d>delta for d in differences)
    ordered=sorted(differences)
    ranks=[r for r in range(1,n+1) if sum(math.comb(n,j) for j in range(r))/2**n<=ALPHA]
    rank=max(ranks) if ranks else None
    return {'n_blocks':n,'above_margin_blocks':k,'mean_difference_ms':st.mean(differences),
            'median_difference_ms':st.median(differences),'one_sided_exact_p':tail(n,k),
            'probability_lower_one_sided_95':lower_probability(n,k),
            'median_lower_ms':ordered[rank-1] if rank else None,
            'median_lower_nominal_coverage_continuous':1-sum(math.comb(n,j) for j in range(rank))/2**n if rank else None,
            'reject_primary_null':tail(n,k)<=ALPHA}

def analyze():
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'));h=digest(PROTOCOL)
    rows=[];issues=[];provenance=[]
    for block in range(1,17):
        folders=list((STUDY/f'block-{block:02d}').glob('*/complete.json'))
        if not folders:continue
        if len(folders)!=1:
            issues.append(f'block {block}: multiple complete attempts require adjudication');continue
        record=json.loads(folders[0].read_text(encoding='utf-8'))
        try:
            assert record['protocol_hash']==h and record['block']==block
            assert record['order']==p['schedule'][block-1]['order']
            captures={}
            for mode in record['order']:
                file=folders[0].parent/f'{mode}/capture.json'
                j=json.loads(file.read_text(encoding='utf-8'))
                assert j['mode']==mode and j['block']==block and j['protocol_hash']==h
                assert instant(j['started_utc'])>=instant(p['created_utc'])
                for snapshot in ['routes-before.json','routes-after.json']:
                    path=file.parent/snapshot
                    verify_routes(json.loads(path.read_text(encoding='utf-8')),mode,record['routing_context'])
                    provenance.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path)})
                captures[mode]=j
                provenance.append({'path':file.relative_to(ROOT).as_posix(),'sha256':digest(file)})
            pm,pl=parse_capture(captures['peering']);tm,tl=parse_capture(captures['tgw'])
            rows.append({'block':block,'order':record['order'],'started_utc':record['started_utc'],
                         'span_seconds':(instant(record['ended_utc'])-instant(record['started_utc'])).total_seconds(),
                         'peering_ms':float(pm),'tgw_ms':float(tm),'difference_ms':float(tm-pm),'missing_replies':pl+tl,
                         'cohort_ids':sorted(e['InstanceId'] for e in record['instance_environment']),
                         'tgw_id':record['routing_context']['transit_gateway_id']})
            provenance.append({'path':folders[0].relative_to(ROOT).as_posix(),'sha256':digest(folders[0])})
        except (AssertionError,KeyError,ValueError,StopIteration,FileNotFoundError) as e:issues.append(f'block {block}: invalid capture {str(e)}')
    ordered=sorted(rows,key=lambda r:r['started_utc'])
    gaps=[(instant(b['started_utc'])-instant(a['started_utc'])).total_seconds() for a,b in zip(ordered,ordered[1:])]
    dates={ (instant(r['started_utc'])+dt.timedelta(hours=7)).date().isoformat() for r in rows}
    if any(g<7200 for g in gaps):issues.append('Block start spacing below frozen 2-hour rule')
    if any(r['span_seconds']>1200 for r in rows):issues.append('Paired block spans more than frozen 20-minute limit')
    if len(rows)==16 and len(dates)<4:issues.append('Fewer than four local dates')
    if any(r['missing_replies'] for r in rows):issues.append('Missing ICMP replies: latency conditional on response; automated conclusion withheld')
    if rows and any((r['cohort_ids'],r['tgw_id'])!=(rows[0]['cohort_ids'],rows[0]['tgw_id']) for r in rows):
        issues.append('Endpoint/TGW identity changed between blocks; separate cohorts instead of pooling')
    full=len(rows)==16 and not issues
    result={'protocol_hash':h,'completed_blocks':len(rows),'required_blocks':16,'local_dates':sorted(dates),
            'issues':issues,'rows':rows,'sources':provenance,'inferential_result':None,
            'status':'incomplete_no_inferential_conclusion','assumptions':p['assumptions']}
    if full:
        result['inferential_result']=statistics([r['difference_ms'] for r in rows])
        result['status']='full_study_analyzed_conditional_on_assumptions'
        result['by_order']={}
        for mode in ['peering','tgw']:
            ds=[r['difference_ms'] for r in rows if r['order'][0]==mode]
            result['by_order'][mode]={'n':len(ds),'mean_difference_ms':st.mean(ds),'median_difference_ms':st.median(ds),
                                     'min_difference_ms':min(ds),'max_difference_ms':max(ds)}
        result['in_both_orders_above_margin']=all(v['median_difference_ms']>.1 for v in result['by_order'].values())
    STUDY.mkdir(parents=True,exist_ok=True)
    (STUDY/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'completed_blocks':len(rows),'issues':issues,'inferential_result':result['inferential_result']}))

def cli(args,json_output=False):
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1',AWS_PAGER='')
    p=subprocess.run(args,capture_output=True,encoding='utf-8',env=env)
    if p.returncode:raise RuntimeError(f'{args[0]} failed: {p.stderr[-1200:]}')
    return json.loads(p.stdout) if json_output else p.stdout

def validate_route_plan(j,expected_tables):
    for r in j.get('resource_changes',[]):
        change=r['change'];actions=change['actions']
        if actions==['no-op']:continue
        assert r['mode']=='managed' and r['type']=='aws_route' and actions==['update'],'Refuse non-route mutation or resource allocation'
        before,after=change['before'],change['after']
        assert before['route_table_id']==after['route_table_id'] and after['route_table_id'] in expected_tables
        assert before['destination_cidr_block']==after['destination_cidr_block'] and after['destination_cidr_block'] in [f'10.{n}.0.0/16' for n in [10,20,30,40]]

def run_block(block,profile,load=False):
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'));h=digest(PROTOCOL)
    assert 1<=block<=16
    aws=lambda args:cli(['aws',*args,'--profile',profile,'--region','us-east-1','--output','json','--no-cli-pager'],True)
    assert aws(['sts','get-caller-identity'])['Account']=='620306387033'
    outputs=cli(['terraform',f'-chdir={TF}','output','-json'],True)
    original=outputs['routing']['value']['mode'];routing=outputs['routing']['value'];instances=outputs['instances']['value']
    assert routing.get('transit_gateway_id'),'Existing TGW required; this script must not create one'
    assert instances['a']['private_ip']=='10.10.10.212' and instances['b']['private_ip']=='10.20.10.155'
    ec2=aws(['ec2','describe-instances','--instance-ids',instances['a']['id'],instances['b']['id']])
    environments=[{key:value for key,value in x.items() if key in ['InstanceId','InstanceType','ImageId','Placement','PrivateIpAddress','State']}
                  for reservation in ec2['Reservations'] for x in reservation['Instances']]
    assert len(environments)==2 and all(e['InstanceType']=='c6i.large' and e['Placement']['AvailabilityZone']=='us-east-1a' and e['State']['Name']=='running' for e in environments)
    assert len({e['ImageId'] for e in environments})==1
    online=aws(['ssm','describe-instance-information'])['InstanceInformationList']
    for node in ['a','b']:
        assert any(x['InstanceId']==instances[node]['id'] and x['PingStatus']=='Online' for x in online),f'{node} must be Online; start existing EC2 before collecting'
    if load:
        analyze()
        analysis=json.loads((STUDY/'analysis.json').read_text(encoding='utf-8'))
        assert analysis['protocol_hash']==h and analysis['completed_blocks']==16 and not analysis['issues'],'Finish all 16 confirmation blocks before exploratory load phase'
        assert sorted(e['InstanceId'] for e in environments)==analysis['rows'][0]['cohort_ids'] and routing['transit_gateway_id']==analysis['rows'][0]['tgw_id'],'Loaded phase requires the same confirmation cohort'
    previous=[] if load else list(STUDY.glob('block-*/*/complete.json'))
    for file in previous:
        old=json.loads(file.read_text(encoding='utf-8'))
        assert old['block']!=block,'Block already complete; do not overwrite or choose a faster repeat'
        assert (dt.datetime.now(dt.timezone.utc)-instant(old['started_utc'])).total_seconds()>=7200,'Wait at least two hours between blocks'
    attempt=uuid.uuid4().hex
    out=(ROOT/'results/rtt-load-exploratory-v1'/attempt) if load else STUDY/f'block-{block:02d}'/attempt
    out.mkdir(parents=True)
    temp=ROOT/'tmp/rtt-confirmation';temp.mkdir(parents=True,exist_ok=True)
    expected_tables={routing[f'route_table_{n}_id'] for n in 'abcd'}
    def switch(mode):
        plan=temp/f'{attempt}-{mode}.tfplan'
        cli(['terraform',f'-chdir={TF}','plan','-input=false','-no-color',f'-var=routing_mode={mode}','-var=enable_transit_gateway=true',f'-out={plan}'])
        j=cli(['terraform',f'-chdir={TF}','show','-json',str(plan)],True)
        validate_route_plan(j,expected_tables)
        cli(['terraform',f'-chdir={TF}','apply','-input=false','-no-color',str(plan)])
    def routes(mode,destination):
        state=aws(['ec2','describe-route-tables','--route-table-ids',routing['route_table_a_id'],routing['route_table_b_id']])
        verify_routes(state,mode,routing)
        destination.write_text(json.dumps(state,indent=2)+'\n')
    def remote(node,commands):
        request={'DocumentName':'AWS-RunShellScript','InstanceIds':[instances[node]['id']],
                 'Parameters':{'commands':commands,'executionTimeout':['240']},'TimeoutSeconds':240,
                 'Comment':f'NT531 confirm RTT block {block} {node}'}
        file=temp/f'{attempt}-{node}-{uuid.uuid4().hex}.json';file.write_text(json.dumps(request),encoding='utf-8')
        sent=aws(['ssm','send-command','--cli-input-json',f'file://{file}']);command_id=sent['Command']['CommandId']
        deadline=time.monotonic()+270
        while time.monotonic()<deadline:
            try:reply=aws(['ssm','get-command-invocation','--command-id',command_id,'--instance-id',instances[node]['id']])
            except RuntimeError as e:
                if 'InvocationDoesNotExist' not in str(e):raise
                time.sleep(3);continue
            if reply['Status'] in ['Success','Failed','TimedOut','Cancelled']:
                if reply['Status']!='Success':raise RuntimeError(f"SSM {node} {reply['Status']}: {reply.get('StandardErrorContent','')[:500]}")
                return reply['StandardOutputContent']
            time.sleep(3)
        raise TimeoutError(f'SSM {command_id}; inspect before any retry')
    record={'block':block,'attempt':attempt,'protocol_hash':h,'order':p['schedule'][block-1]['order'],
            'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'started',
            'routing_context':{k:routing[k] for k in ['route_table_a_id','route_table_b_id','peering_id','transit_gateway_id']},
            'instance_environment':environments}
    routes(original,out/'routes-initial.json')
    (out/'attempt.json').write_text(json.dumps(record,indent=2))
    try:
        for node in ['a','b']:
            preflight=remote(node,['set -eu','ip link set dev ens5 mtu 1500',
                            'test "$(timedatectl show -p NTPSynchronized --value)" = yes',
                            "ss -Htn state established | grep -E ':520[123]([^0-9]|$)' && exit 4 || test $? -eq 1",
                            'uname -r','ip -4 -o addr show dev ens5','mpstat -P ALL 1 1'])
            (out/f'preflight-{node}.txt').write_text(preflight,encoding='utf-8')
        collector_name='collect-rtt-under-load.py' if load else 'collect-confirmation-rtt.py'
        collector=base64.b64encode((ROOT/'scripts'/collector_name).read_bytes()).decode()
        if load:remote('b',['set -eu','systemctl is-active --quiet nt531-iperf@5201'])
        for mode in record['order']:
            folder=out/mode;folder.mkdir()
            print(f'Block {block}: switch {mode}, settle 30 s, then 3 ping runs',flush=True)
            switch(mode);routes(mode,folder/'routes-before.json');time.sleep(30)
            if load:
                # Exploratory order is fixed before this phase; no p-values across these 18 runs.
                for run in range(1,4):
                    for rate in [0,250,500]:
                        print(f'RTT load: {mode}, run {run}, target {rate} Mbps',flush=True)
                        text=remote('a',['set -eu',f"printf '%s' '{collector}' | base64 -d > /home/ec2-user/{collector_name}",
                            f"runuser -l ec2-user -c 'python3 /home/ec2-user/{collector_name} --mode {mode} --run {run} --rate-mbps {rate}'"])
                        raw=gzip.decompress(base64.b64decode(text.strip(),validate=True));assert len(raw)<200000
                        (folder/f'run-{run}-rate-{rate}.json').write_bytes(raw)
                        time.sleep(5)
            else:
                text=remote('a',['set -eu',f"printf '%s' '{collector}' | base64 -d > /home/ec2-user/{collector_name}",
                    f"runuser -l ec2-user -c 'python3 /home/ec2-user/{collector_name} --mode {mode} --block {block} --protocol-hash {h} --attempt {attempt}'"])
                raw=gzip.decompress(base64.b64decode(text.strip(),validate=True));assert len(raw)<200000
                (folder/'capture.json').write_bytes(raw)
                capture=json.loads(raw);parse_capture(capture)
            routes(mode,folder/'routes-after.json')
        record['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat();record['status']='complete'
        (out/'complete.json').write_text(json.dumps(record,indent=2)+'\n')
    except Exception as e:
        record['status']='failed';record['error']=str(e)
        (out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
        raise
    finally:
        print(f'Restore original route mode: {original}',flush=True)
        switch(original)
    if not load:analyze()
    else:print(json.dumps({'exploratory_loaded_RTT_folder':str(out),'no_confirmatory_p_values':True}))

def self_test():
    assert tail(16,12)==2517/65536 and tail(16,11)>.05
    assert tail(16,16)==1/65536
    assert lower_probability(16,12)>.5 and lower_probability(16,11)<.5
    assert abs(lower_probability(16,16)-.05**(1/16))<1e-12
    assert statistics([.2]*16)['median_lower_ms']==.2
    assert not statistics([.1]*16)['reject_primary_null']
    print(json.dumps({'self_tests':'passed','critical_successes_16':12,'null_tail_at_12':tail(16,12),
                      'power_if_success_probability_0_8':tail(16,12,.8),'no_empirical_samples_used':True}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--init',action='store_true');g.add_argument('--analyze',action='store_true')
    g.add_argument('--block',type=int);g.add_argument('--self-test',action='store_true')
    g.add_argument('--load',action='store_true')
    ap.add_argument('--profile',default='nt533-lab');args=ap.parse_args()
    if args.init:init()
    elif args.analyze:analyze()
    elif args.self_test:self_test()
    else:run_block(1 if args.load else args.block,args.profile,load=args.load)
