"""Build the results chapter from verified empirical NT531 datasets.

Use the Python and Node paths returned by Codex workspace dependency loader.
No AWS access, experiment execution, or source-data mutation occurs here.
"""
from pathlib import Path
import argparse
import csv
import json
import math
import statistics as st
import subprocess
import hashlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, String, Line, Rect, Circle, Polygon
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderSVG
from reportlab.lib.colors import HexColor, white
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from report_formulas import calculate, add_formula_pages, export_markdown
from report_context import add_context_pages, export_context_markdown

ROOT = Path(__file__).resolve().parents[1]
MODES = ['peering', 'tgw']
NAMES = {'peering': 'Peering', 'tgw': 'TGW'}
COLORS = [HexColor('#2166AC'), HexColor('#C66A23'), HexColor('#4B8960')]
CHARTS = ROOT / 'docs/images/results'
OUT = ROOT / 'results/analysis'
DOCX = ROOT / 'docs/13-chuong-ket-qua.docx'
ENA_URL = 'https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html'
NETWORK = {
    'a': ('10.10.0.0/16', '10.10.10.0/24', '10.10.10.212'),
    'b': ('10.20.0.0/16', '10.20.10.0/24', '10.20.10.155'),
    'c': ('10.30.0.0/16', '10.30.10.0/24', '10.30.10.212'),
    'd': ('10.40.0.0/16', '10.40.10.0/24', '10.40.10.155'),
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def stats(values):
    return dict(n=len(values), mean=st.mean(values), sample_sd=st.stdev(values), minimum=min(values), maximum=max(values))


def load_data():
    rtt_paths = {
        'peering': ROOT / 'results/pilot-peering/rtt-idle-a-b/nt531-results/peering-rtt-idle-a-b-20261005T115510Z-6qX9Gm/summary.csv',
        'tgw': ROOT / 'results/formal/tgw/rtt-idle-a-b/nt531-results/tgw-rtt-idle-a-b-20261005T120751Z-mx0lij/summary.csv',
    }
    rtt = {}
    for mode, path in rtt_paths.items():
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]
        assert len(rows) == 5 and {r['run'] for r in rows} == set(range(1, 6))
        assert all(r['transmitted'] == 100 and r['received'] == 100 and r['loss_percent'] == 0 for r in rows)
        rtt[mode] = rows
    single_path = ROOT / 'results/formal/tcp-single-comparison-audit.json'
    single_rows = read_json(single_path)
    single = {mode: sorted([r for r in single_rows if r['Mode'] == mode], key=lambda r: r['Run']) for mode in MODES}
    fanin = {}
    receiver = {}
    sources = [*rtt_paths.values(), single_path]
    for mode, epoch in [('peering', 1791293390), ('tgw', 1791296141)]:
        path = ROOT / f'results/formal/{mode}/tcp-fanin/audit-{epoch}/validated-summary.json'
        bpath = path.parent / 'remote-b.json'
        fanin[mode] = read_json(path)
        receiver[mode] = read_json(bpath)['captures'][0]['planned_cpu_windows']
        sources.extend([path, bpath])
        assert len(single[mode]) == 5 and [r['Run'] for r in single[mode]] == list(range(1, 6))
        assert fanin[mode]['full_raw_download_verified'] and fanin[mode]['validated_sender_runs'] == 15
        assert fanin[mode]['raw_files_on_ec2'] == 146 and fanin[mode]['session_epoch'] == epoch
        assert len(receiver[mode]) == 5
        for node in 'acd':
            runs = sorted(r['run'] for r in fanin[mode]['metrics'] if r['node'] == node)
            assert runs == list(range(1, 6))
        for w in fanin[mode]['windows']:
            total = sum(r['receiver_Gbps'] for r in fanin[mode]['metrics'] if r['run'] == w['run'])
            assert math.isclose(total, w['sum_receiver_Gbps'], abs_tol=1e-10)
    return rtt, single, fanin, receiver, sources


def text(drawing, x, y, content, size=11, anchor='start', color='#222222'):
    drawing.add(String(x, y, content, fontName='Arial', fontSize=size, textAnchor=anchor, fillColor=HexColor(color)))


def line_panel(d, x, y, w, h, series, title, ylabel, ymax, step, label_format='%.1f'):
    text(d, x, y+h+25, title, 13)
    text(d, x, y+h+7, ylabel, 10, color='#555555')
    plot = LinePlot()
    plot.x, plot.y, plot.width, plot.height = x+42, y+26, w-50, h-32
    plot.data = [list(zip(range(1, 6), vals)) for _, vals in series]
    plot.xValueAxis.valueMin = 1
    plot.xValueAxis.valueMax = 5
    plot.xValueAxis.valueStep = 1
    plot.yValueAxis.valueMin = 0
    plot.yValueAxis.valueMax = ymax
    plot.yValueAxis.valueStep = step
    plot.yValueAxis.labelTextFormat = label_format
    for axis in [plot.xValueAxis, plot.yValueAxis]:
        axis.labels.fontName, axis.labels.fontSize = 'Arial', 10
        axis.strokeColor = HexColor('#999999')
    plot.yValueAxis.visibleGrid = True
    plot.yValueAxis.gridStrokeColor = HexColor('#E5E5E5')
    for i, (_, values) in enumerate(series):
        plot.lines[i].strokeColor = COLORS[i]
        plot.lines[i].strokeWidth = 1.8
        for run, value in enumerate(values):
            px = plot.x + run * plot.width / 4
            py = plot.y + value * plot.height / ymax
            d.add(Circle(px, py, 3, fillColor=COLORS[i], strokeColor=COLORS[i]))
    d.add(plot)
    text(d, x+w/2, y+2, 'Lượt đo', 10, 'middle')


