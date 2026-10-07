"""Recompute the report's descriptive numbers from canonical local raw files.

Read-only for measurements and existing report. Writes a separate review packet.
Run with the bundled Python runtime; no AWS/SSH access or new experiment.
"""
import datetime as dt
import csv
import hashlib
import json
import math
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/analysis/independent-review.json'
DOC = ROOT / 'docs/18-so-lieu-de-kiem-chung.md'
MODES = ('peering', 'tgw')
COUNTERS = ('bw_in_allowance_exceeded', 'bw_out_allowance_exceeded',
            'pps_allowance_exceeded', 'conntrack_allowance_exceeded', 'linklocal_allowance_exceeded')
sources = {}
checks = []


def read(path):
    path = Path(path)
    sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path.read_text(encoding='utf-8-sig')


def obj(path):
    return json.loads(read(path))


def equal(actual, expected, label, tol=1e-10):
    okay = math.isclose(actual, expected, abs_tol=tol, rel_tol=1e-12)
    checks.append(dict(label=label,actual=actual,expected=expected,tolerance=tol,passed=okay))
    if not okay:
        raise ValueError(f'{label}: raw={actual}, report={expected}')


def iso(text):
    return dt.datetime.fromisoformat(re.sub(r'(\.\d{6})\d+', r'\1', text.strip()).replace('Z', '+00:00'))


def cpu(path, lo, hi):
    rows = []
    for line in read(path).splitlines():
        f = line.split()
        if len(f) == 12 and f[1] == 'all' and re.fullmatch(r'\d\d:\d\d:\d\d', f[0]):
            stamp = dt.datetime.combine(lo.date(), dt.time.fromisoformat(f[0]), tzinfo=dt.timezone.utc)
            if lo < stamp <= hi:
                rows.append((100-float(f[11]), float(f[7])))
    if not rows:
        raise ValueError(f'No CPU samples: {path}')
    return dict(samples=len(rows),busy_percent=st.mean(x[0] for x in rows),
                soft_percent=st.mean(x[1] for x in rows),lo_utc=lo.isoformat(),hi_utc=hi.isoformat())


def ena(before, after):
    a, b = [{k:int(v) for k,v in re.findall(r'^\s*(\w+):\s*(\d+)\s*$', read(p), re.M)}
            for p in (before, after)]
    if not all(k in a and k in b for k in COUNTERS):
        raise ValueError('Missing ENA counter')
    if any(b[k] < a[k] for k in COUNTERS):
        raise ValueError('ENA counter reset across capture')
    return {k:dict(before=a[k],after=b[k],delta=b[k]-a[k]) for k in COUNTERS}


def description(values):
    return dict(n=len(values),mean=st.mean(values),sample_sd=st.stdev(values),
                minimum=min(values),maximum=max(values),cv_percent=100*st.stdev(values)/st.mean(values))


def tcp(path):
    j = obj(path)
    assert j.get('error') is None
    assert j['start']['test_start']['protocol'] == 'TCP'
    r = j['end']['sum_received']
    g = 8*r['bytes']/r['seconds']/1e9
    equal(g,r['bits_per_second']/1e9,f'{path.name} receiver bytes/seconds')
    assert read(path.with_name(path.stem+'-exit-code.txt')).strip() == '0'
    lo = iso(read(path.with_name(path.stem+'-start.txt'))) + dt.timedelta(seconds=5)
    hi = iso(read(path.with_name(path.stem+'-end.txt')))
    return dict(run=int(path.stem.split('-')[1]),source=path.relative_to(ROOT).as_posix(),
                receiver_bytes=r['bytes'],receiver_seconds=r['seconds'],receiver_Gbps=g,
                retransmits=j['end']['sum_sent']['retransmits'],
                cpu=cpu(path.with_name(path.stem+'-cpu.txt'),lo,hi),
                ena=ena(path.with_name(path.stem+'-ena-before.txt'),path.with_name(path.stem+'-ena-after.txt')))


