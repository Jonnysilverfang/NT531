"""One bounded RTT/controlled-TCP-load run on A; exploratory, not primary inference."""
import argparse,base64,datetime as dt,gzip,json,pathlib,re,subprocess,time,uuid,os
os.environ['LC_ALL']='C'
os.environ['TZ']='UTC'

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def call(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr[:400])
    return p.stdout

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['peering','tgw'],required=True)
    ap.add_argument('--rate-mbps',type=int,choices=[0,250,500],required=True)
    ap.add_argument('--run',type=int,choices=[1,2,3],required=True)
    a=ap.parse_args()
    ip=call(['ip','-4','-o','addr','show','dev','ens5'])
    assert '10.10.10.212/' in ip
    assert pathlib.Path('/sys/class/net/ens5/mtu').read_text().strip()=='1500'
    assert call(['timedatectl','show','-p','NTPSynchronized','--value']).strip()=='yes'
    assert not re.search(r':520[123]\b',call(['ss','-Htn','state','established']))
    out=pathlib.Path('/home/ec2-user/nt531-results/rtt-load-exploratory-v1')/a.mode/f'rate-{a.rate_mbps}'/uuid.uuid4().hex
    out.mkdir(parents=True)
    result={'mode':a.mode,'run':a.run,'target_rate_mbps':a.rate_mbps,'remote_folder':str(out),
            'started_utc':now(),'ip':ip,'kernel':call(['uname','-r']),
            'ping_version':call(['ping','-V']),'iperf_version':call(['iperf3','--version']),
            'mtu':1500,'ena_before':call(['sudo','-n','ethtool','-S','ens5'])}
    cpu_file=(out/'cpu.txt').open('w');cpu=subprocess.Popen(['mpstat','-P','ALL','1'],stdout=cpu_file)
    tcp=None;tcp_file=None;err_file=None
    try:
        if a.rate_mbps:
            tcp_file=(out/'tcp.json').open('w');err_file=(out/'tcp-stderr.txt').open('w')
            result['tcp_launch_utc']=now()
            tcp=subprocess.Popen(['iperf3','-c','10.20.10.155','-p','5201','-P','1','-b',f'{a.rate_mbps}M',
                                  '-O','5','-t','30','-i','1','-J','--get-server-output'],stdout=tcp_file,stderr=err_file)
            time.sleep(10)
            assert tcp.poll() is None,'TCP ended before ping; inspect retained stderr'
            assert re.search(r'10\.20\.10\.155:5201',call(['ss','-Htn','state','established']))
        else:time.sleep(10)
        result['ping_start_utc']=now()
        ping=subprocess.run(['ping','-n','-c','100','-i','.2','-W','2','-s','56','10.20.10.155'],capture_output=True,text=True)
        result.update(ping_end_utc=now(),ping_stdout=ping.stdout,ping_stderr=ping.stderr,ping_exit=ping.returncode)
        (out/'ping.txt').write_text(ping.stdout+ping.stderr)
        assert ping.returncode in (0,1),'Ping execution failed; retain raw instead of treating it as a load measurement'
        if tcp:
            assert tcp.poll() is None,'TCP ended before ping ended; run is invalid'
            result['tcp_exit']=tcp.wait(timeout=20);tcp_file.close();err_file.close()
            assert result['tcp_exit']==0
            result['tcp_json']=json.loads((out/'tcp.json').read_text())
            assert not result['tcp_json'].get('error')
            result['tcp_stderr']=(out/'tcp-stderr.txt').read_text()
    finally:
        if tcp and tcp.poll() is None:tcp.terminate();tcp.wait(timeout=10)
        if tcp_file and not tcp_file.closed:tcp_file.close()
        if err_file and not err_file.closed:err_file.close()
        cpu.terminate();cpu.wait(timeout=10);cpu_file.close()
    result['ena_after']=call(['sudo','-n','ethtool','-S','ens5'])
    result['cpu_trace']=(out/'cpu.txt').read_text();result['ended_utc']=now()
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();(out/'capture.json').write_bytes(raw)
    encoded=base64.b64encode(gzip.compress(raw)).decode()
    assert len(encoded)<20000,'SSM output too large; raw remains on EC2'
    print(encoded)

if __name__=='__main__':main()