def legend(d, items, y):
    x = 65
    for i, item in enumerate(items):
        d.add(Rect(x, y-2, 12, 8, fillColor=COLORS[i], strokeColor=None))
        text(d, x+18, y-2, item, 11)
        x += 200


def save_chart(d, name, args):
    svg = CHARTS / f'{name}.svg'
    renderSVG.drawToFile(d, str(svg))
    node_code = "const sharp = require(process.argv[1]); sharp(process.argv[2], {density: 220}).flatten({background:'#ffffff'}).png().toFile(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});"
    subprocess.run([args.node, '-e', node_code, str(Path(args.node_modules)/'sharp'), str(svg), str(svg.with_suffix('.png'))], check=True)


def connection(d, p1, p2, color='#2166AC', width=2, two_way=True):
    """Draw a logical connection; bidirectional arrows mean reachability."""
    d.add(Line(*p1, *p2, strokeColor=HexColor(color), strokeWidth=width))
    ends = [(p1, p2), (p2, p1)] if two_way else [(p1, p2)]
    for start, end in ends:
        dx, dy = end[0]-start[0], end[1]-start[1]
        length=math.hypot(dx,dy)
        ux, uy = dx/length, dy/length
        bx, by = end[0]-8*ux, end[1]-8*uy
        d.add(Polygon([end[0],end[1],bx-3*uy,by+3*ux,bx+3*uy,by-3*ux],fillColor=HexColor(color),strokeColor=None))


def network_node(d, node, x, y):
    cidr, subnet, ip = NETWORK[node]
    color='#2166AC' if node != 'b' else '#4B8960'
    d.add(Rect(x,y,220,98,rx=6,ry=6,fillColor=HexColor('#F5F8FC'),strokeColor=HexColor(color),strokeWidth=1.5))
    text(d,x+12,y+75,f'VPC {node.upper()}    {cidr}',16)
    text(d,x+12,y+52,f'Subnet {subnet}',14)
    text(d,x+12,y+30,f'EC2 {node.upper()}   {ip}',16)
    text(d,x+12,y+10,'SG và route table riêng',13,color='#555555')


def build_architecture(args):
    """Topology from checked-in Terraform; no new AWS deployment implied."""
    d=Drawing(820,355)
    text(d,25,333,'VPC Peering toàn lưới giữa bốn VPC',19)
    # Three blue links terminate at B and are used by the fan-in workload.
    links=[('AB',(270,254),(550,254),'#2166AC'),
           ('AC',(82,205),(82,143),'#A7AFB8'),
           ('AD',(270,205),(550,143),'#A7AFB8'),
           ('BC',(270,143),(550,205),'#2166AC'),
           ('BD',(738,143),(738,205),'#2166AC'),
           ('CD',(270,94),(550,94),'#A7AFB8')]
    for name,p1,p2,color in links:
        connection(d,p1,p2,color)
    for node,x,y in [('a',50,205),('b',550,205),('c',50,45),('d',550,45)]:
        network_node(d,node,x,y)
    for label,x,y in [('AB',410,266),('AC',59,172),('AD',322,208),('BC',484,202),('BD',757,172),('CD',410,108)]:
        text(d,x,y,label,14,'middle')
    text(d,50,15,'Xanh: AB BC BD dùng cho A/C/D → B',14,color='#2166AC')
    text(d,450,15,'Xám: ba Peering còn lại',14,color='#666666')
    save_chart(d,'00a-kien-truc-peering',args)

    d=Drawing(820,355)
    text(d,25,333,'Transit Gateway kết nối bốn VPC',19)
    for p1,p2 in [((270,239),(337,183)),((270,111),(337,157)),((550,239),(483,183)),((550,111),(483,157))]:
        connection(d,p1,p2)
    for node,x,y in [('a',50,205),('b',550,205),('c',50,45),('d',550,45)]:
        network_node(d,node,x,y)
    d.add(Rect(337,137,146,66,rx=8,ry=8,fillColor=HexColor('#FFF4E8'),strokeColor=HexColor('#C66A23'),strokeWidth=2))
    text(d,410,177,'TGW',22,'middle')
    text(d,410,152,'Route table TGW',14,'middle')
    text(d,317,232,'att A',13,'middle')
    text(d,501,232,'att B',13,'middle')
    text(d,317,92,'att C',13,'middle')
    text(d,501,92,'att D',13,'middle')
    text(d,410,15,'1 TGW và 4 VPC attachment hai chiều',15,'middle')
    save_chart(d,'00b-kien-truc-tgw',args)

    d=Drawing(820,315)
    text(d,25,291,'Đường quản trị bằng Termius và Elastic IP',19)
    for x,w,label in [(50,230,'Máy cá nhân  ·  Termius'),(385,320,'Internet  ·  SSH TCP 22')]:
        d.add(Rect(x,238,w,34,rx=4,ry=4,fillColor=HexColor('#FFF4E8'),strokeColor=HexColor('#C66A23')))
        text(d,x+w/2,249,label,17,'middle')
    connection(d,(280,255),(385,255),'#C66A23',two_way=False)
    # A shared Internet segment reaches each VPC's own Internet Gateway.
    d.add(Line(545,238,545,215,strokeColor=HexColor('#C66A23'),strokeWidth=2))
    d.add(Line(107,215,713,215,strokeColor=HexColor('#C66A23'),strokeWidth=2))
    for i,node in enumerate('abcd'):
        x=20+i*202
        connection(d,(x+88,215),(x+88,179),'#C66A23',two_way=False)
        d.add(Rect(x,34,175,145,rx=5,ry=5,fillColor=HexColor('#F5F8FC'),strokeColor=HexColor('#2166AC'),strokeWidth=1.5))
        text(d,x+88,157,f'VPC {node.upper()}',18,'middle')
        text(d,x+88,132,f'IGW {node.upper()}',16,'middle')
        text(d,x+88,109,'Subnet và SG',15,'middle')
        d.add(Rect(x+9,45,157,52,rx=4,ry=4,fillColor=white,strokeColor=HexColor('#4B8960')))
        text(d,x+88,77,f'EC2 {node.upper()} + EIP {node.upper()}',15,'middle')
        text(d,x+88,57,'IP riêng '+NETWORK[node][2],14,'middle')
    text(d,410,10,'Mỗi EC2 có một EIP  ·  Benchmark dùng IP riêng qua Peering hoặc TGW',15,'middle')
    save_chart(d,'00c-quan-tri-eip',args)