def folder(pattern):
    found = list(ROOT.glob(pattern))
    assert len(found) == 1, (pattern, found)
    return found[0]


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def main():
    old = obj(ROOT/'results/analysis/report-metrics.json')
    result = dict(checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  scope='Canonical idle RTT, TCP single, fan-in. Five runs per mode. No new measurement.',
                  rtt={},single={},fanin={})
    ping_folders = {
        'peering': ROOT/'results/pilot-peering/rtt-idle-a-b/nt531-results/peering-rtt-idle-a-b-20261005T115510Z-6qX9Gm',
        'tgw': ROOT/'results/formal/tgw/rtt-idle-a-b/nt531-results/tgw-rtt-idle-a-b-20261005T120751Z-mx0lij'}
    for mode in MODES:
        p = ping_folders[mode]
        rows = list(csv.DictReader(read(p/'summary.csv').splitlines()))
        parsed=[]
        for row in rows:
            n=int(row['run']); raw=read(p/f'run-{n}.txt')
            stat=re.search(r'(\d+) packets transmitted, (\d+) received, ([\d.]+)% packet loss',raw)
            rtt=re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms',raw)
            assert stat and rtt
            vals=dict(run=n,transmitted=int(stat[1]),received=int(stat[2]),loss_percent=float(stat[3]),
                      **dict(zip(('min_ms','avg_ms','max_ms','mdev_ms'),map(float,rtt.groups()))))
            for key in vals: equal(vals[key],float(row[key]),f'{mode} ping run {n} {key}')
            samples=re.findall(r'time=([\d.]+) ms',raw)
            assert len(samples)==vals['received']==100
            vals['raw_reply_samples']=len(samples)
            parsed.append(vals)
        assert [r['run'] for r in parsed]==list(range(1,6))
        desc=description([r['avg_ms'] for r in parsed])
        for k in ('mean','sample_sd','minimum','maximum'):
            equal(desc[k],old['rtt'][mode][k],f'{mode} RTT {k}')
        result['rtt'][mode]=dict(rows=parsed,stats=desc,source=(p/'summary.csv').relative_to(ROOT).as_posix())
        a=folder(f'results/formal/{mode}/tcp-single-a-b/A/*')
        b=folder(f'results/formal/{mode}/tcp-single-a-b/B/*')
        single=[]
        b_ena=ena(b/'ena-before.txt',b/'ena-after.txt')
        for n in range(1,6):
            r=tcp(a/f'run-{n}.json')
            r['cpu_B']=cpu(b/'cpu.txt',iso(read(a/f'run-{n}-start.txt'))+dt.timedelta(seconds=5),
                           iso(read(a/f'run-{n}-end.txt')))
            previous=old['single_rows'][mode][n-1]
            equal(r['receiver_Gbps'],previous['ReceiverGbps'],f'{mode} single {n} Gbps')
            equal(r['retransmits'],previous['Retransmits'],f'{mode} single {n} retransmits')
            for raw_cpu, prev_cpu in ((r['cpu'],previous['CPU_A']),(r['cpu_B'],previous['CPU_B'])):
                equal(raw_cpu['samples'],prev_cpu['Samples'],f'{mode} single {n} CPU samples')
                equal(raw_cpu['busy_percent'],prev_cpu['BusyPercent'],f'{mode} single {n} CPU busy',tol=.000501)
            for k in COUNTERS:
                equal(r['ena'][k]['delta'],previous['ENA_A_Run_Delta'][k],f'{mode} single {n} A {k}')
                equal(b_ena[k]['delta'],previous['ENA_B_Whole_Capture_Delta'][k],f'{mode} single B {k}')
            single.append(r)
        desc=description([r['receiver_Gbps'] for r in single])
        for k in ('mean','sample_sd','minimum','maximum'):
            equal(desc[k],old['tcp_single'][mode][k],f'{mode} single {k}')
        result['single'][mode]=dict(rows=single,stats=desc,B_ena_whole_capture=b_ena)
        epoch=1791293390 if mode=='peering' else 1791296141
        audit=obj(ROOT/f'results/formal/{mode}/tcp-fanin/audit-{epoch}/validated-summary.json')
        b=folder(f'results/formal/{mode}/tcp-fanin/B/*')
        b_ena=ena(b/'ena-before.txt',b/'ena-after.txt')
        for k in COUNTERS:
            equal(b_ena[k]['delta'],audit['receiver_B_capture_ena_delta'][k],f'{mode} fanin B {k}')
        fan_rows=[]
        for n in range(1,6):
            senders={}
            for node in 'acd':
                a=folder(f'results/formal/{mode}/tcp-fanin/{node.upper()}/*')
                r=tcp(a/f'run-{n}.json')
                prev=next(m for m in audit['metrics'] if m['node']==node and m['run']==n)
                equal(r['receiver_Gbps'],prev['receiver_Gbps'],f'{mode} fanin {node} {n} Gbps')
                equal(r['retransmits'],prev['retransmits'],f'{mode} fanin {node} {n} retransmits')
                equal(r['cpu']['busy_percent'],prev['cpu_busy_percent'],f'{mode} fanin {node} {n} CPU')
                senders[node]=r
            lo=dt.datetime.fromtimestamp(epoch+45*(n-1)+5,dt.timezone.utc)
            hi=lo+dt.timedelta(seconds=30)
            bcpu=cpu(b/'cpu.txt',lo,hi)
            prev=old['fanin_B_cpu'][mode][n-1]
            equal(bcpu['busy_percent'],prev['busy_percent'],f'{mode} fanin B {n} CPU')
            rates=[r['receiver_Gbps'] for r in senders.values()]
            total=sum(rates);jain=total*total/(3*sum(g*g for g in rates))
            equal(total,audit['windows'][n-1]['sum_receiver_Gbps'],f'{mode} fanin {n} approximate sum')
            equal(jain,old['quantitative_methods']['jain_per_run'][mode][n-1]['jain'],f'{mode} fanin {n} Jain')
            fan_rows.append(dict(run=n,senders=senders,approximate_total_Gbps=total,
                                 jain=jain,cpu_B=bcpu,wrapper_overlap_estimate_seconds=
                                 audit['windows'][n-1]['approximate_common_measurement_seconds']))
        desc=description([r['approximate_total_Gbps'] for r in fan_rows])
        for k in ('mean','sample_sd','minimum','maximum'):
            equal(desc[k],old['fanin_approximate_total'][mode][k],f'{mode} fanin {k}')
        result['fanin'][mode]=dict(rows=fan_rows,stats=desc,B_ena_whole_capture=b_ena)
    p,t=(result['rtt'][m]['stats']['mean'] for m in MODES)
    ps,ts=(result['single'][m]['stats']['mean'] for m in MODES)
    pf,tf=(result['fanin'][m]['stats']['mean'] for m in MODES)
    result['comparisons']=dict(rtt_tgw_minus_peering_ms=t-p,rtt_tgw_over_peering=t/p,
                              tcp_single_peering_above_tgw_percent=100*(ps/ts-1),
                              fanin_tgw_below_peering_percent=100*(1-tf/pf))
    result['checks']=checks;result['passed']=all(c['passed'] for c in checks)
    result['source_files']=[dict(path=p,sha256=h) for p,h in sorted(sources.items())]
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    export_md(result)
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),source_files=len(sources),
                          comparisons=result['comparisons'],output=str(DOC)),ensure_ascii=False))


