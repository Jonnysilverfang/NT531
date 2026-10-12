"""Offline empirical RTT distribution and TCP time-series supplement.

Preserves original data. No AWS calls, experiment execution, or causal p-values.
Python standard library for statistics; ReportLab for SVG; optional Sharp for PNG.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import statistics as st
import subprocess
from reportlab.graphics.shapes import Drawing, Line, PolyLine, String, Rect
from reportlab.graphics import renderSVG
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/analysis/statistics-probability.json'
FIG = ROOT / 'docs/images/statistics'
MODES = ('peering', 'tgw')
COLORS = {'peering': HexColor('#2166AC'), 'tgw': HexColor('#C66A23')}


def percentile(values, q):
    """Nearest rank: x_(ceil(n*q)), 1-based, without interpolation."""
    assert values and 0 < q <= 1
    return sorted(values)[math.ceil(len(values) * q) - 1]


def lag1(values):
    """Descriptive within-run lag-1 correlation; not a hypothesis test."""
    a, b = values[:-1], values[1:]
    ma, mb = st.mean(a), st.mean(b)
    den = math.sqrt(sum((v-ma)**2 for v in a) * sum((v-mb)**2 for v in b))
    return sum((x-ma)*(y-mb) for x, y in zip(a, b)) / den if den else None


def metrics(values):
    return dict(n=len(values), mean_of_printed_replies_ms=st.mean(values),
                sample_sd_of_printed_replies_ms=st.stdev(values),
                min_ms=min(values), max_ms=max(values),
                **{f'p{int(q*100)}_ms': percentile(values, q) for q in (.5, .95, .99)},
                thresholds=[dict(threshold_ms=v, exceedances=sum(x > v for x in values),
                                 empirical_exceedance_fraction=sum(x > v for x in values)/len(values))
                            for v in (.25, .5, 1.0)])


def label(d, x, y, text, size=10, anchor='start'):
    d.add(String(x, y, text, fontName='Helvetica', fontSize=size,
                 textAnchor=anchor, fillColor=HexColor('#253447')))


def axes(d, box, xlim, ylim, xticks, yticks, title, ylabel, logx=False):
    x, y, w, h = box
    def sx(v):
        a, b = xlim
        if logx:
            v, a, b = math.log10(v), math.log10(a), math.log10(b)
        return x + (v-a)/(b-a)*w
    def sy(v): return y+(v-ylim[0])/(ylim[1]-ylim[0])*h
    label(d, x, y+h+18, title, 12)
    label(d, x-4, y+h+3, ylabel, 9)
    for v in yticks:
        d.add(Line(x, sy(v), x+w, sy(v), strokeColor=HexColor('#E1E6ED'), strokeWidth=.5))
        label(d, x-8, sy(v)-3, f'{v:g}', 9, 'end')
    for v in xticks:
        d.add(Line(sx(v), y, sx(v), y-4, strokeColor=HexColor('#64748B')))
        label(d, sx(v), y-17, f'{v:g}', 9, 'middle')
    d.add(Line(x, y, x+w, y, strokeColor=HexColor('#64748B')))
    d.add(Line(x, y, x, y+h, strokeColor=HexColor('#64748B')))
    return sx, sy


def save(d, name, args):
    svg = FIG / (name+'.svg')
    renderSVG.drawToFile(d, str(svg))
    if args.node and args.node_modules:
        sharp = str(Path(args.node_modules) / 'sharp')
        code = "require(process.argv[1])(process.argv[2]).resize({width:2400}).png().toFile(process.argv[3])"
        subprocess.run([args.node, '-e', code, sharp, str(svg), str(FIG/(name+'.png'))], check=True)


def ecdf_figure(samples, args):
    d = Drawing(1000, 420)
    d.add(Rect(0, 0, 1000, 420, fillColor=HexColor('#FFFFFF'), strokeColor=None))
    label(d, 55, 393, 'Idle ICMP RTT: empirical distributions of printed replies', 16)
    label(d, 55, 373, '500 replies per mode; sequential sessions; no independence assumed for this descriptive plot', 10)
    for mode, x in (('peering', 55), ('tgw', 220)):
        d.add(Line(x, 346, x+22, 346, strokeColor=COLORS[mode], strokeWidth=2))
        label(d, x+28, 342, mode.upper())
    for box, limits, ticks, logx, title in (
        ((65,75,390,220),(.15,.9),(.2,.4,.6,.8),False,'Bulk view: linear RTT axis'),
        ((570,75,390,220),(.15,6.5),(.2,.5,1,2,5),True,'Full sample: logarithmic RTT axis')):
        sx, sy = axes(d, box, limits, (0,1), ticks, (0,.25,.5,.75,1), title, 'F_n(x)', logx)
        for mode in MODES:
            points = [sx(limits[0]),sy(0)]
            previous = 0
            for i, v in enumerate(sorted(samples[mode]), 1):
                current = i / len(samples[mode])
                if limits[0] <= v <= limits[1]:
                    points += [sx(v),sy(previous),sx(v),sy(current)]
                previous = current
            points += [sx(limits[1]), sy(previous if max(samples[mode]) <= limits[1] else sum(v<=limits[1] for v in samples[mode])/len(samples[mode]))]
            d.add(PolyLine(points, strokeColor=COLORS[mode], strokeWidth=1.8, fillColor=None))
        label(d, box[0]+box[2]/2, 38, 'RTT (ms)', 10, 'middle')
    label(d, 55, 12, 'The right panel includes the 5.90 ms observation; the left panel shows only RTT <= 0.90 ms.', 9)
    save(d, '01-rtt-ecdf', args)


def tcp_figure(tcp, args):
    d=Drawing(960,740)
    d.add(Rect(0,0,960,740,fillColor=HexColor('#FFFFFF'),strokeColor=None))
    label(d,60,714,'TCP single stream: median trajectories across five runs per mode',16)
    label(d,60,692,'TCP_INFO RTT and cwnd snapshots; sender rate; omitted warm-up intervals excluded',10)
    specs=(('sender_Gbps', (0,5.5), (0,2,4,5),'Sender rate (Gbps)'),
           ('tcp_rtt_ms', (0,max(r['tcp_rtt_ms'] for m in MODES for run in tcp[m] for r in run['intervals'])*1.05), None, 'TCP RTT estimate (ms)'),
           ('cwnd_KiB', (0,max(r['cwnd_KiB'] for m in MODES for run in tcp[m] for r in run['intervals'])*1.05),None,'cwnd (KiB)'))
    for row,(key,limits,ticks,title) in enumerate(specs):
        ticks=ticks or (0,round(limits[1]/2,2),round(limits[1],2))
        sx,sy=axes(d,(65,460-190*row,840,130),(0,31),limits,(0,5,10,15,20,25,30),ticks,title,'')
        for mode in MODES:
            points=[]
            for i in range(30):
                xs=[run['intervals'][i]['measurement_elapsed_end_s'] for run in tcp[mode]]
                ys=[run['intervals'][i][key] for run in tcp[mode]]
                points += [sx(st.median(xs)),sy(st.median(ys))]
            d.add(PolyLine(points,strokeColor=COLORS[mode],strokeWidth=2,fillColor=None))
    for mode,x in (('peering',615),('tgw',765)):
        d.add(Line(x,666,x+22,666,strokeColor=COLORS[mode],strokeWidth=2))
        label(d,x+28,662,mode.upper())
    label(d,485,36,'Elapsed measurement time after warm-up (s)',10,'middle')
    label(d,60,14,'Medians, not confidence bands. First reported interval may be partial; durations are retained in JSON.',9)
    save(d,'02-tcp-trajectories',args)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--node'); ap.add_argument('--node-modules')
    args=ap.parse_args()
    assert percentile([1,2,3,4],.5)==2 and percentile([1,2,3,4],.95)==4
    review=json.loads((ROOT/'results/analysis/independent-review.json').read_text(encoding='utf-8'))
    pinned={r['path']:r['sha256'] for r in review['source_files']}
    sources={}
    def read(name):
        raw=(ROOT/name).read_bytes()
        h=hashlib.sha256(raw).hexdigest()
        assert h==pinned[name], f'Raw source changed since review: {name}'
        sources[name]=h
        return raw.decode('utf-8-sig')
    result=dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                scope='Offline analysis only. No new AWS measurement; no service-wide p-values.',
                quantile_method='Nearest rank, ceil(n*q), without interpolation',
                threshold_status='Exploratory thresholds 0.25/0.5/1.0 ms selected after measurement, not prespecified SLOs',
                rtt={}, tcp_single={}, assumptions=['Printed reply values are quantized; distinct from ping summary averages.',
                'Packet/interval samples within runs are not assumed independent.',
                'Modes were measured in sequential sessions; session/time and routing mode are confounded.'])
    samples={}
    for mode in MODES:
        folder=Path(review['rtt'][mode]['source']).parent
        combined=[]; rows=[]
        for n in range(1,6):
            name=(folder/f'run-{n}.txt').as_posix()
            raw=read(name)
            summary=re.search(r'(\d+) packets transmitted, (\d+) received, ([\d.]+)% packet loss',raw)
            assert summary and tuple(map(float,summary.groups()))==(100,100,0)
            pairs=[(int(a),float(b)) for a,b in re.findall(r'icmp_seq=(\d+).*?time=([\d.]+) ms',raw)]
            assert [a for a,b in pairs]==list(range(1,101))
            values=[b for a,b in pairs]; combined+=values
            rows.append(dict(run=n,source=name,printed_reply_values_ms=values,
                             lag1_correlation=lag1(values),**metrics(values)))
        samples[mode]=combined
        result['rtt'][mode]=dict(per_run=rows,pooled=metrics(combined),
                               original_report_mean_of_ping_summary_avgs_ms=review['rtt'][mode]['stats']['mean'])
        tcp=[]
        for row in review['single'][mode]['rows']:
            j=json.loads(read(row['source']))
            intervals=[]
            for interval in j['intervals']:
                if interval['sum']['omitted']: continue
                assert len(interval['streams'])==1
                s=interval['streams'][0]
                intervals.append(dict(start_s=s['start'],end_s=s['end'],seconds=s['seconds'],
                                      sender_Gbps=s['bits_per_second']/1e9,
                                      tcp_rtt_ms=s['rtt']/1000,cwnd_KiB=s['snd_cwnd']/1024,
                                      receiver_window_KiB=s['snd_wnd']/1024,retransmits=s['retransmits']))
            assert len(intervals)==30
            for item in intervals:
                item['measurement_elapsed_end_s']=item['end_s']-intervals[0]['start_s']
            tcp.append(dict(run=row['run'],source=row['source'],intervals=intervals))
        result['tcp_single'][mode]=tcp
    upper=-math.expm1(math.log(.05)/500)
    assert abs((1-upper)**500-.05)<1e-12
    result['zero_missing_reply_example']=dict(missing=0,trials=500,one_sided_confidence=.95,
        upper_probability=upper,assumption='Illustrative iid Bernoulli constant-p model, not verified for this trace; not an AWS SLA bound')
    assert result['rtt']['peering']['pooled']['p95_ms']==.227
    assert result['rtt']['tgw']['pooled']['p95_ms']==.638
    assert sum(v>1 for v in samples['tgw'])==4 and sum(v>1 for v in samples['peering'])==0
    result['sources']=[dict(path=p,sha256=h) for p,h in sorted(sources.items())]
    FIG.mkdir(parents=True,exist_ok=True)
    ecdf_figure(samples,args);tcp_figure(result['tcp_single'],args)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sources_verified':len(sources),'p95_ms':{m:result['rtt'][m]['pooled']['p95_ms'] for m in MODES},
                      'tail_over_1ms':{m:sum(v>1 for v in samples[m]) for m in MODES},
                      'iid_zero_event_upper_percent':upper*100,'tcp_runs':sum(len(result['tcp_single'][m]) for m in MODES),
                      'measured_tcp_intervals':sum(len(run['intervals']) for m in MODES for run in result['tcp_single'][m]),
                      'json':str(OUT)}))


if __name__=='__main__': main()
