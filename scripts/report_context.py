"""Beginner concepts, bounded conclusions and the proposed completion plan.

These pages describe existing observations and future work. They do not run
experiments, change infrastructure or upgrade architectural facts to measurements.
"""

PEERING = 'https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html'
OPTIONS = 'https://docs.aws.amazon.com/whitepapers/latest/aws-vpc-connectivity-options/amazon-vpc-to-amazon-vpc-connectivity-options.html'
TGW = 'https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html'
PRICE = 'https://aws.amazon.com/transit-gateway/pricing/'
ENA = 'https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html'
BLOCKS = 'https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm'

NETWORK = [
    ('VPC và subnet', 'VPC là mạng riêng logic trên AWS; subnet là một phần dải địa chỉ của VPC trong một AZ. Đồ án dùng bốn VPC có CIDR khác nhau, mỗi VPC có một EC2 làm điểm gửi hoặc nhận.'),
    ('CIDR và private IP', 'CIDR viết dải địa chỉ theo dạng 10.10.0.0/16. Private IP là địa chỉ của EC2 bên trong mạng, ví dụ A là 10.10.10.212. Bài đo dùng private IP để đi qua kết nối liên VPC.'),
    ('Route table và security group', 'Route table chọn nơi chuyển gói theo địa chỉ đích; security group cho phép hoặc chặn lưu lượng tới EC2. Có kết nối Peering/TGW chưa đủ: cần route hai chiều và quyền truy cập phù hợp.'),
    ('Peering và tính không bắc cầu', 'Peering nối trực tiếp một cặp VPC. Có AB và BC không tự tạo đường A tới C qua B. Muốn mọi cặp trong bốn VPC liên lạc trực tiếp, mô hình toàn lưới cần sáu kết nối.'),
    ('TGW và attachment', 'TGW là router vùng do AWS quản lý; attachment nối một VPC vào TGW. Bốn VPC dùng bốn attachment. TGW chuyển tiếp giữa các attachment theo route; các VPC không tự liên lạc chỉ vì đã gắn vào TGW.'),
    ('Association và propagation', 'Association chọn bảng TGW dùng để tra đường cho lưu lượng đi vào từ attachment. Propagation đưa dải địa chỉ của attachment vào bảng TGW. Chúng khác với route trong bảng subnet của từng VPC.'),
    ('EIP và AZ', 'Elastic IP là IP công cộng cố định để quản trị SSH trong đồ án. AZ là vùng sẵn sàng thuộc một region; bốn EC2 được đo cùng us-east-1a. EIP không nằm trên đường benchmark private IP.'),
]

METRICS = [
    ('RTT', 'Round trip time là thời gian từ khi A gửi gói tới khi A nhận phản hồi từ B. Ping đo RTT, không đo riêng độ trễ một chiều. Không lấy RTT chia hai rồi coi là số đo một chiều đã xác minh.'),
    ('Goodput và Gbps', 'Thông lượng phía nhận của iperf3 là tốc độ dữ liệu ứng dụng nhận được. Gbps là tỷ bit mỗi giây; 1 byte bằng 8 bit. Số này không phải tốc độ đường truyền vật lý hoặc tốc độ tải file bằng GB/s.'),
    ('Một luồng và fan-in', 'Một luồng là một kết nối TCP tải từ A tới B. Fan-in là nhiều nguồn cùng gửi tới một receiver: A, C, D tới B. Ba nguồn có thể tranh tài nguyên nhận của B dù dùng ba kết nối Peering khác nhau.'),
    ('MTU và PPS', 'MTU là kích thước gói IP lớn nhất giao diện gửi mà không cần phân mảnh ở đó; bài cơ sở dùng 1500 byte. PPS là số gói mỗi giây. Cùng thông lượng bit, gói nhỏ hơn có thể tạo nhiều gói hơn và tăng chi phí xử lý.'),
    ('Retransmission và mất phản hồi', 'TCP có thể truyền lại dữ liệu khi không nhận ACK theo cơ chế của nó. Retransmits của iperf3 là số lần truyền lại, không phải phần trăm mất gói. Ping mất phản hồi cũng không định vị được gói bị mất ở chiều nào.'),
    ('CPU và ENA', 'CPU busy tổng hợp là 100 trừ phần trăm idle, gồm mọi hoạt động trên máy. ENA là adapter mạng của EC2; delta allowance counter phản ánh số đếm tăng do vượt giới hạn instance. Không dùng counter tích lũy như throughput hoặc cộng chúng thành số gói mất.'),
    ('Lượt và đợt đo', 'Năm lượt liên tiếp của một phiên mô tả biến động trong phiên đó. Đợt bổ sung ở thời điểm khác, có cả hai mode và kiểm soát thứ tự, giúp đánh giá khả năng tái lập. Dòng log mỗi giây không phải các thí nghiệm độc lập.'),
]