def architecture_pages(doc):
    next_page(doc,'Mô hình kiến trúc Peering và Transit Gateway')
    paragraph(doc,'Hai mô hình dùng cùng bốn EC2 c6i.large trong us-east-1a, region us-east-1. Mỗi VPC có một subnet, một security group (SG) và một route table. Các hình thể hiện kết nối logic; mũi tên hai chiều biểu diễn khả năng gửi và phản hồi khi route và SG cho phép.')
    figure(doc,'00a-kien-truc-peering.png','Hình 1. Peering toàn lưới gồm AB, AC, AD, BC, BD và CD; ba liên kết xanh phục vụ bài A/C/D cùng gửi tới B.')
    figure(doc,'00b-kien-truc-tgw.png','Hình 2. Một TGW nối bốn VPC qua bốn attachment; các CIDR được propagation vào bảng định tuyến TGW mặc định.')
    paragraph(doc,'Một cặp qua Peering dùng kết nối trực tiếp giữa hai VPC. Qua TGW, dữ liệu đi từ VPC nguồn qua attachment, TGW và attachment đích. Cả hai mô hình cho phép các cặp trao đổi đồng thời; hình TGW không có nghĩa mọi luồng chia một mức thông lượng cố định.')

    next_page(doc,'Đường quản trị và cách chọn đường đo')
    figure(doc,'00c-quan-tri-eip.png','Hình 3. Termius truy cập bốn EC2 bằng bốn Elastic IP qua Internet Gateway riêng của từng VPC. EIP là địa chỉ public gắn với EC2, không phải một router trung gian.')
    paragraph(doc,'Subnet gắn route table có route 0.0.0.0/0 tới IGW của VPC. SG cho SSH TCP 22 theo ssh_admin_cidr; cấu hình demo hiện tại dùng 0.0.0.0/0. Các phép đo dùng địa chỉ riêng 10.x và các route liên VPC nên đường Internet/EIP không tham gia truyền tải benchmark.')
    doc.add_heading('Định tuyến cùng một tập endpoint',2)
    table(doc,['Thuộc tính','Peering','TGW'],[
        ['Target của route tới VPC khác','Peering đúng cặp','TGW'],
        ['Số route liên VPC','12 route có hướng','12 route có hướng'],
        ['Route trong từng VPC','3 CIDR đích của 3 VPC còn lại','3 CIDR đích của 3 VPC còn lại'],
        ['Kết nối dùng trong bài ba nguồn','AB, BC, BD','Attachment A, B, C, D'],
    ],[2.5,2.1,2.1])
    paragraph(doc,'Biến routing_mode chọn target của 12 route; enable_transit_gateway giữ hoặc cấp TGW. Peering và TGW có thể cùng tồn tại trong cấu hình, nhưng mỗi route đích có một target được chọn. Chuyển mode giữ nguyên EC2, IP riêng và đường SSH. Khi đo phải đợi apply hoàn tất và xác nhận route hai chiều; việc đổi 12 route không diễn ra nguyên tử.')
    doc.add_heading('Các luồng được dùng để đo',2)
    paragraph(doc,'RTT khi rảnh dùng ICMP từ A tới B và phản hồi về A. TCP một luồng dùng A tới B:5201. Bài ba nguồn dùng A tới B:5201, C tới B:5202 và D tới B:5203 đồng thời, với ba listener riêng trên B. CPU và bộ đếm ENA được ghi ở các endpoint; các hình chỉ vị trí quan sát, không biểu diễn số liệu giám sát bên trong dịch vụ TGW.')
    paragraph(doc,'Nguồn sơ đồ: cấu hình Terraform của dự án và metadata đã kiểm tra của các phiên đo ngày 06/10/2026.')


