"""Deploy and run a bounded application pilot on the EXISTING four EC2.

Only three private-source ingress rules may be added; route switches reuse the
confirmation plan validator. Stops services and restores original mode on exit.
Retains failed attempts. Does not allocate EC2/EIP/TGW/S3 or mix pilot with RTT.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import ipaddress
from pathlib import Path
import secrets
import re
import shlex
import shutil
import subprocess
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'experiments/application-qos'
RESULTS = ROOT / 'results/application-qos-pilot-v1'
TF = ROOT / 'infra/terraform'
REMOTE = '/opt/nt531-application'
spec = importlib.util.spec_from_file_location('confirmation', ROOT / 'scripts/rtt-confirmation.py')
confirmation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(confirmation)
cli = confirmation.cli


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Experiment:
    def __init__(self, profile):
        self.profile = profile
        # AWS login's credential process can be rate-limited under CLI bursts.
        # Serialize local CLI invocations while SSM commands still run independently.
        self._aws_slots = threading.BoundedSemaphore(1)
        self.attempt = uuid.uuid4().hex
        self.temp = ROOT / 'tmp/application-qos' / self.attempt
        self.temp.mkdir(parents=True)
        assert self.aws(['sts', 'get-caller-identity'])['Account'] == '620306387033'
        outputs = cli(['terraform', f'-chdir={TF}', 'output', '-json'], True)
        self.instances = outputs['instances']['value']
        for node, address in dict(a='10.10.10.212', b='10.20.10.155', c='10.30.10.212', d='10.40.10.155').items():
            assert self.instances[node]['private_ip'] == address, 'Unexpected endpoint IP: ' + node
        self.routing = outputs['routing']['value']
        assert self.routing['transit_gateway_id'], 'Existing TGW required'
        self.tables = {self.routing[f'route_table_{n}_id'] for n in 'abcd'}
        self.original = self.routing['mode']
        online = self.aws(['ssm', 'describe-instance-information'])['InstanceInformationList']
        for node in 'abcd':
            assert any(x['InstanceId'] == self.instances[node]['id'] and x['PingStatus'] == 'Online' for x in online), node + ' not Online'

    def aws(self, args):
        with self._aws_slots:
            return cli(['aws', *args, '--profile', self.profile, '--region', 'us-east-1',
                '--output', 'json', '--no-cli-pager'], True)

    def remote(self, node, commands, timeout=240):
        request = {'DocumentName': 'AWS-RunShellScript', 'InstanceIds': [self.instances[node]['id']],
            'Parameters': {'commands': ['set -eu', *commands], 'executionTimeout': [str(timeout)]},
            'TimeoutSeconds': timeout, 'Comment': 'NT531 application QoS ' + node}
        path = self.temp / (node + '-' + uuid.uuid4().hex + '.json')
        path.write_text(json.dumps(request), encoding='utf-8')
        sent = self.aws(['ssm', 'send-command', '--cli-input-json', 'file://' + str(path)])
        command = sent['Command']['CommandId']
        deadline = time.monotonic() + timeout + 60
        while time.monotonic() < deadline:
            try:
                reply = self.aws(['ssm', 'get-command-invocation', '--command-id', command,
                    '--instance-id', self.instances[node]['id']])
            except RuntimeError as e:
                if 'InvocationDoesNotExist' not in str(e):
                    raise
                time.sleep(2)
                continue
            if reply['Status'] in ['Success', 'Failed', 'TimedOut', 'Cancelled']:
                path.with_suffix('.result.json').write_text(json.dumps(reply), encoding='utf-8')
                if reply['Status'] != 'Success':
                    raise RuntimeError(f"SSM {node} {reply['Status']}: {reply.get('StandardErrorContent', '')[-1800:]} {reply.get('StandardOutputContent', '')[-800:]}")
                return reply['StandardOutputContent'].strip()
            time.sleep(2)
        raise TimeoutError('Inspect SSM command before retrying: ' + command)

    def switch(self, mode):
        path = self.temp / (mode + '.tfplan')
        cli(['terraform', f'-chdir={TF}', 'plan', '-input=false', '-no-color',
            '-var=enable_transit_gateway=true', '-var=enable_application_qos=true',
            f'-var=routing_mode={mode}', f'-out={path}'])
        plan = cli(['terraform', f'-chdir={TF}', 'show', '-json', str(path)], True)
        confirmation.validate_route_plan(plan, self.tables)
        cli(['terraform', f'-chdir={TF}', 'apply', '-input=false', '-no-color', str(path)])

    def snapshot(self, mode, destination):
        state = self.aws(['ec2', 'describe-route-tables', '--route-table-ids', *sorted(self.tables)])
        links = [('a', 'b'), ('b', 'c'), ('c', 'b'), ('b', 'd'), ('d', 'b'), ('b', 'a')]
        for source, target in links:
            table = next(t for t in state['RouteTables'] if t['RouteTableId'] == self.routing[f'route_table_{source}_id'])
            route = next(r for r in table['Routes'] if r.get('DestinationCidrBlock') == f"10.{dict(a=10,b=20,c=30,d=40)[target]}.0.0/16")
            pair = ''.join(sorted([source, target]))
            peer = self.routing['peering_id'] if pair == 'ab' else self.routing['cross_peering_ids'][pair]
            key = 'VpcPeeringConnectionId' if mode == 'peering' else 'TransitGatewayId'
            assert route['State'] == 'active' and route.get(key) == (peer if mode == 'peering' else self.routing['transit_gateway_id']), 'Wrong route: ' + source + target
        destination.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')

    def preflight(self, out):
        ec2 = self.aws(['ec2', 'describe-instances', '--instance-ids', *[self.instances[n]['id'] for n in 'abcd']])
        envs = [i for r in ec2['Reservations'] for i in r['Instances']]
        assert len(envs) == 4 and all(i['State']['Name'] == 'running' and i['InstanceType'] == 'c6i.large' and i['Placement']['AvailabilityZone'] == 'us-east-1a' for i in envs)
        assert len({i['ImageId'] for i in envs}) == 1
        for node in 'abcd':
            text = self.remote(node, [
                'test "$(cat /sys/class/net/ens5/mtu)" = 1500 || { echo "MTU must be 1500" >&2; exit 6; }',
                'test "$(timedatectl show -p NTPSynchronized --value)" = yes || { echo "NTP must be synchronized" >&2; exit 6; }',
                "if pgrep -f '[c]ollect-confirmation-rtt.py|[c]ollect-rtt-under-load.py|[i]perf3 -c|[a]pp.py load' >/dev/null; then echo 'A measurement is already active' >&2; exit 5; fi",
                "if pgrep -x 'otelcol|otelcol-contrib|prometheus|grafana|grafana-server' >/dev/null; then echo 'Stop observability processes before comparison' >&2; exit 5; fi",
                f"{REMOTE}/venv/bin/python --version", f'{REMOTE}/venv/bin/pip freeze',
                'uname -r', 'mpstat -P ALL 1 1'])
            (out / f'preflight-{node}.txt').write_text(text + '\n', encoding='utf-8')
            actual = self.remote(node, [f'sha256sum {REMOTE}/app.py']).split()[0]
            assert actual == sha(APP / 'app.py'), 'Application differs on node ' + node

    def stop(self):
        errors = []
        def stop_node(node):
            try:
                self.remote(node, ['if systemctl cat nt531-app-monitor.service >/dev/null 2>&1; then systemctl stop nt531-app-monitor.service; fi',
                    'if systemctl cat nt531-app.service >/dev/null 2>&1; then systemctl stop nt531-app.service; fi',
                    'test "$(systemctl is-active nt531-app.service || true)" != active'])
            except Exception as e:
                errors.append(node + ': ' + str(e))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(stop_node, 'abcd'))
        if errors:
            raise RuntimeError('Cleanup failed: ' + '; '.join(errors))

    def monitor_start(self, mode):
        def start_node(node):
            path = f'{REMOTE}/results/{self.attempt}-{mode}-{node}-monitor'
            self.remote(node, [f'mkdir -p {path}', f'chown ec2-user:ec2-user {REMOTE}/results {path}',
                f'ethtool -S ens5 > {path}/ena-before.txt',
                'systemctl reset-failed nt531-app-monitor.service 2>/dev/null || true',
                f"systemd-run --quiet --collect --unit=nt531-app-monitor --property=User=ec2-user -- /bin/sh -c 'LC_ALL=C TZ=UTC exec mpstat -P ALL 1 > {path}/cpu.txt'"])
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(start_node, 'abcd'))

    def monitor_save(self, mode, destination):
        def save_node(node):
            path = f'{REMOTE}/results/{self.attempt}-{mode}-{node}-monitor'
            code = f"import pathlib,gzip,json; p=pathlib.Path({path!r}); b=json.dumps({{f.name:f.read_text() for f in p.glob('*.txt')}}).encode(); (p/'monitor.json.gz').write_bytes(gzip.compress(b,mtime=0))"
            self.remote(node, ['systemctl stop nt531-app-monitor.service', f'ethtool -S ens5 > {path}/ena-after.txt',
                'python3 -c ' + shlex.quote(code)])
            self.fetch(node, path + '/monitor.json.gz', destination / f'monitor-{node}.json.gz')
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(save_node, 'abcd'))

    def start(self, mode, tracing=False, protocol=None):
        protocol = protocol or json.loads((APP / 'pilot.json').read_text(encoding='utf-8'))
        health = {}
        for node in 'cdb':
            instance = self.instances[node]
            role, port = ('gateway', 8080) if node == 'b' else ('worker', 8081)
            command = f'{REMOTE}/venv/bin/python {REMOTE}/app.py {role} --node {node} --mode {mode} --bind {instance["private_ip"]} --port {port}'
            command += f' --worker-delay-ms {protocol["worker_delay_ms"]} --worker-slots {protocol["worker_slots"]} --response-bytes {protocol["worker_response_bytes"]} --timeout {protocol["request_timeout_seconds"]}'
            if protocol.get('queue_logging') and node in 'cd':
                command += f' --queue-file {REMOTE}/queue-{self.attempt}-{node}.jsonl.gz'
            if tracing:
                command += f' --trace-file {REMOTE}/traces-{self.attempt}-{node}.jsonl'
            unit = '[Unit]\nDescription=NT531 application pilot\nAfter=network-online.target\n[Service]\nType=simple\nUser=ec2-user\nExecStart=' + command + '\nRestart=no\nTimeoutStopSec=10\nLimitNOFILE=8192\n[Install]\nWantedBy=multi-user.target\n'
            encoded = base64.b64encode(unit.encode()).decode()
            text = self.remote(node, [f"printf '%s' '{encoded}' | base64 -d > /etc/systemd/system/nt531-app.service",
                'systemctl daemon-reload', 'systemctl start nt531-app.service',
                'sleep 1', 'systemctl is-active --quiet nt531-app.service',
                f"curl --fail --silent http://{instance['private_ip']}:{port}/health"])
            health[node] = json.loads(text)
            assert health[node]['node'] == node and health[node]['role'] == role
            assert health[node]['worker_slots'] == protocol['worker_slots'] and health[node]['worker_delay_ms'] == protocol['worker_delay_ms']
            assert health[node]['tracing'] == tracing and health[node]['response_bytes'] == protocol['worker_response_bytes']
            assert health[node]['queued'] == health[node]['active'] == 0
            if node in 'cd':assert health[node]['queue_logging'] == bool(protocol.get('queue_logging'))
        return health

    def fetch(self, node, filename, destination):
        """SSM output is capped: fetch independent 18000-byte base64 chunks, hash verify."""
        key = ROOT / 'tmp/ssh-download-private/nt531.pem'
        scp = shutil.which('scp')
        if key.is_file() and scp and 'denybin' not in scp:
            return self.fetch_scp(node, filename, destination, key)
        info = json.loads(self.remote(node, ["python3 -c " + shlex.quote(
            f"import pathlib,hashlib,json; p=pathlib.Path({filename!r}); b=p.read_bytes(); print(json.dumps(dict(size=len(b),sha256=hashlib.sha256(b).hexdigest())))")]))
        assert info['size'] < 20_000_000, 'Bounded pilot artifact size exceeded'
        def chunk(offset):
            encoded = self.remote(node, ["python3 -c " + shlex.quote(
                f"import pathlib,base64; b=pathlib.Path({filename!r}).read_bytes(); print(base64.b64encode(b[{offset}:{offset+17000}]).decode())")])
            return base64.b64decode(encoded, validate=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            content = b''.join(pool.map(chunk, range(0, info['size'], 17000)))
        assert len(content) == info['size'] and hashlib.sha256(content).hexdigest() == info['sha256']
        destination.write_bytes(content)

    def fetch_scp(self, node, filename, destination, key):
        """Read-only bulk transfer after capture, with SSM-pinned host key and byte hash."""
        assert filename.startswith(REMOTE + '/') and re.fullmatch(r'[A-Za-z0-9_./-]+', filename)
        info = json.loads(self.remote(node, ['python3 -c ' + shlex.quote(
            f"import pathlib,hashlib,json; p=pathlib.Path({filename!r}); b=p.read_bytes(); print(json.dumps(dict(size=len(b),sha256=hashlib.sha256(b).hexdigest())))")]))
        assert 0 <= info['size'] < 20000000
        host = self.instances[node]['public_ip']
        ipaddress.ip_address(host)
        known = self.temp / ('known-hosts-' + node)
        if not known.exists():
            pub = self.remote(node, ['cat /etc/ssh/ssh_host_ed25519_key.pub']).split()
            assert len(pub) >= 2 and pub[0] == 'ssh-ed25519'
            known.write_text(host + ' ' + pub[0] + ' ' + pub[1] + '\n', encoding='utf-8')
        command = ['scp', '-q', '-i', str(key), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known),
            '-o', 'ConnectTimeout=10', 'ec2-user@' + host + ':' + filename, str(destination)]
        reply = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if reply.returncode:
            raise RuntimeError('Read-only SCP download failed: ' + reply.stderr[-1800:])
        assert destination.stat().st_size == info['size'] and sha(destination) == info['sha256'], 'SCP checksum mismatch'
        proof = dict(transport='scp_after_capture', node=node, remote_file=filename,
            verified_size=info['size'], verified_sha256=info['sha256'],
            host_key_source='Authenticated SSM /etc/ssh/ssh_host_ed25519_key.pub',
            known_hosts_sha256=sha(known), strict_host_key_checking=True,
            collected_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        destination.with_suffix(destination.suffix + '.transport.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')


def setup(experiment):
    flag = TF / 'application.auto.tfvars'
    flag.write_text('enable_application_qos = true\n', encoding='utf-8')
    path = experiment.temp / 'application-access.tfplan'
    cli(['terraform', f'-chdir={TF}', 'plan', '-input=false', '-no-color',
        f'-var=routing_mode={experiment.original}', '-var=enable_transit_gateway=true', f'-out={path}'])
    plan = cli(['terraform', f'-chdir={TF}', 'show', '-json', str(path)], True)
    changes = [r for r in plan.get('resource_changes', []) if r['change']['actions'] != ['no-op']]
    allowed = {f'aws_vpc_security_group_ingress_rule.application_http["{link}"]': (source, target, port)
        for link, source, target, port in [('a_b','a','b',8080), ('b_c','b','c',8081), ('b_d','b','d',8081)]}
    for resource in changes:
        assert resource['address'] in allowed and resource['change']['actions'] == ['create'], 'Refuse any infrastructure mutation except three application ingress creates'
        source, target, port = allowed[resource['address']]
        after = resource['change']['after']
        assert after['cidr_ipv4'] == experiment.instances[source]['private_ip'] + '/32' and after['security_group_id'] == experiment.instances[target]['security_group_id']
        assert after['from_port'] == after['to_port'] == port and after['ip_protocol'] == 'tcp'
    cli(['terraform', f'-chdir={TF}', 'apply', '-input=false', '-no-color', str(path)])
    for node in 'abcd':
        print('Install isolated application environment: ' + node, flush=True)
        commands = ['ip link set dev ens5 mtu 1500', f'mkdir -p {REMOTE}', f'chown ec2-user:ec2-user {REMOTE}']
        for filename in ['app.py', 'requirements.txt']:
            encoded = base64.b64encode((APP / filename).read_bytes()).decode()
            commands += [f"printf '%s' '{encoded}' | base64 -d > {REMOTE}/{filename}", f'chown ec2-user:ec2-user {REMOTE}/{filename}']
        commands += [f"runuser -u ec2-user -- python3 -m venv {REMOTE}/venv",
            f'runuser -u ec2-user -- {REMOTE}/venv/bin/pip install --disable-pip-version-check -r {REMOTE}/requirements.txt',
            f'{REMOTE}/venv/bin/pip check']
        experiment.remote(node, commands, timeout=600)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / ('deployment-' + experiment.attempt + '.json')).write_text(json.dumps({'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'instances': experiment.instances, 'new_compute_resources': 0, 'new_ingress_rules': len(changes),
        'application_sha256': sha(APP / 'app.py'), 'requirements_sha256': sha(APP / 'requirements.txt'),
        'services_start_on_boot': False, 'original_mode': experiment.original}, indent=2) + '\n', encoding='utf-8')


def pilot(experiment, protocol_file):
    protocol = json.loads(protocol_file.read_text(encoding='utf-8'))
    out = ROOT / 'results' / protocol['id'] / experiment.attempt
    out.mkdir(parents=True)
    shutil.copyfile(Path(__file__), out / 'runner-source.py')
    for name in ['app.py', 'requirements.txt']:
        shutil.copyfile(APP / name, out / name)
    shutil.copyfile(protocol_file, out / 'pilot.json')
    record = {'attempt': experiment.attempt, 'phase': protocol['phase'], 'protocol': protocol,
        'protocol_sha256': sha(protocol_file), 'application_sha256': sha(APP / 'app.py'),
        'runner_sha256': sha(Path(__file__)), 'requirements_sha256': sha(APP / 'requirements.txt'),
        'instances': experiment.instances, 'original_mode': experiment.original,
        'routing_context': experiment.routing,
        'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'order': secrets.SystemRandom().sample(['peering', 'tgw'], 2), 'status': 'started', 'runs': []}
    def save():
        (out / 'attempt.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    save()
    cleanup_errors = []
    try:
        experiment.preflight(out)
        for mode in record['order']:
            print('Application pilot: ' + mode, flush=True)
            experiment.stop()
            experiment.switch(mode)
            modepath = out / mode
            modepath.mkdir()
            experiment.snapshot(mode, modepath / 'routes-before.json')
            time.sleep(protocol['settle_seconds'])
            experiment.start(mode, protocol=protocol)
            experiment.monitor_start(mode)
            for rate in protocol['rates_rps']:
                stem = f'{REMOTE}/results/{experiment.attempt}-{mode}-{rate}'
                command = f'{REMOTE}/venv/bin/python {REMOTE}/app.py load --node a --mode {mode} --rate {rate}'
                command += f' --response-bytes {protocol["worker_response_bytes"]} --deadline-ms {protocol["deadline_ms"]} --timeout {protocol["request_timeout_seconds"]} --maximum-inflight {protocol["maximum_inflight"]}'
                experiment.remote('a', [f'runuser -u ec2-user -- {command} --duration {protocol["warmup_seconds"]} --out {stem}-warmup > {stem.split("/results/")[0]}/warmup-{experiment.attempt}.log'])
                print(f'  {rate} requests/s, {protocol["duration_seconds"]} s, tracing off', flush=True)
                output = experiment.remote('a', [f'runuser -u ec2-user -- {command} --duration {protocol["duration_seconds"]} --out {stem}'])
                result = json.loads(output)
                record['runs'].append(result)
                save()
                # Compress complete raw request data; summary alone is insufficient for verification.
                experiment.remote('a', ["python3 -c " + shlex.quote(f"import pathlib,gzip; p=pathlib.Path({stem!r}); (p/'requests.jsonl.gz').write_bytes(gzip.compress((p/'requests.jsonl').read_bytes(),mtime=0))")])
                ratepath = modepath / f'rate-{rate}'
                ratepath.mkdir()
                (ratepath / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
                experiment.fetch('a', stem + '/requests.jsonl.gz', ratepath / 'requests.jsonl.gz')
            experiment.snapshot(mode, modepath / 'routes-after.json')
            experiment.monitor_save(mode, modepath)
        experiment.stop()
        # One small trace-only functional run, excluded from all comparative summaries.
        mode = record['order'][-1]
        experiment.start(mode, tracing=True, protocol=protocol)
        stem = f'{REMOTE}/results/{experiment.attempt}-trace-smoke'
        output = experiment.remote('a', [f'runuser -u ec2-user -- {REMOTE}/venv/bin/python {REMOTE}/app.py load --node a --mode {mode} --rate 2 --duration 3 --out {stem} --trace-file {REMOTE}/traces-{experiment.attempt}-a.jsonl'])
        record['trace_smoke'] = json.loads(output)
        experiment.stop()  # SIGTERM drains tracing processors.
        tracepath = out / 'trace-smoke'
        tracepath.mkdir()
        for node in 'abcd':
            experiment.fetch(node, f'{REMOTE}/traces-{experiment.attempt}-{node}.jsonl', tracepath / (node + '.jsonl'))
        record['status'] = 'complete'
    except Exception as e:
        record['status'] = 'failed'
        record['error'] = str(e)
        raise
    finally:
        for label, action in [('stop_services', experiment.stop), ('restore_routes', lambda: experiment.switch(experiment.original))]:
            try:
                action()
            except Exception as e:
                cleanup_errors.append(label + ': ' + str(e))
        record['cleanup_errors'] = cleanup_errors
        record['ended_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        if cleanup_errors:
            record['status'] = 'cleanup_failed'
        save()
        print(json.dumps({'folder': str(out), 'status': record['status'], 'cleanup_errors': cleanup_errors}), flush=True)
    if cleanup_errors:
        raise RuntimeError('Inspect cleanup_errors before running any further measurement')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['setup', 'pilot', 'stop'])
    p.add_argument('--profile', default='nt533-lab')
    p.add_argument('--protocol', choices=['pilot', 'calibration'], default='pilot')
    args = p.parse_args()
    experiment = Experiment(args.profile)
    if args.action == 'setup':
        setup(experiment)
    elif args.action == 'pilot':
        pilot(experiment, APP / (args.protocol + '.json'))
    else:
        experiment.stop()