COMPARISON = [
    ['RTT khi rảnh\nSố đo hiện có', '0,2078 ms\nThấp hơn trong phiên', '0,5630 ms'],
    ['TCP một luồng\nSố đo hiện có', '4,7828 Gbps\nCao hơn khoảng 3,79%', '4,6083 Gbps'],
    ['Ba nguồn tới B\nTổng xấp xỉ', '11,6110 Gbps', '11,5905 Gbps\nChưa chứng minh tương đương'],
    ['Bốn VPC toàn lưới\nĐặc điểm kiến trúc', '6 kết nối Peering', '1 TGW và 4 attachment'],
    ['Mở rộng thêm VPC\nNếu giữ toàn lưới', 'Thêm một kết nối tới mỗi VPC cũ', 'Thêm một attachment\nVẫn cần cập nhật route'],
    ['Quản lý định tuyến\nKhả năng dịch vụ', 'Theo các cặp VPC', 'Tập trung; có nhiều bảng để phân đoạn'],
    ['Chi phí kết nối\nTheo tài liệu AWS', 'Không phí tạo Peering;\ntruyền cùng AZ miễn phí', 'Phí attachment theo giờ\nvà xử lý dữ liệu theo GB'],
]

CONCLUSION = (
    'Trong cấu hình bốn EC2 c6i.large cùng AZ và MTU 1500 đã thử nghiệm, '
    'Peering có lợi thế về RTT khi rảnh và thông lượng TCP một luồng quan sát được. '
    'TGW có lợi thế kiến trúc khi cần kết nối nhiều VPC và tổ chức định tuyến tập trung. '
    'Với ít VPC, ưu tiên độ trễ và chi phí kết nối, Peering là lựa chọn phù hợp; '
    'khi quy mô và quản trị mạng là yêu cầu chính, TGW đáng cân nhắc. '
    'Bài fan-in ghi nhận giới hạn máy nhận ở cả hai mode, nên chưa xác định năng lực tối đa của dịch vụ.'
)

ROADMAP = [
    ['06–08/10', 'Chốt câu hỏi, rà bằng chứng route; kiểm tra khả năng căn chỉnh interval fan-in từ log có sẵn.'],
    ['09–12/10', 'Bổ sung đợt lặp RTT khi rảnh và TCP một luồng; cân bằng thứ tự hai mode, lưu route và metadata mỗi lần đổi.'],
    ['13–16/10', 'Nếu ngân sách cho phép, đo RTT khi có tải ở hai mức tải hữu hạn, đồng thời ghi CPU và ENA.'],
    ['17–20/10', 'Hoàn thiện báo cáo đầy đủ, thống kê giữa các đợt, mô hình chi phí và kết luận lựa chọn.'],
    ['21–23/10', 'Rà repo GitHub, tạo slide, chuẩn bị demo ngắn và bản ghi dự phòng.'],
    ['24–26/10', '24–25/10 tập bảo vệ và chốt bản; 26/10 trình bày.'],
]


