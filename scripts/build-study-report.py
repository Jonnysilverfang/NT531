"""Assemble one dated Markdown report from validated evidence, never collect data."""
import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZONE = dt.timezone(dt.timedelta(hours=7))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value, places=4):
    return f'{float(value):.{places}f}'.replace('.', ',')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '|' + '|'.join(['---'] * len(headers)) + '|'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def main():
    paths = ['results/analysis/report-metrics.json',
             'results/confirmation-rtt-v1/analysis.json',
             'results/application-slots-confirmation-v1/analysis.json',
             'results/analysis/queue-occupancy-audit.json']
    historical, rtt, slots, queues = [read(ROOT / p) for p in paths]
    fanin_path = 'results/analysis/fanin-sender-interval-figures.json'
    fanin = read(ROOT / fanin_path)
    assert fanin['files'] == 30 and fanin['total_non_omitted_sender_intervals'] == 900
    assert fanin['sender_retransmit_sums_match_summaries']
    assert sha(ROOT / 'results/analysis/fanin-common-window-audit.json') == fanin['source_audit_sha256']
    for source in fanin['sources'] + fanin['figures']:
        assert sha(ROOT / source['path']) == source['sha256']
    paths.append(fanin_path)
    assert sha(ROOT / paths[0]) == 'c8537ae84c0bf528b12a65edb53fc06dd4132e0966a3a6db1bfc4577ba42d94d'
    assert not rtt['issues'] and not slots['issues']
    for source in historical['sources'] + rtt['sources']:
        assert sha(ROOT / source['path']) == source['sha256']
    verified_paths = {source['path'] for source in historical['sources'] + rtt['sources'] + fanin['sources']}
    for block in slots['rows']:
        folder = ROOT / 'results/application-slots-confirmation-v1' / f"block-{block['block']:02d}" / block['attempt']
        analysis = read(folder / 'analysis.json')
        assert not analysis['issues']
        for source in analysis['sources']:
            assert sha(folder / source['path']) == source['sha256']
            verified_paths.add((folder / source['path']).relative_to(ROOT).as_posix())
    for study in queues['study_results']:
        for condition in study['conditions']:
            for source in condition['sources']:
                assert sha(ROOT / source['path']) == source['sha256']
                verified_paths.add(source['path'])
    # Keep the raw-derived tables synchronized; never invent an incomplete block.
    latest = slots['rows'][-1] if slots['rows'] else None
    q_latest = next((q for q in queues['study_results']
                     if latest and q['phase'] == 'confirmatory_block'
                     and (q['block'], q['attempt']) == (latest['block'], latest['attempt'])), None)
    if latest:
        assert q_latest, 'Rebuild the queue audit before the report'
        folder = ROOT / 'results/application-slots-confirmation-v1' / f"block-{latest['block']:02d}" / latest['attempt']
        assert sha(folder / 'analysis.json') == q_latest['validated_analysis_sha256']
    now = dt.datetime.now(ZONE)
    sections = [f'''# Đánh giá VPC Peering và Transit Gateway từ RTT đến chất lượng ứng dụng

Báo cáo tổng hợp đồ án NT531. Snapshot {now:%d/%m/%Y %H:%M} giờ Việt Nam.
Các bảng được tạo từ analysis và đối chiếu SHA với file nguồn; không dùng
ảnh chụp để thay raw. Báo cáo này ghép phần đã thực hiện; kết luận suy diễn
chỉ xuất hiện sau khi analyzer xác nhận đủ thiết kế.

## Câu hỏi và đóng góp

Đồ án so sánh hai cách kết nối cùng bốn VPC trên AWS. Phần vận chuyển đo
RTT, TCP goodput, truyền lại, CPU và ENA. Phần ứng dụng hỏi liệu thay đường
mạng hay tăng khả năng phục vụ đồng thời của worker giúp yêu cầu hoàn thành
đúng hạn hơn khi tải tăng. Can thiệp slots cùng log hàng đợi giúp giải thích
cơ chế thay vì chỉ xếp hạng hai con số thông lượng.

Bằng chứng lịch sử cho thấy Peering có RTT thấp hơn trong đợt đo đó.
Trong phiên engineering ứng dụng, tăng 8 lên 16 slots cải thiện deadline
rõ trên cả hai đường mạng. Hai đợt xác nhận mới kiểm tra khả năng lặp lại
của các hiệu ứng đã định trước; không gộp lịch sử, pilot hay engineering
vào mẫu xác nhận.

## Kiến trúc và cách so sánh

![Peering full mesh bốn VPC](images/results/00a-kien-truc-peering.png)

![Một TGW nối bốn VPC](images/results/00b-kien-truc-tgw.png)

Bốn máy c6i.large tại us-east-1a, MTU 1500. A/B/C/D thuộc bốn VPC có CIDR
khác nhau. EIP phục vụ quản trị; tải benchmark dùng private IP. Cả hai
phương án cung cấp liên lạc giữa cùng các cặp máy; TGW không bị giới hạn
chỉ chuyển A sang B. Route snapshot xác nhận đường thực dùng trước/sau đo.

Với n VPC cần liên lạc mọi cặp, Peering cần n(n−1)/2 kết nối cặp;
TGW cần n attachment VPC vào một gateway trong mô hình này. n=4 cho
6 peering so với 4 attachment. Đây là độ phức tạp topology logic,
không đo số đường vật lý hoặc công suất chuyển tiếp. Chi tiết cấu hình
và nguồn AWS ở [kiến trúc](03-bon-vpc.md).

```mermaid
flowchart LR
    A["A tạo yêu cầu theo lịch"] --> B["B gateway ứng dụng"]
    B --> C["C queue và 8 hoặc 16 slots"]
    B --> D["D queue và 8 hoặc 16 slots"]
    C --> B
    D --> B
    B --> A
```

B gọi C/D song song và A chờ cả hai kết quả. Mỗi request tạo một lời gọi
tại mỗi worker. 800 request/s tại A tương ứng tải danh nghĩa 800 lời gọi/s
ở từng worker, không phải 1.600 ở mỗi máy. B là gateway ứng dụng, không
phải TGW. Slots là giới hạn lời gọi phục vụ đồng thời, không phải vCPU.

## Các phép đo đã thực hiện

| Phần | Phép đo và mục đích | Vai trò bằng chứng |
|---|---|---|
| Vận chuyển lịch sử | RTT khi rảnh, TCP một luồng, hai cặp độc lập, ba nguồn fan-in vào B | Mô tả, chẩn đoán; khác cohort xác nhận mới |
| Pilot và calibration ứng dụng | Tải theo lịch, P95, deadline, vùng backlog, tracing mẫu | Chọn câu hỏi và kiểm tra công cụ; không tính block xác nhận |
| Engineering slots | Cùng đường mạng và mức tải, can thiệp 8 → 16 slots | Kiểm tra can thiệp và cơ chế trước xác nhận |
| Xác nhận RTT | Cặp A/B, cùng cohort, hai mode trong một block cân bằng thứ tự | Kiểm định chính riêng của RTT |
| Xác nhận slots | Hai route × hai mức tải × hai số slots trong mỗi block | Kiểm định chính riêng của hiệu ứng slots |
| Little từ queue logs | Ghép request ID, tích phân số chờ và tổng thời gian chờ | Giải thích cơ chế trên cùng raw, không phải mẫu độc lập mới |

Hai cặp độc lập A→B và C→D kiểm tra vận hành đồng thời, không tự tạo
điểm nghẽn dùng chung tại EC2. Fan-in A/C/D→B tạo điểm nhận dùng chung,
nhưng CPU/ENA tăng ở B chưa đủ phân lập giới hạn nội bộ mạng AWS.
''']
    legacy = []
    for mode in ['peering', 'tgw']:
        legacy.append([mode.upper(), number(historical['rtt'][mode]['mean']),
                       number(historical['tcp_single'][mode]['mean']),
                       number(historical['fanin_approximate_total'][mode]['mean']),
                       number(historical['quantitative_methods']['jain_descriptive'][mode]['mean_of_run_indices'], 6)])
    sections.append('## Kết quả vận chuyển lịch sử\n\n' + table(
        ['Mạng', 'RTT mean ms', 'TCP một luồng Gbps', 'Fan-in tổng xấp xỉ Gbps', 'Mean Jain từng lượt'], legacy) + '''

Mỗi bộ có năm lượt. RTT là mean các mean từng lượt; TCP dùng payload
phía nhận. Tổng fan-in cộng goodput của các nguồn trong cửa sổ riêng,
không phải byte trong một cửa sổ chung đã căn chỉnh. Audit 30 JSON không
có đủ thông tin để đổi thành tổng common-window chính xác.
[Audit cửa sổ](../results/analysis/fanin-common-window-audit.json).

Peering/TGW đo nối tiếp nên các lượt cùng số thứ tự không mặc nhiên là
cặp cùng thời điểm. Chênh lệch mô tả không thay kiểm định qua nhiều ngày.
Số liệu này không chứng minh băng thông tối đa dịch vụ; retransmission
không trực tiếp bằng tỷ lệ mất gói. Xem [chương kết quả lịch sử](13-tong-hop-ket-qua.md).

![Peering fan-in sender qua năm lượt](images/application/historical-fanin/peering-sender-intervals.png)

![TGW fan-in sender qua năm lượt](images/application/historical-fanin/tgw-sender-intervals.png)

Đồ thị từ 30 JSON cũ bỏ interval có `omitted=true`, giữ thời gian riêng của
mỗi client sau khi iperf reset omit. Cột đầu là payload phía **gửi**, không
đổi nhãn thành goodput nhận chung cửa sổ. RTT TCP là trạng thái socket tại
interval, không phải ping khi rảnh. Truyền lại/s chia counter interval cho
thời lượng thực; không biến thành phần trăm mất gói. Các lượt cùng số giữa
hai mode không là cặp ghép thời gian. [SHA và audit interval](../results/analysis/fanin-sender-interval-figures.json).
''')
    sections.append(f'''## Thiết kế xác nhận được khóa trước khi đo

RTT hiện có **{rtt['completed_blocks']}/16 block** trên {len(rtt['local_dates'])} ngày;
slots có **{slots['completed_blocks']}/16 block** trên {len(slots['local_dates'])} ngày.
Mỗi nghiên cứu cần 16 block hợp lệ, ít nhất bốn ngày địa phương và start
cách nhau ít nhất hai giờ. Slots yêu cầu uptime tối thiểu 30 phút.

RTT giữ payload 56 byte, 100 gói/lượt, interval 0,2 s, ba lượt/mode;
không chạy tải thử nghiệm. Slots giữ I/O mô phỏng 10 ms, payload 4.096 byte,
deadline 50 ms, timeout 2 s, rate 600/800 rps, slots 8/16. Mỗi điều kiện có
fresh server, warm-up 5 s, drain, đo 15 s; tracing đầy đủ tắt ở cả hai mode.

Đơn vị suy diễn là block. Hàng nghìn request cùng phiên hoặc 100 gói cùng
lượt không được coi là hàng nghìn block độc lập. Thứ tự route/điều kiện
đã cân bằng trước; không đổi ngưỡng hoặc dừng sớm khi thấy kết quả thuận lợi.
Giữ lỗi kỹ thuật; chỉ phân xử retry có lý do ngoài outcome.

### Công thức và ký hiệu

Với block j, định nghĩa chênh lệch RTT và hiệu ứng slots tại 800 rps:

\\[
\\Delta_j=\\overline{{RTT}}_{{T,j}}-\\overline{{RTT}}_{{P,j}},\\qquad
\\widehat p_{{m,c,j}}=\\frac{{N_{{\\mathrm{{đúng\\ hạn}}}}}}{{N_{{\\mathrm{{theo\\ lịch}}}}}},
\\qquad d_j=\\frac{{(\\widehat p_{{P,16,j}}-\\widehat p_{{P,8,j}})
+(\\widehat p_{{T,16,j}}-\\widehat p_{{T,8,j}})}}{{2}}.
\\]

P là Peering, T là TGW, m là mode, c là slots mỗi worker. Δ có đơn vị ms;
p và d là tỷ lệ không đơn vị. Đúng hạn chia cho mọi request theo lịch,
bao gồm lỗi/không gửi được; P95 latency chỉ tính request thành công và
phải ghi rõ mẫu số riêng. 100d là mức tăng **điểm phần trăm**.

Trong từng nghiên cứu, Zj=1 nếu Δj>0,1 ms (RTT) hoặc dj>0,10 (slots),
ngược lại bằng 0. K là số block vượt ngưỡng, θ là xác suất một block
vượt ngưỡng trong quá trình lấy mẫu phù hợp. Kiểm định riêng H0: θ≤0,5,
H1: θ>0,5, α=0,05. Với n=16 block:

\\[
K=\\sum_{{j=1}}^{{16}}Z_j,\\qquad
p_{{\\mathrm{{exact}}}}=\\sum_{{k=K}}^{{16}}\\binom{{16}}{{k}}2^{{-16}}.
\\]

K≥12 cho ngưỡng bác bỏ; tại K=12, đuôi null bằng 0,0384063721.
Đó là tính thiết kế, không phải p-value thực nghiệm trước khi hoàn tất.
Cận dưới θ một phía 95% giải P(Binomial(16,θL)≥K)=0,05 khi K>0;
K=0 thì θL=0. K và cận θ khác tỷ lệ request đúng hạn p.

Slots còn báo CI bootstrap 95% phụ trợ bằng resample nguyên block
20.000 lần; dùng cùng chỉ số block cho các đối chiếu để giữ ghép cặp.
Đây là phân tích mô tả phụ, không kiểm định tương đương. Mỗi kiểm định
chính có α riêng, không khẳng định mức sai số đồng thời 5% cho mọi câu.
Khoảng cách hai giờ không chứng minh độc lập; suy luận vẫn có điều kiện
về quá trình lấy mẫu và tương quan block.
''')
    rtt_rows = [[b['block'], dt.datetime.fromisoformat(b['started_utc']).astimezone(ZONE).strftime('%d/%m %H:%M'),
                 ' → '.join(b['order']), number(b['peering_ms']), number(b['tgw_ms']),
                 number(b['difference_ms']), b['missing_replies']] for b in rtt['rows']]
    sections.append('## Kết quả xác nhận RTT\n\n' + table(
        ['Block', 'Giờ Việt Nam', 'Thứ tự', 'Peering ms', 'TGW ms', 'Δ ms', 'Mất phản hồi'], rtt_rows))
    sections.append('![RTT ghép cặp theo block](images/application/confirmation-progress/rtt-blocks.png)')
    if latest:
        app_rows = []
        for rate in [600, 800]:
            for mode in ['peering', 'tgw']:
                for count in [8, 16]:
                    row = next(x for x in latest['rows'] if (x['mode'], x['slots'], x['rate_rps']) == (mode, count, rate))
                    app_rows.append([mode.upper(), count, rate, row['scheduled'],
                                     number(100 * row['deadline_success_count'] / row['scheduled'], 3),
                                     number(row['successful_completion_p95_ms'], 3), row['failed']])
        sections.append(f"## Kết quả xác nhận slots mới nhất\n\nBlock {latest['block']}, bắt đầu UTC {latest['started_utc']}.\n\n" + table(
            ['Mạng', 'Slots', 'rps', 'Theo lịch', 'Đúng hạn %', 'P95 thành công ms', 'Lỗi'], app_rows) +
            f"\n\nHiệu ứng dj của block này là **{number(Decimal(latest['improvement']) * 100)} điểm phần trăm**.\n"
            'Giữ mọi block trong bảng hiệu ứng sau; không chỉ trình bày block thuận lợi nhất.\n\n' + table(
                ['Block', 'Giờ Việt Nam', 'Tăng đúng hạn mean hai route điểm %'],
                [[b['block'], dt.datetime.fromisoformat(b['started_utc']).astimezone(ZONE).strftime('%d/%m %H:%M'),
                  number(Decimal(b['improvement']) * 100)] for b in slots['rows']]))
        sections.append('![Đúng hạn và hiệu ứng slots theo block](images/application/confirmation-progress/slots-blocks.png)')
        q_rows = []
        for condition in sorted(q_latest['conditions'], key=lambda c: (c['mode'], c['slots'])):
            if condition['configured_arrival_rps'] != 800:
                continue
            for w in condition['workers']:
                q_rows.append([condition['mode'].upper(), condition['slots'], w['node'].upper(),
                               number(w['mean_wait_ms'], 6), number(w['mean_queue_occupancy'], 6),
                               w['peak_queue_occupancy'], number(w['cohort_count_rate_per_second'], 3)])
        sections.append('## Giải thích cơ chế bằng hàng đợi ứng dụng\n\n' + table(
            ['Mạng', 'Slots', 'Worker', 'Mean chờ ms', 'Mean số chờ', 'Peak số chờ', 'N/T lời gọi mỗi s'], q_rows) + r'''

Mỗi worker dùng cửa sổ chứa trọn entry/exit của request ID đo, gồm đuôi
xử lý; không bỏ các lời gọi hủy. Với N lời gọi, T là thời lượng cửa sổ,
Wq,i là thời gian chờ của lời gọi i và QC(t) là số đang chờ thuộc cohort:

\[
\overline L_{q,C}=\frac{1}{T}\int Q_C(t)\,dt
=\frac{1}{T}\sum_{i=1}^{N}W_{q,i}
=\underbrace{\frac{N}{T}}_{\lambda_C}
\underbrace{\frac{1}{N}\sum_{i=1}^{N}W_{q,i}}_{\overline W_q}.
\]

λC có đơn vị lời gọi/s, Wq là s, Lq là số lời gọi trung bình. Khi backlog
có đuôi, N/T khác rate cấu hình 800. Không nhân 800 với mean chờ rồi
gán thành số chờ của cửa sổ này; không thay mean bằng P95.
Đây là đẳng thức hữu hạn, không cần giả định Poisson/trạng thái dừng.
Hai cách tính trên cùng timestamp kiểm tra nhất quán, không tạo bằng
chứng thống kê độc lập hoặc chứng minh clock/logger luôn đúng.
[Chứng minh, ký hiệu và ví dụ đầy đủ](33-hang-doi-va-dinh-luat-little.md).
''' + f"\n![Hàng đợi block {latest['block']}](images/application/queue-occupancy/block-{latest['block']:02d}-queue.png)\n")
    sections.append('## Kết luận theo mức bằng chứng\n\n')
    for label, study, flag in [('RTT', rtt, 'reject_primary_null'), ('Slots', slots, 'majority_improvement_supported')]:
        result = study['inferential_result']
        if result is None:
            sections.append(f"**{label}:** {study['completed_blocks']}/16 block; chưa công bố p-value hoặc kết luận xác nhận. Các bảng trên mô tả block đã kiểm chứng.\n")
        else:
            assert study['completed_blocks'] == 16 and len(study['local_dates']) >= 4
            sections.append(f"**{label}:** đủ 16 block, K={result['above_margin_blocks']}, p exact={number(result['one_sided_exact_p'], 8)}, cận θ một phía 95%={number(result['probability_lower_one_sided_95'], 6)}. " +
                            ('Ủng hộ giả thuyết hiệu ứng vượt ngưỡng trong đa số block.' if result[flag] else 'Chưa đủ bằng chứng bác bỏ H0; không kết luận tương đương hoặc không có hiệu ứng.') + '\n')
    sections.append('''
**Kiến trúc:** full mesh Peering có số kết nối cặp tăng bậc hai theo n;
TGW dùng topology trung tâm với attachment VPC tăng tuyến tính trong mô
hình này. Lợi ích quản trị topology tách khỏi hiệu năng đã đo.

**Ứng dụng:** engineering và block xác nhận đã thu hỗ trợ vai trò của giới
hạn đồng thời worker và backlog trong workload mô phỏng. Phải hoàn tất
đợt xác nhận trước phát biểu xác suất lặp lại; không gọi 16 slots là tối ưu
mọi ứng dụng hoặc quy mọi trễ hạn cho mạng/CPU.

Đồ án không tìm một dịch vụ thắng tổng quát. Nó cung cấp phép so sánh có
điều kiện, can thiệp có kiểm soát và raw tái tạo để chỉ ra quyết định thay
mạng cần xét cùng deadline và khả năng phục vụ của ứng dụng.

## Liên hệ bài giảng nghiên cứu và quan sát

Arrival Processes and Queuing Systems gắn với arrivals theo lịch, Wq,
slots và Little. Congestion Control gắn với TCP cwnd, RTT, retransmission
và goodput; CUBIC thực dùng không được mô tả như mọi bước Reno/Tahoe.
Internet Performance QoS and Cloud Native Metrics gắn với phân vị, ECDF,
SLI deadline và distributed tracing. [Đối chiếu bài giảng](17-doi-chieu-bai-giang-va-cong-cu.md).

Little liên hệ số tác vụ trung bình, tốc độ vào và thời gian lưu; sample
path hữu hạn ở đây có phép chứng minh và ranh giới cụ thể. Nguồn nền:
[Sigman 2009](https://www.columbia.edu/~ks20/stochastic-I/stochastic-I-LL.pdf),
[Little 2011](https://pubsonline.informs.org/doi/10.1287/opre.1110.0940).
Độ trễ đuôi khi mức sử dụng và độ phức tạp dịch vụ tăng là câu hỏi liên
quan trong [The Tail at Scale](https://research.google/pubs/the-tail-at-scale/);
workload hai worker không tái tạo quy mô Google. Theo
[ASA 2016](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf),
p-value không cho xác suất giả thuyết đúng hay độ lớn hiệu ứng.

OpenTelemetry giúp quan sát lời gọi. Đã kiểm tra Collector → Tempo →
Grafana bằng replay 12 traces thật/120 spans; không tuyên bố OTLP live
hoặc hostmetrics EC2 đã triển khai. Tracing đầy đủ tắt trong primary.
Thêm công cụ không thay thiết kế lấy mẫu hay kiểm định.

## Tái tạo và việc còn lại

Nguồn tổng hợp: [metrics lịch sử](../results/analysis/report-metrics.json),
[RTT](../results/confirmation-rtt-v1/analysis.json),
[slots](../results/application-slots-confirmation-v1/analysis.json),
[queue audit](../results/analysis/queue-occupancy-audit.json),
[SHA của snapshot báo cáo](../results/analysis/study-report.json).

```powershell
py scripts/audit-queue-occupancy.py
tmp/application-venv/Scripts/python.exe scripts/plot-queue-occupancy.py
tmp/application-venv/Scripts/python.exe scripts/plot-confirmation-progress.py
tmp/application-venv/Scripts/python.exe scripts/plot-fanin-history.py
py scripts/build-study-report.py
```

Hoàn tất các block còn lại theo protocol, rồi RTT khi tải thuộc phần thăm
dò đã định. Chốt effect/cận xác suất/CI từ analyzer; ghép vào phụ lục Word,
kiểm tra từng trang và chuẩn bị demo từ dữ liệu đã lưu. Không cần dựng
thêm VPC hay công cụ để hoàn thành hai giả thuyết chính.

Mỗi phiên AWS sao lưu và stop bốn EC2; giữ EBS/EIP/TGW theo yêu cầu.
Lịch tự tiếp tục, giới hạn ngày và trạng thái hiện hành ở
[tài liệu 32](32-trang-thai-xac-nhan.md). Phần code/raw đã rà soát công bố
trên nhánh minh-work; state, credentials, SSH key và ZIP riêng không công bố.

AI Usage Declaration cần nhóm điền theo việc dùng thực tế khi nộp. Các
thành viên phải tự giải thích thiết kế, công thức, code và kết luận; báo
cáo này không khai thay tác giả hoặc việc nhóm chưa làm.
''')
    out = ROOT / 'docs/34-bao-cao-tong-hop.md'
    out.write_text('\n\n'.join(sections).rstrip() + '\n', encoding='utf-8')
    proof = dict(created_local=now.isoformat(), report_sha256=sha(out),
                 rtt_blocks=rtt['completed_blocks'], slots_blocks=slots['completed_blocks'],
                 raw_source_hash_checks=len(verified_paths), no_AWS_calls=True,
                 sources=[dict(path=p, sha256=sha(ROOT / p)) for p in paths])
    (ROOT / 'results/analysis/study-report.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
