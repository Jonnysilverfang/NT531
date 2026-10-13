/** Local slide authoring. Does not call AWS or modify frozen research data. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const [runtimeModules, skillDir, pythonExecutable, revision='v1'] = process.argv.slice(2);
if (!runtimeModules || !skillDir || !pythonExecutable) throw Error('Pass runtime modules, Presentations skill dir, Python executable, optional revision');
process.env.RUNTIME_NODE_MODULES=runtimeModules;
const {Presentation, PresentationFile} = await import(pathToFileURL(path.join(runtimeModules,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation, applyPresentationChartFont} = await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
const root=process.cwd(), out=path.join(root,'docs/presentation'), temp=path.join(root,'tmp/defense-deck',revision);
await fs.mkdir(out,{recursive:true}); await fs.mkdir(temp,{recursive:true});
const read=async p=>JSON.parse(await fs.readFile(path.join(root,p),'utf8'));
const content=await read('docs/presentation/defense-content.json');
const rtt=await read('results/confirmation-rtt-v1/analysis.json');
const summary=await read('results/analysis/reduced-study-summary.json');
const queue=await read('results/analysis/queue-occupancy-audit.json');
const historical=await read('results/analysis/report-metrics.json');
if(rtt.completed_blocks!==5 || summary.slot_conditions.length!==8 || content.slides.length!==18) throw Error('Unexpected data scope');
const cases=summary.slot_conditions;
const worker=(slots)=>queue.study_results.find(s=>s.phase==='confirmatory_block' && s.block===3).conditions.find(c=>c.mode==='peering' && c.slots===slots && c.configured_arrival_rps===800).workers.find(w=>w.node==='c');
const q8=worker(8), q16=worker(16);
const fmt=(n,d=3)=>Number(n).toLocaleString('vi-VN',{minimumFractionDigits:d,maximumFractionDigits:d});
const C={ink:'#132D46',muted:'#4F6171',teal:'#00837D',orange:'#D86A24',pale:'#EAF4F4',line:'#D5E0E7',white:'#FFFFFF'};
const p=Presentation.create({slideSize:{width:1280,height:720}});
const FONT='Arial';
function text(s,value,x,y,w,h,size=28,{bold=false,color=C.ink,align='left',fill='none',middle=false}={}){
  const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});
  sh.text=value; sh.text.style={typeface:FONT,fontSize:size,bold,color,alignment:align,verticalAlignment:middle?'middle':'top',insets:0,autoFit:'none',wrap:'square'}; return sh;
}
function heading(s,t,n){text(s,t,64,44,1150,82,t.length>55?40:42,{bold:true});text(s,`${String(n).padStart(2,'0')}`,1175,675,48,25,18,{color:C.muted,align:'right'});}
function footer(s,t){text(s,t,64,655,1080,49,17,{color:C.muted});}
function node(s,label,x,y,w=175,h=78,color=C.teal){
  const sh=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:C.white,line:{fill:color,width:2}});
  sh.text=label;sh.text.style={typeface:FONT,fontSize:24,bold:true,color:C.ink,alignment:'center',verticalAlignment:'middle',insets:6};return sh;
}
function link(s,a,b,{arrow=false,color=C.teal,fromSide,toSide,kind='straight'}={}){
  return s.shapes.connect(a,b,{kind,fromSide,toSide,line:{fill:color,width:2},tail:{type:arrow?'arrow':'none',width:'med',length:'med'}});
}
function table(s,values,x,y,w,h,widths,fontsize=25){
  const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values,columnWidths:widths});
  t.borders.assign({fill:C.line,width:1,style:'solid'});
  for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
    const cell=t.getCell(r,c);cell.fill=r===0?C.ink:(r%2?C.white:'#F2F6F8');
    cell.text.style={typeface:FONT,fontSize:fontsize,bold:r===0,color:r===0?C.white:C.ink,verticalAlignment:'middle',insets:12};
  }
  return t;
}
function chart(s,cfg){
  // Portable Excel workbooks store up to 15 significant digits. Twelve retains
  // much more precision than the displayed results without changing raw data.
  cfg.series=cfg.series.map(v=>({...v,values:v.values.map(n=>Number(n.toPrecision(12)))}));
  const ch=s.charts.add('bar',cfg);applyPresentationChartFont(ch,{fontFamily:FONT});return ch;
}
async function image(s,file,x,y,w,h){const bytes=await fs.readFile(path.join(root,file));s.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/jpeg',alt:'Trace smoke thật đã lưu, replay giữ nguyên thời gian và ID',fit:'contain',position:{left:x,top:y,width:w,height:h}});}
const grid={style:'solid',fill:C.line,width:1};
for(let i=0;i<content.slides.length;i++){
  const d=content.slides[i],s=p.slides.add();s.background.fill=C.white;
  s.speakerNotes.text=`${d.seconds?`Thời lượng gợi ý: ${d.seconds} giây.\n\n`:'Phụ lục, chỉ mở khi cần.\n\n'}${d.script}\n\nNguồn:\n${d.sources.join('\n')}`;
  if(d.layout!=='cover')heading(s,d.title,i+1);
  switch(d.layout){
    case 'cover':
      s.background.fill=C.ink;
      text(s,content.course,64,60,1150,40,25,{color:'#B6DEDB'});
      text(s,content.title,64,170,1150,150,65,{color:C.white,bold:true});
      text(s,content.subtitle,64,335,1140,70,34,{color:'#DCE7ED'});
      text(s,content.members.map(m=>`${m.name} · ${m.student_id}`).join('\n'),64,460,700,140,25,{color:C.white});
      text(s,`Giảng viên: ${content.teacher}`,64,625,1135,45,25,{color:'#B6DEDB'});break;
    case 'question':
      text(s,'Mạng nhanh hơn có giúp ứng dụng\nđáp ứng deadline khi gần công suất?',64,175,1140,155,49,{bold:true});
      text(s,'RTT của hai đường mạng',64,385,530,50,32,{bold:true,color:C.teal});
      text(s,'So sánh cùng EC2, ghép hai mode\ntrong từng block.',64,450,530,125,28);
      text(s,'Khả năng phục vụ tại worker',675,385,540,50,32,{bold:true,color:C.orange});
      text(s,'Can thiệp 8 và 16 slots\nở tải 600 và 800 yêu cầu/s.',675,450,540,125,28);
      footer(s,'Hai lớp đo: ICMP cho RTT mạng và HTTP cho chất lượng ứng dụng.');break;
    case 'network': {
      text(s,'VPC Peering full mesh',64,135,560,45,31,{bold:true,color:C.teal});
      const a=node(s,'VPC A\nEC2 A',85,230),b=node(s,'VPC B\nEC2 B',390,230),c=node(s,'VPC C\nEC2 C',85,465),dd=node(s,'VPC D\nEC2 D',390,465);
      for(const [u,v]of [[a,b],[a,c],[a,dd],[b,c],[b,dd],[c,dd]])link(s,u,v);
      text(s,'6 kết nối cặp',135,575,360,40,29,{bold:true,color:C.teal,align:'center'});
      text(s,'Transit Gateway',680,135,530,45,31,{bold:true,color:C.orange});
      const ta=node(s,'VPC A',690,230,160,65,C.orange),tb=node(s,'VPC B',1045,230,160,65,C.orange),tc=node(s,'VPC C',690,465,160,65,C.orange),td=node(s,'VPC D',1045,465,160,65,C.orange),hub=node(s,'TGW',886,345,125,85,C.orange);
      for(const u of [ta,tb,tc,td])link(s,u,hub,{color:C.orange});
      text(s,'1 hub, 4 attachment',760,575,440,40,29,{bold:true,color:C.orange,align:'center'});
      footer(s,'Cùng bốn EC2. Đổi đích route để chọn mode. IP private cho phép đo, EIP cho SSH.');break;
    }
    case 'application': {
      const a=node(s,'A\nTạo tải',64,330,185,90),b=node(s,'B\nGateway',330,330,200,90),c=node(s,'C\nWorker',720,215,205,90),dd=node(s,'D\nWorker',720,470,205,90);
      link(s,a,b,{arrow:true,fromSide:'right',toSide:'left'});link(s,b,c,{arrow:true,kind:'elbow',fromSide:'right',toSide:'left'});link(s,b,dd,{arrow:true,kind:'elbow',fromSide:'right',toSide:'left'});
      text(s,'HTTP',256,292,105,35,23,{color:C.muted});
      text(s,'Hai lời gọi song song',570,150,545,40,29,{bold:true});
      text(s,'Hàng đợi trước slots\n8 hoặc 16 lời gọi\nphục vụ đồng thời',975,245,245,160,25);
      text(s,'Mỗi worker:\nI/O mô phỏng 10 ms\nPhản hồi 4 KiB',975,435,245,135,25);
      footer(s,'800 yêu cầu/s tại A tạo khoảng 800 lời gọi/s trên từng worker C và D.');break;
    }
    case 'design':
      text(s,'c6i.large · us-east-1a · MTU 1500',64,143,1140,45,31,{color:C.teal,bold:true});
      table(s,[['Phép đo','Đã thu','Trong mỗi block'],['RTT A–B','5 block','2 mode × 3 lượt × 100 probe'],['Ứng dụng','3 block','2 mode × 2 slots × 2 mức tải']],64,220,1150,220,[255,200,695],27);
      text(s,'Ứng dụng: 5 s warm-up, 15 s đo, deadline 50 ms.\nTổng 252.000 yêu cầu theo lịch qua 24 điều kiện.',64,465,1140,95,28);
      text(s,'Kế hoạch 16 block rút gọn vì ngân sách.\nThống kê mô tả trên dữ liệu đã thu.',64,578,1140,66,24,{color:C.muted});break;
    case 'metrics':
      text(s,'RTT',64,170,300,48,35,{bold:true,color:C.teal});
      text(s,'Thời gian đi và phản hồi\nĐơn vị: ms',64,237,340,100,29);
      text(s,'P95',464,170,340,48,35,{bold:true,color:C.teal});
      text(s,'k = ⌈0,95 × n⌉\nP95 = x₍ₖ₎',464,237,340,110,35);
      text(s,'SLI đúng hạn',863,170,350,48,35,{bold:true,color:C.teal});
      text(s,'p̂ = N_good / N_sched\nSLI = 100 × p̂ (%)',863,237,350,110,29);
      text(s,'n: số độ trễ hợp lệ. x₍ₖ₎: giá trị thứ k sau khi sắp tăng dần.\nN_good: số yêu cầu đúng hạn. N_sched: số yêu cầu theo lịch.\nĐúng hạn: HTTP thành công và hoàn thành ≤ 50 ms từ lịch gửi.',64,405,1140,175,27);
      footer(s,'QoS: trang PDF 4, 26, 41–42. Nearest rank là lựa chọn tính toán của nhóm.');break;
    case 'rtt':
      chart(s,{position:{left:64,top:150,width:810,height:460},categories:rtt.rows.map(r=>`Block ${r.block}`),series:[{name:'Peering',values:rtt.rows.map(r=>r.peering_ms),fill:C.teal},{name:'TGW',values:rtt.rows.map(r=>r.tgw_ms),fill:C.orange}],barOptions:{direction:'column',grouping:'clustered',gapWidth:90},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:21}},xAxis:{textStyle:{fontSize:20}},yAxis:{min:0,max:0.75,majorUnit:0.15,numberFormatCode:'0.00',title:{text:'RTT trung bình (ms)',textStyle:{fontSize:22}},majorGridlines:grid,textStyle:{fontSize:20}},dataLabels:{showValue:false}});
      text(s,'+0,3119 ms',900,200,300,65,45,{bold:true,color:C.orange});
      text(s,'TGW trừ Peering\nTrung bình 5 block',900,282,300,90,28);
      text(s,'Khoảng chênh lệch\n0,2303–0,4257 ms\n\n0 / 3.000 thiếu phản hồi',900,405,305,170,26);
      footer(s,'12–13/10/2026. Mỗi cột là trung bình một mode trong block. Nguồn: analysis RTT.');break;
    case 'deadline': {
      const v=(mode,slots)=>cases.find(c=>c.mode===mode&&c.slots===slots&&c.rate_rps===800).observed_deadline_success_percent/100;
      chart(s,{position:{left:64,top:155,width:820,height:455},categories:['Peering','TGW'],series:[{name:'8 slots',values:[v('peering',8),v('tgw',8)],fill:C.orange},{name:'16 slots',values:[v('peering',16),v('tgw',16)],fill:C.teal}],barOptions:{direction:'column',grouping:'clustered',gapWidth:125},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:22}},xAxis:{textStyle:{fontSize:23}},yAxis:{min:0,max:1.15,majorUnit:0.25,numberFormatCode:'0%',title:{text:'Tỷ lệ đúng hạn ≤ 50 ms',textStyle:{fontSize:22}},majorGridlines:grid,textStyle:{fontSize:20}},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0%',textStyle:{fontSize:23,bold:true}}});
      text(s,'+96,84',910,195,290,72,53,{bold:true,color:C.teal});
      text(s,'điểm phần trăm\nHiệu ứng trung bình\ncủa can thiệp slots',910,277,290,135,28);
      text(s,'800 yêu cầu/s\n3 block\n36.000 request/điều kiện',910,465,295,105,25);
      footer(s,'Tỷ lệ gộp các request quan sát. Hiệu ứng tính theo block. 100% chỉ trong cửa sổ đã đo.');break;
    }
    case 'p95':
      table(s,[['Đường mạng','Slots','P95 từng block (ms)'],...cases.filter(c=>c.rate_rps===800).map(c=>[c.mode==='peering'?'Peering':'TGW',String(c.slots),`${fmt(c.minimum_block_successful_completion_p95_ms)}–${fmt(c.maximum_block_successful_completion_p95_ms)}`])],64,175,1150,340,[280,190,680],30);
      text(s,'Ở 600 yêu cầu/s: cả 4 điều kiện đạt 100% đúng hạn\ntrong dữ liệu đã thu.',64,557,1140,75,29,{bold:true,color:C.teal});
      footer(s,'Min–max của P95 trong 3 block, không phải CI hoặc P95 gộp. Chỉ xét hoàn thành thành công.');break;
    case 'little':
      text(s,'Lq = λ × Wq',64,160,1140,85,65,{bold:true,color:C.teal});
      text(s,'Lq: số lời gọi chờ trung bình\nλ: tốc độ vào worker (lời gọi/s)\nWq: thời gian chờ trung bình (s)',64,265,490,180,30);
      text(s,`${fmt(q8.cohort_count_rate_per_second)} × ${fmt(q8.mean_wait_ms/1000,6)}`,605,279,610,60,37,{bold:true});
      text(s,`≈ ${fmt(q8.mean_queue_occupancy)} lời gọi chờ`,605,365,610,65,38,{bold:true,color:C.orange});
      text(s,'Worker C · Peering · 800 rps · block 3\n8 slots: Wq ≈ 700,951 ms\n16 slots: Wq ≈ 0,005239 ms',64,497,1140,125,29);
      footer(s,'Arrival: trang PDF 62–66. Cửa sổ chứa trọn cohort và đuôi xử lý. Kiểm tra nhất quán log.');break;
    case 'capacity':
      text(s,'μnom = M / s',64,163,525,65,43,{bold:true,color:C.teal});
      text(s,'ρnom = λcfg × s / M',675,163,540,65,43,{bold:true,color:C.teal});
      text(s,'M: slots trên một worker. s = 0,010 s/lời gọi.\nλcfg: tải cấu hình trên từng worker.',64,254,1140,83,27);
      table(s,[['Tải / worker','Slots','μnom (lời gọi/s)','ρnom'],['600 /s','8','800','0,75'],['800 /s','8','800','1,00'],['800 /s','16','1.600','0,50']],64,365,1150,240,[290,165,425,270],27);
      footer(s,'Ước lượng danh nghĩa từ slots và I/O mô phỏng. ρnom không phải %CPU. Arrival: trang PDF 3, 66.');break;
    case 'trace':
      await image(s,'docs/images/application/grafana-demo/02-trace-waterfall.jpg',64,142,858,477);
      text(s,'12 trace thật\n120 span',950,161,270,100,32,{bold:true,color:C.teal});
      text(s,'Collector nhận\nTempo lưu\nGrafana hiển thị',950,302,270,135,29);
      text(s,'Trace smoke đã lưu\nReplay giữ ID/thời gian\n10 span trong ảnh',950,482,265,105,23,{color:C.muted});
      footer(s,'Trace tải nhẹ minh họa luồng gọi. Log phiên chính đo hàng đợi ở 800 rps. Hostmetrics EC2 chưa bật.');break;
    case 'choice':
      table(s,[['Khía cạnh','Peering','TGW'],['RTT đã đo','Thấp hơn ở cả 5 block','Cao hơn trung bình 0,3119 ms'],['Bốn VPC full mesh','6 kết nối cặp','1 hub, 4 attachment'],['Quản trị topology','Quản lý theo cặp','Định tuyến tại hub']],64,170,1150,300,[295,395,460],26);
      text(s,'Ở 800 rps, thiếu slots làm deadline thấp ở cả hai mode.\nTăng khả năng phục vụ cải thiện rõ trong workload đã thử.',64,516,1140,92,31,{bold:true,color:C.teal});
      footer(s,'Ưu điểm topology theo tài liệu AWS. Chưa lượng hóa công sức quản trị hoặc chứng minh giới hạn AWS.');break;
    case 'closing':
      text(s,'Peering có RTT thấp hơn\ntrong cấu hình đã đo',64,160,1140,112,45,{bold:true,color:C.teal});
      text(s,'Chất lượng ứng dụng còn phụ thuộc\nkhả năng phục vụ và thời gian chờ',64,320,1140,122,44,{bold:true});
      text(s,'Minh chứng: raw và route proof, bảng kết quả, log Little, trace Grafana.\nDemo trực tiếp hoặc video dùng dữ liệu lịch sử có nhãn rõ ràng.',64,502,1140,98,27);
      footer(s,'github.com/Jonnysilverfang/NT531 · nhánh minh-work');break;
    case 'historical':
      table(s,[['Bộ đo lịch sử','Peering','TGW'],['RTT mạng rảnh (ms)',fmt(historical.rtt.peering.mean),fmt(historical.rtt.tgw.mean)],['TCP 1 luồng nhận (Gbps)',fmt(historical.tcp_single.peering.mean),fmt(historical.tcp_single.tgw.mean)],['Tổng fan-in xấp xỉ (Gbps)',fmt(historical.fanin_approximate_total.peering.mean),fmt(historical.fanin_approximate_total.tgw.mean)]],64,170,1150,280,[560,295,295],27);
      text(s,'Hai cặp độc lập: A–B và C–D.\nFan-in: A, C, D cùng gửi về B.\nBộ đếm ENA: đối chiếu chênh trước và sau.',64,490,1140,125,28);
      footer(s,'Mỗi bộ 5 lượt, cohort lịch sử riêng. Tổng fan-in là xấp xỉ từ trung bình luồng, không đo capacity TGW.');break;
    case 'all_conditions':
      table(s,[['Mạng','Slots','rps','Đúng hạn / lịch','P95 từng block (ms)'],...cases.map(c=>[c.mode==='peering'?'Peering':'TGW',String(c.slots),String(c.rate_rps),`${c.deadline_success_count.toLocaleString('vi-VN')} / ${c.scheduled.toLocaleString('vi-VN')}`,`${fmt(c.minimum_block_successful_completion_p95_ms)}–${fmt(c.maximum_block_successful_completion_p95_ms)}`])],64,155,1150,475,[165,105,100,300,480],22);
      footer(s,'3 block. Tổng 252.000 request theo lịch. Không lỗi HTTP/JSON quan sát. P95 min–max, không phải CI.');break;
    case 'faq':
      table(s,[['Câu hỏi','Câu trả lời ngắn'],['Nhiều request có đủ kiểm định?','Request cùng phiên có thể phụ thuộc. Đơn vị lặp là block.'],['100% đúng hạn nghĩa là chắc chắn?','100% trong cửa sổ đã đo.'],['Little cần traffic Poisson?','Cohort hữu hạn đầy đủ không cần giả định Poisson.'],['Đã chứng minh giới hạn TGW?','Quan sát end-to-end và hàng đợi ứng dụng.'],['Dashboard CPU trống?','Hostmetrics EC2 chưa bật. CPU từ mpstat.']],64,164,1150,460,[400,750],25);
      footer(s,'5 block RTT, 3 block ứng dụng. Kế hoạch xác nhận 16 block đã rút gọn vì ngân sách.');break;
    case 'sources':
      text(s,'Bài giảng NT531',64,158,1120,45,32,{bold:true,color:C.teal});
      text(s,'Arrival Processes and Queuing Systems\nTrang PDF 3, 62–66: tải danh nghĩa, Little và concurrency.\n\nInternet Performance, QoS and Cloud-Native Metrics\nTrang PDF 4, 26, 31, 34, 39, 41–42: RTT, SLI, trace, phân vị.',64,219,1130,230,27);
      text(s,'Tài liệu AWS và dữ liệu nhóm',64,472,1120,45,32,{bold:true,color:C.teal});
      text(s,'AWS VPC Peering, AWS Transit Gateway (tài liệu chính thức).\nRepository: raw, protocols, analysis, queue audit và hướng dẫn demo.',64,532,1130,95,27);
      footer(s,'URL và đường dẫn nguồn trong Notes từng slide. Nhóm khai AI Usage và phân công theo thực tế.');break;
    default:throw Error(d.layout);
  }
}
const digest=async f=>createHash('sha256').update(await fs.readFile(path.join(root,f))).digest('hex');
const sources=['docs/presentation/defense-content.json','results/confirmation-rtt-v1/analysis.json','results/analysis/reduced-study-summary.json','results/analysis/queue-occupancy-audit.json','results/analysis/report-metrics.json','docs/images/application/grafana-demo/02-trace-waterfall.jpg'];
const finalPath=path.join(out,'NT531-thuyet-trinh.pptx');
const draft=path.join(temp,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(draft);
await fs.writeFile(path.join(temp,'deck-proto.json'),JSON.stringify(p.toProto()));
for(let i=0;i<p.slides.items.length;i++){
  const s=p.slides.items[i];
  await fs.writeFile(path.join(temp,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await (await p.export({slide:s,format:'png',scale:1})).arrayBuffer()));
}
const script=['# Lời thoại bảo vệ đồ án NT531','',`Giảng viên: ${content.teacher}.`,...content.members.map(m=>`${m.student_id} – ${m.name}`),'',`14 slide chính: khoảng ${Math.round(content.slides.slice(0,14).reduce((n,s)=>n+s.seconds,0)/60)} phút. 4 slide phụ lục mở khi hỏi. Lời thoại cũng nằm trong Notes của PowerPoint. Thời lượng gợi ý, nhóm tập nói và điều chỉnh theo lịch môn học.`, '', 'Gợi ý phân vai để nhóm tự thống nhất: Minh slide 1–5, Nhật slide 6–9, Kiên slide 10–14. Đây là gợi ý trình bày, không khai thay phân công thực hiện đồ án.',''];
for(let i=0;i<content.slides.length;i++){const d=content.slides[i];script.push(`## Slide ${i+1}. ${d.title}`,'',d.seconds?`Thời lượng: khoảng ${d.seconds} giây.`:'Phụ lục: không đọc hết trong phần chính.','',d.script,'');}
script.push('## Trước buổi báo cáo','', 'Mở PowerPoint ở Presenter View để nhìn Notes. Không đọc nguyên văn chữ trên slide. Chỉ vào trục, đơn vị và số block trước khi nêu kết quả. Nếu thầy yêu cầu thời gian ngắn hơn, giữ slide 1, 3, 4, 5, 7, 8, 10, 13, 14 và tóm tắt phần còn lại.', '', 'Bộ dữ liệu chốt 5/3 block là thống kê mô tả. Không dùng bản kế hoạch 16 block như kết quả đã hoàn thành. Không gọi tổng TCP fan-in là giới hạn TGW. Khi quay trace, nói rõ smoke replay, không giả làm phiên tải live.', '', 'Hạ tầng AWS chưa bị xóa trong lúc chuẩn bị slide. Việc stop hoặc destroy cần thực hiện và kiểm tra riêng sau khi đã lưu video. Chỉ giữ máy chạy trong khoảng cần quay.');
await fs.writeFile(path.join(out,'Loi-thoai-NT531.md'),script.join('\n')+'\n','utf8');
const tableOwners=[5,9,11,13,15,16,17];
const validation=await finalizePresentation({workspaceDir:root,candidatePath:draft,finalPath,pythonExecutable,integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:18,requiredNativeTableOwnerSlides:tableOwners,requiredNativeChartOwnerSlides:[7,8],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(temp,'validation.json')});
const proof={created_local:new Date().toLocaleString('sv-SE',{timeZone:'Asia/Ho_Chi_Minh'}),pptx:path.relative(root,finalPath).replaceAll('\\','/'),slides:18,main_slides:14,speaker_notes:18,editable_charts:2,editable_tables:7,no_AWS_calls:true,sources:await Promise.all(sources.map(async f=>({path:f,sha256:await digest(f)}))),pptx_sha256:await digest(path.relative(root,finalPath)),automated_finalization:'passed',visual_review:'pending'};
await fs.writeFile(path.join(temp,'proof.json'),JSON.stringify(proof,null,2)+'\n');
console.log(JSON.stringify({finalPath,slides:18,privatePreviewDir:temp,script:path.join(out,'Loi-thoai-NT531.md'),finalization:validation}));