def add_context_pages(doc, paragraph, table, next_page, hyperlink):
    next_page(doc, '8 Khái niệm mạng dành cho người mới')
    paragraph(doc, 'Đọc phần này trước các biểu đồ nếu chưa quen AWS. Ba sơ đồ ở phần kiến trúc minh họa đường đo và đường quản trị. Các khái niệm dưới đây giải thích vì sao cùng bốn EC2 có thể thử hai cách kết nối.')
    for title, explanation in NETWORK:
        p = paragraph(doc, '')
        p.add_run(title + '. ').bold = True
        p.add_run(explanation)
    p = paragraph(doc, 'Nguồn khái niệm kiến trúc: ')
    hyperlink(p, 'AWS VPC Peering', PEERING)
    p.add_run(' và ')
    hyperlink(p, 'AWS Transit Gateway', TGW)
    p.add_run('. Kiểm tra ngày 06/10/2026.')

    next_page(doc, '8 Khái niệm phép đo và cách đọc kết quả')
    for title, explanation in METRICS:
        p = paragraph(doc, '')
        p.add_run(title + '. ').bold = True
        p.add_run(explanation)
    paragraph(doc, 'Ví dụ đường đo A tới B: A tra route 10.20.0.0/16, đi qua Peering AB hoặc TGW tới B, rồi phản hồi về A theo route ngược. Listener iperf3 trên B có thể chạy nền trong lúc terminal B chỉ ghi CPU; không cần B chủ động chạy client.')
    p = paragraph(doc, 'Nguồn giải thích allowance counter: ')
    hyperlink(p, 'AWS ENA metrics', ENA)
    p.add_run('. Công thức, ký hiệu và ví dụ số nằm ở mục 7.')

    next_page(doc, '9 Kết luận lựa chọn Peering và TGW')
    paragraph(doc, CONCLUSION)
    table(doc, ['Tiêu chí và loại bằng chứng', 'Peering', 'TGW'], COMPARISON, [2.25, 2.2, 2.25])
    paragraph(doc, 'Lợi thế quản trị của TGW là khả năng kiến trúc theo tài liệu AWS; đồ án chưa đo thời gian thao tác quản trị hoặc diễn tập phân đoạn. Số attachment tăng tuyến tính không có nghĩa số route trong cấu hình hiện tại cũng tuyến tính: bốn VPC vẫn có tổng 12 route liên VPC ở cả hai mode.')
    paragraph(doc, 'Thông lượng một luồng Peering cao hơn nhưng số lần truyền lại cũng nhiều hơn. Vì vậy không xếp hạng một phương án tốt hơn ở mọi chỉ số. Tổng fan-in chênh 0,18% chỉ mô tả hai phiên; chưa phải bằng chứng tương đương thống kê.')
    p = paragraph(doc, 'Nguồn kiến trúc và chi phí: ')
    hyperlink(p, 'AWS connectivity options', OPTIONS)
    p.add_run('; ')
    hyperlink(p, 'Peering pricing', PEERING)
    p.add_run('; ')
    hyperlink(p, 'TGW pricing', PRICE)
    p.add_run('. EC2, EIP và các khoản khác không nằm trong so sánh phí kết nối này.')

    next_page(doc, '10 Kế hoạch củng cố trước ngày báo cáo')
    paragraph(doc, 'Đến 06/10/2026, hạ tầng bốn VPC, sáu bộ đo chính và chương kết quả đã có bằng chứng lưu cục bộ. Báo cáo đầy đủ, đo lặp giữa các đợt, slide và demo vẫn là phần cần hoàn thiện. Đây là kế hoạch đề xuất đến 26/10, chưa phải các phép đo đã thực hiện.')
    table(doc, ['Thời gian năm 2026', 'Sản phẩm cần hoàn thành'], ROADMAP, [1.35, 5.35])
    paragraph(doc, 'Ưu tiên ban đầu: bốn đợt bổ sung ở các thời điểm khác nhau, mỗi đợt có Peering và TGW, ba lượt mỗi bài RTT khi rảnh và TCP một luồng cho từng mode. Phân bổ hai đợt Peering trước và hai đợt TGW trước, xáo thứ tự đợt và ghi lịch từ trước. Bốn đợt là kế hoạch thực hành, không bảo đảm công suất thống kê.')
    paragraph(doc, 'Mỗi đợt lưu route hai chiều, thời gian UTC, công cụ, MTU, CPU/ENA và toàn bộ lượt lỗi. Phân tích chênh lệch theo đợt, không coi hàng trăm gói ping hoặc dòng log một giây là hàng trăm lần thử độc lập. Kiểm tra dữ liệu và chi phí trước khi mở rộng.')
    paragraph(doc, 'Bài mới ưu tiên là RTT khi có tải để trả lời độ trễ thay đổi ra sao khi endpoint chịu tải. Chưa ưu tiên thêm VPC, cross-region, UDP hoặc mua máy lớn hơn. Kế hoạch chi tiết và tiêu chí hoàn thành nằm trong docs/16-ke-hoach-hoan-thien-den-26-10.md.')
    p = paragraph(doc, 'Cơ sở thiết kế đợt lặp: ')
    hyperlink(p, 'NIST randomized block designs', BLOCKS)
    p.add_run('. Đổi thứ tự giúp giảm sai lệch theo thời gian; không bảo đảm loại bỏ ảnh hưởng burst credits.')