def export_md(r):
    def mean_cpu(area,mode,key): return st.mean(row[key]['busy_percent'] for row in r[area][mode]['rows'])
    lines=['# Số liệu để kiểm chứng đồ án NT531',
           '', 'Tính lại từ file gốc ngày 06/10/2026. Bộ chuẩn: 5 lượt mỗi mode mỗi bài; không có phép đo mới. '+
           'Số hiện theo dấu chấm thập phân. JSON đi kèm giữ độ chính xác đầy đủ và SHA256 từng nguồn.',
           '', '## Nhận xét về bản phản biện gửi kèm', '',
           'Nhận xét hợp lý: giữ đề tài, siết điều kiện áp dụng. Cần làm rõ đơn vị GB/GiB, giả định warm-up, '+
           'ranh giới đếm route, và tổng fan-in theo cửa sổ chung. Khoảng tin cậy ghép theo đợt chưa thể tính từ '+
           'việc ghép tùy ý lượt 1–5 của hai phiên cũ. Bản phản biện chỉ xem kế hoạch; lần kiểm chứng này '+
           'đối chiếu thêm ping, TCP JSON, mpstat và ENA đã lưu.',
           '', '## Bảng tổng hợp', '']
    summary=[]
    for label,area,field in [('RTT trung bình các lượt (ms)','rtt','mean'),
                             ('SD mẫu giữa 5 RTT trung bình (ms)','rtt','sample_sd'),
                             ('TCP một luồng: goodput nhận (Gbps)','single','mean'),
                             ('SD mẫu goodput một luồng (Gbps)','single','sample_sd'),
                             ('Fan-in: tổng xấp xỉ (Gbps)','fanin','mean'),
                             ('SD mẫu tổng xấp xỉ fan-in (Gbps)','fanin','sample_sd')]:
        summary.append([label,*[f"{r[area][m]['stats'][field]:.6f}" for m in MODES]])
    summary.extend([['CPU A bài một luồng (%)',*[f'{mean_cpu("single",m,"cpu"):.4f}' for m in MODES]],
                    ['CPU B bài một luồng (%)',*[f'{mean_cpu("single",m,"cpu_B"):.4f}' for m in MODES]],
                    ['CPU B bài fan-in (%)',*[f'{mean_cpu("fanin",m,"cpu_B"):.4f}' for m in MODES]],
                    ['Trung bình Jain 5 lượt fan-in',*[f'{st.mean(x["jain"] for x in r["fanin"][m]["rows"]):.6f}' for m in MODES]]])
    lines.append(table(['Chỉ số','Peering','TGW'],summary))
    lines+=['', 'CPU busy = 100 − %idle, lấy dòng CPU all của mpstat trong cửa sổ nêu ở JSON. '+
             'Số tổng hợp là trung bình năm giá trị từng lượt, không phải tổng hai lõi; fan-in B có một cửa sổ Peering 29 mẫu, các cửa sổ còn lại 30 mẫu.',
             '', '## RTT khi mạng rảnh', '',
             'ICMP A→B→A; MTU 1500; mỗi lượt 100 gói, payload 56 byte, interval 0.2 giây. '+
             'RTT avg/min/max/mdev dưới đây lấy từ dòng thống kê ping (đã được ping làm tròn).']
    for m in MODES:
        lines+=['',f'### {m}', '', table(['Lượt','Gửi/nhận','Loss (%)','Min (ms)','Avg (ms)','Max (ms)','mdev (ms)'],
            [[x['run'],f"{x['transmitted']}/{x['received']}",x['loss_percent'],x['min_ms'],x['avg_ms'],x['max_ms'],x['mdev_ms']]
             for x in r['rtt'][m]['rows']]),'',f"Nguồn: `{r['rtt'][m]['source']}` và run-1.txt đến run-5.txt cạnh file đó."]
    lines+=['', 'Cả hai phiên 500/500 phản hồi, loss quan sát 0%. mdev là độ lệch chuẩn RTT bên trong một lượt; '+
             'SD mẫu trong bảng tổng hợp là SD của năm RTT avg, hai đại lượng khác nhau.',
             '', '## TCP một luồng A→B', '',
             'TCP P1, omit 5 giây, đo 30 giây, MTU 1500, iperf3 3.19.1, TCP cubic. Goodput dùng phía nhận.']
    for m in MODES:
        lines+=['',f'### {m}', '', table(['Lượt','Payload nhận (byte)','Thời gian nhận (s)','Goodput (Gbps)','Retransmits','CPU A (%)','CPU B (%)'],
             [[x['run'],x['receiver_bytes'],x['receiver_seconds'],f"{x['receiver_Gbps']:.9f}",x['retransmits'],
               f"{x['cpu']['busy_percent']:.4f}",f"{x['cpu_B']['busy_percent']:.4f}"] for x in r['single'][m]['rows']])]
    lines+=['', 'Các delta ENA đã theo dõi đều bằng 0 ở bài một luồng: A lấy trước/sau từng lượt, B lấy trước/sau cả phiên ghi. '+
             'Không suy ra toàn đường mạng không có mất gói. Retransmits là số segment truyền lại do TCP báo, không phải phần trăm mất gói.',
             '', '## Fan-in A/C/D cùng gửi tới B', '',
             'Mỗi nguồn một luồng; cổng 5201/5202/5203; 5 lượt, lịch bắt đầu cách 45 giây. '+
             'Mỗi nguồn dùng cửa sổ nhận riêng. Tổng dưới đây cộng ba goodput trung bình, chưa phải goodput chung cửa sổ chính xác.']
    for m in MODES:
        rows=[]
        for x in r['fanin'][m]['rows']:
            rows.append([x['run'],*[f"{x['senders'][n]['receiver_Gbps']:.9f}" for n in 'acd'],
                         f"{x['approximate_total_Gbps']:.9f}",f"{x['jain']:.9f}",
                         f"{x['cpu_B']['busy_percent']:.4f}",x['cpu_B']['samples']])
        lines+=['',f'### {m}', '',table(['Lượt','A nhận (Gbps)','C nhận (Gbps)','D nhận (Gbps)','Tổng xấp xỉ (Gbps)','Jain','CPU B (%)','Mẫu CPU B'],rows),
                '',table(['Nguồn','Goodput nhận TB (Gbps)','Retransmits 5 lượt','CPU nguồn TB (%)'],
                [[n.upper(),f"{st.mean(x['senders'][n]['receiver_Gbps'] for x in r['fanin'][m]['rows']):.9f}",
                  ', '.join(str(x['senders'][n]['retransmits']) for x in r['fanin'][m]['rows']),
                  f"{st.mean(x['senders'][n]['cpu']['busy_percent'] for x in r['fanin'][m]['rows']):.4f}"] for n in 'acd'])]
    lines+=['', 'Jain từng lượt J=(Σgᵢ)²/(3Σgᵢ²), với gᵢ là goodput nhận từng nguồn trong cửa sổ riêng; '+
             'số tổng hợp là trung bình năm J, không phải J của ba goodput trung bình cả phiên. '+
             'J gần 1 mô tả mức đều nhau trong bộ đo, chưa chứng minh max-min fairness hay năng lực tối đa dịch vụ.',
             '', '### ENA máy B: trước, sau và delta cả phiên', '']
    for m in MODES:
        lines+=['',f'**{m}**', '',table(['Counter','Trước','Sau','Delta'],
                 [[k,*[r['fanin'][m]['B_ena_whole_capture'][k][v] for v in ('before','after','delta')]] for k in COUNTERS])]
    lines+=['', 'Các delta ENA B trên bao gồm toàn phiên ghi, cả thời gian chờ/nghỉ; không phải riêng 30 giây của một lượt. '+
             'Không cộng bw_in và PPS thành số gói mất: các counter có thể cùng phản ánh một gói vượt allowance. '+
             '[Định nghĩa counter AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html).',
             '', '## Công thức để tự tính lại', '',
             '- Trung bình: x̄ = Σxᵣ/5. SD mẫu giữa lượt: s = √[Σ(xᵣ−x̄)²/4]. CV = 100s/x̄ (%).',
             '- Goodput nhận: G = 8 × receiver_bytes / receiver_seconds / 10⁹ (Gbps).',
             '- CPU busy mỗi mẫu = 100 − %idle; mỗi lượt lấy trung bình các mẫu thuộc cửa sổ; bảng tổng hợp lấy trung bình 5 lượt.',
             '- ENA delta = counter_sau − counter_trước, cùng NIC và không reset giữa hai lần đọc.',
             '- Tổng xấp xỉ fan-in mỗi lượt = G_A + G_C + G_D; chỉ số chung cửa sổ cần byte nhận trong cùng W.',
             '', 'Ví dụ Peering một luồng lượt 1: 8 × 17,932,877,824 / 30.00049 / 10⁹ = 4.7820226467 Gbps.',
             '', '### Chênh lệch quan sát', '']
    c=r['comparisons']
    lines+= [f"- RTT TGW − Peering = {c['rtt_tgw_minus_peering_ms']:.4f} ms; tỷ số TGW/Peering = {c['rtt_tgw_over_peering']:.4f}.",
             f"- TCP một luồng: (Peering/TGW − 1) × 100 = {c['tcp_single_peering_above_tgw_percent']:.6f}%; mẫu số là TGW.",
             f"- Fan-in: (1 − TGW/Peering) × 100 = {c['fanin_tgw_below_peering_percent']:.6f}%; mẫu số là Peering, dùng tổng xấp xỉ.",
             '', 'Đây là thống kê mô tả các phiên nối tiếp. Lượt cùng số ở hai mode không phải cặp đo đồng thời. '+
             'Chưa có CI theo đợt, kiểm định tương đương, RTT khi tải hay bảng giá us-east-1 đã chốt.',
             '', '## Ví dụ dự toán, không phải số đo hay hóa đơn', '',
             'Giả định tốc độ 4.6 Gbps giữ đều trong 35 giây: 20,125,000,000 byte = 20.125 GB thập phân = '+
             '18.742867 GiB. Nếu chỉ xét 30 giây cùng tốc độ: 17,250,000,000 byte = 17.25 GB = 16.065314 GiB. '+
             'Warm-up thực tế, ACK, retransmission và overhead cần được tính riêng để ước lượng lưu lượng tính phí. '+
             'Giá trị 4.6 Gbps đo trong 30 giây không tự chứng minh tốc độ 5 giây warm-up.',
             '', 'C_TGW = Σhⱼr_h + V_in r_g: phí attachment theo giờ bị tính và phí dung lượng gửi vào TGW. '+
             'Đơn giá theo region còn cần xác minh. [Quy tắc AWS](https://aws.amazon.com/transit-gateway/pricing/) '+
             'ghi giờ attachment lẻ tính tròn giờ và 1 GB bằng 1024 MB. Không nhân đôi payload unicast chỉ vì có attachment nguồn và đích.',
             '', 'N=4: 6 Peering full mesh hoặc 1 TGW + 4 attachment; 12 route liên VPC ở bốn bảng subnet nếu mỗi bảng có ba CIDR đích. '+
             'Không phải tổng số route toàn hệ thống. Đây là đếm kiến trúc, không phải kết quả tốc độ.',
             '', '## Nguồn và cách chạy lại', '',
             'Chạy `scripts/verify-results-for-review.py` bằng Python có sẵn. Script tính lại từ raw bằng thư viện chuẩn, '+
             'đối chiếu với báo cáo và xuất riêng tài liệu này cùng `results/analysis/independent-review.json`.',
             '',f"Đã đối chiếu {len(r['checks'])} phép tính/giá trị từ {len(r['source_files'])} file nguồn. JSON liệt kê đầy đủ đường dẫn, SHA256, "+
             'byte/thời lượng nhận, cửa sổ CPU và kiểm tra từng giá trị. Các số không làm tròn trong JSON phù hợp để gửi người khác kiểm chứng.',
             '', 'Nguồn chuẩn:']
    for mode in MODES:
        lines.append(f"- RTT {mode}: `{r['rtt'][mode]['source']}`.")
        lines.append(f"- TCP một luồng {mode}: `{Path(r['single'][mode]['rows'][0]['source']).parent.as_posix()}`.")
        for node in 'acd':
            lines.append(f"- Fan-in {mode} {node.upper()}: `{Path(r['fanin'][mode]['rows'][0]['senders'][node]['source']).parent.as_posix()}`.")
    DOC.write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