def build_charts(rtt, single, fanin, receiver, args):
    CHARTS.mkdir(parents=True, exist_ok=True)
    d = Drawing(820, 325)
    text(d, 20, 303, 'RTT khi mạng rảnh từ A tới B', 18)
    line_panel(d, 20, 65, 365, 175, [(NAMES[m], [r['avg_ms'] for r in rtt[m]]) for m in MODES], 'RTT trung bình từng lượt', 'RTT (ms)', .8, .2)
    line_panel(d, 435, 65, 365, 175, [(NAMES[m], [r['max_ms'] for r in rtt[m]]) for m in MODES], 'RTT lớn nhất từng lượt', 'RTT (ms)', 6, 2)
    legend(d, ['Peering', 'TGW'], 31)
    save_chart(d, '01-rtt', args)

    d = Drawing(820, 325)
    text(d, 20, 303, 'TCP một luồng từ A tới B', 18)
    line_panel(d, 20, 65, 365, 175, [(NAMES[m], [r['ReceiverGbps'] for r in single[m]]) for m in MODES], 'Thông lượng phía nhận', 'Thông lượng (Gbps)', 5, 1)
    line_panel(d, 435, 65, 365, 175, [(NAMES[m], [r['Retransmits'] for r in single[m]]) for m in MODES], 'Số lần truyền lại TCP', 'Retransmits (lần)', 60000, 20000, '%d')
    legend(d, ['Peering', 'TGW'], 31)
    save_chart(d, '02-tcp-single', args)

    d = Drawing(820, 340)
    text(d, 20, 318, 'Ba nguồn cùng gửi TCP tới B', 18)
    for i, mode in enumerate(MODES):
        x = 30+i*405
        text(d, x, 281, NAMES[mode], 13)
        text(d, x, 263, 'Tổng xấp xỉ từ trung bình từng nguồn (Gbps)', 10)
        bc = VerticalBarChart()
        bc.x, bc.y, bc.width, bc.height = x+32, 78, 325, 165
        bc.data = [[next(r['receiver_Gbps'] for r in fanin[mode]['metrics'] if r['run']==run and r['node']==node) for run in range(1, 6)] for node in 'acd']
        bc.categoryAxis.categoryNames = ['1', '2', '3', '4', '5']
        bc.categoryAxis.style = 'stacked'
        bc.categoryAxis.labels.fontName, bc.categoryAxis.labels.fontSize = 'Arial', 10
        bc.valueAxis.labels.fontName, bc.valueAxis.labels.fontSize = 'Arial', 10
        bc.valueAxis.valueMin, bc.valueAxis.valueMax, bc.valueAxis.valueStep = 0, 13, 2
        bc.valueAxis.visibleGrid = True
        bc.valueAxis.gridStrokeColor = HexColor('#E5E5E5')
        for j in range(3):
            bc.bars[j].fillColor, bc.bars[j].strokeColor = COLORS[j], white
        d.add(bc)
        text(d, x+195, 55, 'Lượt đo', 10, 'middle')
    legend(d, ['A → B', 'C → B', 'D → B'], 25)
    save_chart(d, '03-tcp-fanin', args)

    d = Drawing(820, 325)
    text(d, 20, 303, 'CPU tổng hợp của máy nhận B', 18)
    line_panel(d, 20, 65, 365, 175, [(NAMES[m], [r['CPU_B']['BusyPercent'] for r in single[m]]) for m in MODES], 'TCP một luồng A tới B', 'CPU busy (%)', 100, 25, '%d')
    line_panel(d, 435, 65, 365, 175, [(NAMES[m], [r['busy_percent'] for r in receiver[m]]) for m in MODES], 'Ba nguồn cùng gửi tới B', 'CPU busy (%)', 100, 25, '%d')
    legend(d, ['Peering', 'TGW'], 31)
    save_chart(d, '04-cpu-b', args)


def paragraph(doc, content, style=None):
    return doc.add_paragraph(content, style)