def export_context_markdown(root):
    lines = ['# Khái niệm và kết luận so sánh Peering với TGW', '',
             'Cập nhật 06/10/2026. Khái niệm dành cho người mới; kết luận dựa trên sáu bộ thực nghiệm đã kiểm tra, không phải giới hạn tuyệt đối của dịch vụ.', '',
             '## Kết luận dùng trong báo cáo', '', CONCLUSION, '',
             '## Khái niệm mạng', '']
    for title, explanation in NETWORK:
        lines.extend(['### ' + title, '', explanation, ''])
    lines.extend(['## Khái niệm đo', ''])
    for title, explanation in METRICS:
        lines.extend(['### ' + title, '', explanation, ''])
    lines.extend(['## Bảng so sánh', '', '| Tiêu chí | Peering | TGW |', '|---|---|---|'])
    for row in COMPARISON:
        lines.append('| ' + ' | '.join(cell.replace('\n', '<br>') for cell in row) + ' |')
    lines.extend(['', 'Khả năng định tuyến tập trung và phân đoạn là đặc điểm dịch vụ, chưa được đo thành lợi ích vận hành trong đồ án. Toàn lưới với N VPC cần N(N−1)/2 Peering hoặc N attachment TGW; trong cấu hình route theo từng CIDR hiện tại, tổng route liên VPC ở bảng subnet vẫn là N(N−1) cho cả hai phương án.', '',
                  '### Những điểm không nên đánh đồng', '',
                  '- Số kết nối hạ tầng khác số luồng TCP; cả Peering và TGW đều cho phép nhiều cặp gửi đồng thời.',
                  '- TGW không phải một EC2 router trung tâm do nhóm tự dựng; sơ đồ hub không chứng minh một điểm nghẽn vật lý duy nhất.',
                  '- TGW hỗ trợ nhiều bảng route nhưng không tự làm mạng an toàn hơn nếu cấu hình vẫn cho mọi attachment liên lạc.',
                  '- Fan-in đã đo là tổng xấp xỉ từ cửa sổ riêng. Chưa chứng minh tương đương thống kê hoặc giới hạn tối đa.',
                  '- RTT một phiên, chi phí dịch vụ và mức dễ quản trị là ba tiêu chí khác nhau; không cộng thành một điểm thắng tổng thể tùy ý.', '',
                  '## Nguồn đối chiếu', '',
                  f'- [AWS VPC Peering và chi phí cùng AZ]({PEERING}).',
                  f'- [AWS VPC connectivity options và tính không bắc cầu]({OPTIONS}).',
                  f'- [TGW route tables association propagation]({TGW}).',
                  f'- [TGW phí attachment và xử lý dữ liệu]({PRICE}).',
                  f'- [ENA allowance counters]({ENA}).', '',
                  'Nguồn số đo: [chương kết quả](13-tong-hop-ket-qua.md) và [report-metrics.json](../results/analysis/report-metrics.json).',
                  'Kế hoạch bổ sung: [hoàn thiện đến 26/10](16-ke-hoach-hoan-thien-den-26-10.md).', ''])
    (root / 'docs/15-khai-niem-va-ket-luan-so-sanh.md').write_text('\n'.join(lines), encoding='utf-8')