def table(doc, headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment, t.autofit = WD_TABLE_ALIGNMENT.CENTER, False
    for cell, width in zip(t.columns, widths):
        cell.width = Inches(width)
    pr = t._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        element = OxmlElement(f'w:{name}')
        for attr, value in [('val','single'),('sz','4'),('color','D9D9D9')]:
            element.set(qn('w:'+attr), value)
        borders.append(element)
    pr.append(borders)
    margins = OxmlElement('w:tblCellMar')
    for side in ['top','bottom','left','right']:
        e=OxmlElement('w:'+side); e.set(qn('w:w'),'90'); e.set(qn('w:type'),'dxa'); margins.append(e)
    pr.append(margins)
    for index, values in enumerate([headers, *rows]):
        row = t.rows[0] if index == 0 else t.add_row()
        if index == 0:
            repeat = OxmlElement('w:tblHeader'); row._tr.get_or_add_trPr().append(repeat)
        no_split=OxmlElement('w:cantSplit'); row._tr.get_or_add_trPr().append(no_split)
        for j, (cell, value) in enumerate(zip(row.cells, values)):
            cell.width=Inches(widths[j]); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(0)
            p.paragraph_format.line_spacing=1.05
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
            run=p.add_run(str(value)); run.font.size=Pt(10)
            sh=OxmlElement('w:shd'); sh.set(qn('w:fill'), '333333' if index == 0 else ('F3F5F7' if index%2==0 else 'FFFFFF')); cell._tc.get_or_add_tcPr().append(sh)
            if index == 0:
                run.bold=True; run.font.color.rgb=RGBColor(255,255,255)
    paragraph(doc, '').paragraph_format.space_after=Pt(1)
    return t


def figure(doc, filename, caption):
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(4)
    p.add_run().add_picture(str(CHARTS/filename), width=Inches(6.6))
    p.paragraph_format.keep_with_next=True
    p=paragraph(doc, caption, 'Caption'); p.paragraph_format.space_after=Pt(9)


def next_page(doc, heading):
    doc.add_page_break()
    doc.add_heading(heading, 1)


def hyperlink(p, label, url):
    rel=p.part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    h=OxmlElement('w:hyperlink'); h.set(qn('r:id'),rel)
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr'); col=OxmlElement('w:color'); col.set(qn('w:val'),'2166AC'); pr.append(col); r.append(pr)
    tx=OxmlElement('w:t'); tx.text=label; r.append(tx); h.append(r); p._p.append(h)


def build_document(rtt, single, fanin, receiver, summary):
    doc=Document(); sec=doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin=Inches(.7), Inches(.65)
    sec.left_margin, sec.right_margin=Inches(.9), Inches(.9)
    for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption']:
        style=doc.styles[name]; style.font.name='Arial'; style.font.color.rgb=RGBColor(0,0,0)
        style.paragraph_format.space_after=Pt(8)
    doc.styles['Normal'].font.size=Pt(11)
    doc.styles['Normal'].paragraph_format.line_spacing=1.13
    doc.styles['Title'].font.size=Pt(23)
    doc.styles['Heading 1'].font.size=Pt(16)
    doc.styles['Heading 2'].font.size=Pt(12)
    doc.styles['Caption'].font.size=Pt(9)
    # The bundled Word template carries a blue rule in its Title style.
    for style in doc.styles:
        for border in style.element.xpath('.//w:pBdr'):
            border.getparent().remove(border)
    hp=sec.header.paragraphs[0]; hp.add_run('NT531  |  Đánh giá hiệu năng VPC Peering và Transit Gateway').font.size=Pt(9)
    fp=sec.footer.paragraphs[0]; fp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    fp.add_run('Trang ').font.size=Pt(9)
    field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); fp._p.append(field)
    doc.core_properties.title='Kết quả đánh giá hiệu năng VPC Peering và Transit Gateway'
    doc.core_properties.subject='Chương kết quả từ sáu bộ đo thực nghiệm NT531'
    doc.add_paragraph('Kết quả đánh giá hiệu năng VPC Peering và Transit Gateway', 'Title')
    paragraph(doc, 'Chương kết quả thực nghiệm của đồ án NT531', 'Subtitle')
    paragraph(doc, 'Trong cấu hình bốn EC2 cùng loại và cùng vùng sẵn sàng, Peering có RTT khi rảnh thấp hơn TGW trong đợt đo đã thực hiện. Thông lượng TCP một luồng qua hai phương án gần nhau. Khi ba nguồn cùng gửi tới B, tổng thông lượng xấp xỉ đạt khoảng 11,6 Gbps ở cả hai phương án, đồng thời máy nhận ghi nhận bộ đếm ENA vượt giới hạn tăng. Kết quả phản ánh hệ thống thử nghiệm và chưa xác định năng lực tối đa của dịch vụ AWS.')
    doc.add_heading('1 Phạm vi và điều kiện đo', 1)
    table(doc, ['Thành phần','Cấu hình'], [
        ['Máy đo','A 10.10.10.212; B 10.20.10.155\nC 10.30.10.212; D 10.40.10.155'],
        ['EC2 và hệ điều hành','c6i.large; Amazon Linux 2023; AZ us-east-1a'],
        ['Mạng và công cụ','MTU 1500; iperf3 3.19.1; TCP cubic; NTP yes'],
        ['Đường đo','IP riêng giữa các EC2; Elastic IP dùng để quản trị'],
        ['So sánh kiến trúc','Peering toàn lưới 6 kết nối; TGW 1 gateway và 4 attachment'],
    ], [1.65,5.05])
    paragraph(doc, 'Bộ kết quả gồm ba điều kiện thử nghiệm, mỗi điều kiện đo qua Peering và TGW, mỗi phương án 5 lượt. Giữ nguyên các endpoint và đổi target của 12 route liên VPC. Hai phương án được đo nối tiếp; số thứ tự lượt là thứ tự trong từng phiên, không phải các mẫu ghép cặp cùng thời điểm.')
    table(doc, ['Điều kiện','Peering','TGW'],[
        ['RTT trung bình khi rảnh','0,2078 ms','0,5630 ms'],
        ['TCP một luồng A tới B','4,7828 Gbps','4,6083 Gbps'],
        ['TCP ba nguồn tới B\nTổng thông lượng xấp xỉ','11,6110 Gbps','11,5905 Gbps'],
    ],[3.1,1.8,1.8])
    paragraph(doc, 'Tất cả giá trị trong bảng là trung bình của 5 lượt. Tổng ba nguồn là tổng các trung bình theo cửa sổ riêng của từng nguồn; xem giới hạn thời gian ở mục 4.')

    architecture_pages(doc)

    next_page(doc, '2 Độ trễ khi mạng rảnh')
    paragraph(doc, 'A gửi ICMP tới B khi không chạy tải iperf3. Mỗi lượt gồm 100 gói, cách nhau 0,2 giây, payload 56 byte; nghỉ 5 giây giữa các lượt. RTT là thời gian đi và phản hồi về A, không phải độ trễ một chiều.')
    figure(doc, '01-rtt.png', 'Hình 4. RTT trung bình và lớn nhất của từng lượt; hai ô dùng thang trục dọc khác nhau.')
    table(doc, ['Chỉ số','Peering','TGW'],[
        ['Trung bình của RTT trung bình','0,2078 ms','0,5630 ms'],
        ['Min đến max RTT trung bình từng lượt','0,195–0,215 ms','0,501–0,666 ms'],
        ['SD mẫu của 5 RTT trung bình',f"{summary['rtt']['peering']['sample_sd']:.4f} ms".replace('.',','),f"{summary['rtt']['tgw']['sample_sd']:.4f} ms".replace('.',',')],
        ['RTT lớn nhất quan sát','0,256 ms','5,897 ms'],
        ['Phản hồi nhận được','500/500','500/500'],
    ],[3.2,1.75,1.75])
    paragraph(doc, 'Peering có RTT trung bình thấp hơn trong đợt đo này. Chênh lệch trung bình là 0,3552 ms. TGW có một lượt với RTT lớn nhất 5,897 ms; điểm này được giữ trong dữ liệu, chưa xác định nguyên nhân. Không ghi nhận mất gói ICMP trong 500 gói của mỗi phương án.')
    paragraph(doc, 'SD mẫu trong bảng mô tả độ phân tán giữa 5 giá trị RTT trung bình. Chỉ số mdev của ping mô tả độ phân tán RTT các gói trong một lượt; đây là hai cấp tổng hợp khác nhau. Năm lượt của một phiên chưa đủ để suy rộng độ ổn định qua nhiều thời điểm hoặc vùng sẵn sàng.')

    next_page(doc, '3 Thông lượng TCP một luồng')
    paragraph(doc, 'A chạy iperf3 tới B:5201 với một luồng TCP, bỏ 5 giây khởi động và đo 30 giây. Mỗi phương án có 5 lượt, nghỉ 10 giây giữa các lượt. Chọn thông lượng phía nhận làm chỉ số chính; đồng thời lưu JSON, mã thoát, CPU và ảnh chụp bộ đếm ENA.')
    figure(doc, '02-tcp-single.png', 'Hình 5. Thông lượng phía nhận và số lần truyền lại TCP theo từng lượt.')
    table(doc, ['Chỉ số trung bình hoặc khoảng','Peering','TGW'],[
        ['Receiver throughput trung bình','4,7828 Gbps','4,6083 Gbps'],
        ['SD mẫu thông lượng 5 lượt',f"{summary['tcp_single']['peering']['sample_sd']:.4f} Gbps".replace('.',','),f"{summary['tcp_single']['tgw']['sample_sd']:.4f} Gbps".replace('.',',')],
        ['Retransmits từng lượt', '48 253–57 185','0–671'],
        ['CPU busy A trung bình','20,95%','17,81%'],
        ['CPU busy B trung bình','18,66%','20,51%'],
        ['Delta 5 bộ đếm allowance ENA','Đều bằng 0','Đều bằng 0'],
    ],[3.2,1.75,1.75])
    paragraph(doc, 'Thông lượng phía nhận qua Peering cao hơn TGW khoảng 3,79% trong hai phiên này. Thông lượng từng phương án ít biến động giữa 5 lượt, trong khi Peering ghi nhận nhiều lần truyền lại hơn. Retransmits là số lần truyền lại TCP do iperf3 báo cáo, không phải phần trăm mất gói.')
    paragraph(doc, 'Các delta ENA được theo dõi bằng 0 chưa chứng minh toàn đường truyền không có hàng đợi hoặc mất gói. CPU là busy tổng hợp của máy, không phải riêng tiến trình iperf3. Dữ liệu hiện tại chưa chỉ ra nguyên nhân chênh lệch retransmission, cũng chưa tách được giới hạn endpoint khỏi ảnh hưởng của đường định tuyến.')

    next_page(doc, '4 Ba nguồn đồng thời gửi tới máy B')
    paragraph(doc, 'A, C và D mỗi máy gửi một luồng TCP tới B qua các cổng 5201, 5202 và 5203. Mỗi lượt bỏ 5 giây đầu, đo 30 giây; 5 lượt bắt đầu cách nhau 45 giây theo lịch chung. Kịch bản tạo tải hội tụ tại một máy nhận để quan sát thông lượng từng nguồn và giới hạn endpoint.')
    figure(doc, '03-tcp-fanin.png', 'Hình 6. Thông lượng từng nguồn và tổng xấp xỉ của ba nguồn trong mỗi lượt.')
    table(doc, ['Nguồn tới B','Peering mean Gbps','TGW mean Gbps'],[
        ['A','3,9583','3,7966'],['C','3,7799','3,7943'],['D','3,8728','3,9996'],['Tổng xấp xỉ','11,6110','11,5905'],
    ],[2.7,2,2])
    paragraph(doc, 'Tổng xấp xỉ TGW thấp hơn Peering 0,18% trong hai phiên đã đo. Thông lượng từng nguồn TGW thay đổi rõ hơn giữa các lượt, trong khi tổng xấp xỉ dao động ít. Các mẫu này chưa đủ để kết luận khác biệt có ý nghĩa thống kê, hai phương án tương đương hoặc một phương án chia tải công bằng hơn.')
    paragraph(doc, 'Độ lệch khởi chạy wrapper của các nguồn là khoảng 0,30–0,96 giây ở Peering và 0,78–0,82 giây ở TGW. Cửa sổ tạo tải chung xấp xỉ 29,05–29,71 giây và 29,19–29,23 giây. Đây là ước lượng từ wrapper start cộng 5 giây đến wrapper end, không phải mốc nội bộ iperf3. Tổng trên biểu đồ cộng các trung bình toàn cửa sổ riêng, chưa tính lại thông lượng theo interval trong cửa sổ chung.')

    next_page(doc, '5 CPU và bộ đếm ENA của máy nhận')
    figure(doc, '04-cpu-b.png', 'Hình 7. CPU busy tổng hợp B qua từng lượt ở điều kiện một nguồn và ba nguồn.')
    table(doc, ['Chỉ số máy B','Peering','TGW'],[
        ['CPU busy mean một nguồn','18,66%','20,51%'],
        ['CPU busy mean ba nguồn','59,18%','56,88%'],
        ['Delta bw_in_allowance_exceeded\nToàn phiên ba nguồn','1 434 501','6 608 210'],
        ['Delta pps_allowance_exceeded\nToàn phiên ba nguồn','160 457 411','77 094 456'],
        ['Delta bw_out conntrack linklocal\nToàn phiên ba nguồn','0 cho từng bộ đếm','0 cho từng bộ đếm'],
    ],[3.3,1.7,1.7])
    paragraph(doc, 'CPU busy được tính bằng 100 trừ %idle trên dòng all của mpstat. Với ba nguồn, B được tổng hợp theo năm cửa sổ 30 giây dự kiến của lịch chạy: Peering có 29–30 mẫu mỗi cửa sổ, TGW có 30 mẫu. Vì đây là CPU tổng hợp, một lõi hoặc một phần xử lý mạng vẫn có thể bị giới hạn khi CPU toàn máy chưa đạt 100%.')
    paragraph(doc, 'Theo tài liệu AWS [1], bw_in_allowance_exceeded đếm gói bị xếp hàng hoặc loại bỏ do vượt giới hạn băng thông nhận của instance; pps_allowance_exceeded theo dõi vượt giới hạn PPS hai chiều. Delta của hai bộ đếm trên B tăng ở cả hai phiên ba nguồn, là bằng chứng giới hạn endpoint tác động tới phép đo. Delta ENA của các máy gửi không tăng trong từng lượt.')
    paragraph(doc, 'Bộ đếm allowance không tự tăng chỉ vì thời gian đo dài hơn. Chúng tăng khi điều kiện vượt giới hạn xảy ra. Ảnh chụp trước và sau của B bao phủ toàn phiên, gồm cả chờ và nghỉ, nên chưa phân bổ được cho từng nguồn hoặc lượt. Không cộng hai delta thành số gói mất và không dùng chúng để suy ra phần trăm mất gói hay năng lực tối đa của Peering hoặc TGW.')

    next_page(doc, '6 Thảo luận và giới hạn của kết quả')
    doc.add_heading('Kết luận trong phạm vi thử nghiệm',2)
    paragraph(doc, 'Peering đạt RTT khi rảnh thấp hơn TGW với cùng cặp EC2. TCP một luồng đạt khoảng 4,78 và 4,61 Gbps; mức chênh lệch này cần được kiểm chứng qua nhiều phiên nếu muốn kết luận ổn định. Khi hội tụ ba nguồn tại B, tổng thông lượng xấp xỉ gần nhau và ENA ghi nhận vượt giới hạn tại máy nhận. Vì vậy, kết quả ba nguồn hữu ích để nhận diện giới hạn của hệ thống thử nghiệm hơn là xếp hạng năng lực tối đa của hai dịch vụ.')
    doc.add_heading('Các giới hạn cần trình bày khi bảo vệ',2)
    for s in [
        'Mỗi điều kiện chỉ có một phiên 5 lượt cho mỗi phương án, đo nối tiếp và chưa đổi thứ tự xen kẽ. Điều kiện theo thời gian có thể ảnh hưởng kết quả; độ phân tán nhỏ trong một phiên không thay thế độ tái lập giữa nhiều phiên.',
        'Thử nghiệm dùng một loại EC2, một AZ, một MTU và tải TCP ngắn. Chưa đo ổn định lâu dài hay kiểm soát trạng thái network burst của instance. Không suy rộng sang nhiều AZ, nhiều region, loại máy hoặc kích thước gói khác.',
        'Tổng thông lượng ba nguồn là ước lượng từ các trung bình riêng. CPU và ENA có cửa sổ tổng hợp khác nhau; chưa đủ để gán nguyên nhân truyền lại hoặc phân bổ từng delta ENA cho từng luồng.',
        'Bài hai cặp độc lập A tới B và C tới D qua Peering là dữ liệu bổ sung. Chưa kiểm tra đầy đủ file gốc và chưa có bộ TGW đối ứng nên không đưa vào sáu bộ chính hoặc kết luận định lượng của chương này.',
    ]:
        paragraph(doc, s, 'List Bullet')
    doc.add_heading('Bằng chứng và khả năng tái lập',2)
    paragraph(doc, 'Sáu bộ chính đã được kiểm tra và lưu cục bộ. Hai phiên ba nguồn có 146 file gốc mỗi phiên, gồm 15 JSON phía gửi và log CPU, ENA, metadata, mốc thời gian. Phiên Peering dùng epoch 1791293390; phiên TGW dùng epoch 1791296141. Các bản sao trùng thư mục không được tính là lượt đo độc lập. Kết quả hủy giữa chừng không dùng để tổng hợp.')
    paragraph(doc, 'Bảng và biểu đồ được tạo bằng scripts/build-results-report.py từ CSV RTT và các audit JSON trong results/formal. Số liệu chi tiết, SD mẫu và SHA256 của đầu vào nằm ở results/analysis/report-metrics.json. Chương này dùng dữ liệu thực nghiệm, không dùng bộ số liệu tổng hợp mô phỏng.')
    doc.add_heading('Tài liệu tham khảo',2)
    p=paragraph(doc, '[1] AWS. '); hyperlink(p,'Monitor network performance for ENA settings on your EC2 instance',ENA_URL)
    p.add_run('. Truy cập ngày 06/10/2026. Các định nghĩa bộ đếm được dùng để diễn giải mục 5.')
    paragraph(doc, 'Bước tiếp theo của đồ án là ghép chương này vào báo cáo, bổ sung cơ sở lý thuyết và phương pháp, chuẩn bị slide và minh chứng tái lập. Chỉ mở rộng thí nghiệm khi có câu hỏi nghiên cứu cụ thể chưa được dữ liệu hiện tại trả lời.')
    add_formula_pages(doc, summary, paragraph, table, next_page, hyperlink)
    add_context_pages(doc, paragraph, table, next_page, hyperlink)
    doc.save(DOCX)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--node',required=True); ap.add_argument('--node-modules',required=True)
    args=ap.parse_args()
    pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
    rtt, single, fanin, receiver, sources=load_data()
    summary={
        'scope':'six verified empirical datasets; five runs per dataset',
        'rtt':{m:stats([r['avg_ms'] for r in rtt[m]]) for m in MODES},
        'tcp_single':{m:stats([r['ReceiverGbps'] for r in single[m]]) for m in MODES},
        'fanin_approximate_total':{m:stats([r['sum_receiver_Gbps'] for r in fanin[m]['windows']]) for m in MODES},
        'rtt_rows':rtt,
        'single_rows':single,
        'fanin_metrics':{m:fanin[m]['metrics'] for m in MODES},
        'fanin_B_cpu':receiver,
        'architecture':{
            'region':'us-east-1','availability_zone':'us-east-1a',
            'nodes':{node:{'vpc_cidr':v[0],'subnet_cidr':v[1],'private_ip':v[2]} for node,v in NETWORK.items()},
            'peering_pairs':['ab','ac','ad','bc','bd','cd'],
            'transit_gateways':1,'vpc_attachments':4,'directed_inter_vpc_routes':12,'management_eips':4,
            'provenance':[{'path':f'infra/terraform/{name}','sha256':hashlib.sha256((ROOT/'infra/terraform'/name).read_bytes()).hexdigest()} for name in ['full-mesh.tf','transit-gateway.tf','routes.tf','elastic-ips.tf','expansion.tf','subnets.tf']],
            'notes':['Logical topology from project configuration and verified measurement metadata; not a fresh AWS inventory.',
                     'EIP management addresses are separate from private-IP benchmark paths.'],
        },
        'sources':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
        'notes':['Sample SD is descriptive across five run averages, not ping mdev or inferential confidence intervals.',
                 'Run indices across modes do not imply contemporaneous paired observations.',
                 'Fanin totals sum separate source-window averages, not interval-aligned common-window goodput.',
                 'B ENA deltas cover whole captures; no packet-loss percentage can be inferred.'],
    }
    summary['quantitative_methods'] = calculate(summary, ROOT)
    export_markdown(summary, ROOT)
    export_context_markdown(ROOT)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'report-metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    build_charts(rtt,single,fanin,receiver,args)
    build_architecture(args)
    build_document(rtt,single,fanin,receiver,summary)
    print(json.dumps({'docx':str(DOCX),'charts':4,'architecture_diagrams':3,'rtt_mean_ms':{m:summary['rtt'][m]['mean'] for m in MODES},'tcp_single_mean_Gbps':{m:summary['tcp_single'][m]['mean'] for m in MODES}},ensure_ascii=False))


if __name__ == '__main__':
    main()
