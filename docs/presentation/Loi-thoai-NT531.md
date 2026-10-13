# Lời thoại bảo vệ đồ án NT531

Giảng viên: Đặng Lê Bảo Chương.
24521068 – Nguyễn Ngọc Minh
24521253 – Nguyễn Huy Nhật
24520885 – Nguyễn Trung Kiên

14 slide chính: khoảng 11 phút. 4 slide phụ lục mở khi hỏi. Lời thoại cũng nằm trong Notes của PowerPoint. Thời lượng gợi ý, nhóm tập nói và điều chỉnh theo lịch môn học.

Gợi ý phân vai để nhóm tự thống nhất: Minh slide 1–5, Nhật slide 6–9, Kiên slide 10–14. Đây là gợi ý trình bày, không khai thay phân công thực hiện đồ án.

## Slide 1. VPC Peering và Transit Gateway

Thời lượng: khoảng 25 giây.

Em chào thầy. Nhóm chúng em gồm Nguyễn Ngọc Minh, Nguyễn Huy Nhật và Nguyễn Trung Kiên. Đồ án đánh giá VPC Peering và Transit Gateway trên AWS, đồng thời xem khả năng phục vụ của ứng dụng ảnh hưởng thế nào đến chất lượng dịch vụ. Chúng em trình bày kiến trúc, kết quả đo và cách dùng định luật Little để giải thích hàng đợi.

## Slide 2. Câu hỏi nghiên cứu

Thời lượng: khoảng 40 giây.

Ban đầu nhóm muốn biết Peering hay Transit Gateway có hiệu năng tốt hơn. Nhưng một câu trả lời chung như vậy dễ bỏ qua ứng dụng. Vì vậy nhóm tách thành hai câu hỏi cụ thể. Thứ nhất, trên cùng cặp máy, RTT khác nhau bao nhiêu khi đổi đường mạng? Thứ hai, khi ứng dụng gần công suất phục vụ, giảm độ trễ mạng hay tăng khả năng xử lý sẽ cải thiện deadline rõ hơn? Hai câu hỏi dẫn đến hai nhóm thí nghiệm, đo mạng và can thiệp slots tại worker.

## Slide 3. Kiến trúc mạng trên cùng bốn VPC

Thời lượng: khoảng 50 giây.

Mỗi VPC có một EC2. Để bốn VPC liên lạc trực tiếp với nhau bằng Peering, nhóm tạo sáu kết nối cặp. Với Transit Gateway, bốn VPC gắn vào một hub bằng bốn attachment. Hai cách đều phục vụ cùng tập máy và cùng các chiều liên lạc. Khi đo, nhóm đổi đích route sang Peering hoặc TGW, không thay loại EC2. Lưu lượng đo dùng IP private. Elastic IP chỉ giúp nhóm SSH từ máy cá nhân, nên không nằm trên đường truyền benchmark.

## Slide 4. Ứng dụng gọi hai worker song song

Thời lượng: khoảng 50 giây.

Máy A tạo tải theo lịch và gửi HTTP đến gateway B. B gọi C và D song song, chờ cả hai kết quả rồi trả về A. Mỗi worker có hàng đợi trước một bộ slots. Một slot cho phép một lời gọi đang phục vụ, không phải một vCPU. Phần phục vụ mô phỏng chờ I/O mười mili giây và trả bốn KiB. Ở mức tám trăm yêu cầu mỗi giây tại A, mỗi worker nhận khoảng tám trăm lời gọi mỗi giây. Tổng C và D mới là một nghìn sáu trăm, không được nhầm thành tải trên từng worker.

## Slide 5. Thiết kế và dữ liệu đã chốt

Thời lượng: khoảng 50 giây.

Nhóm giữ cùng loại c6i.large, cùng Availability Zone us-east-1a và MTU một nghìn năm trăm. Đợt RTT có năm block, mỗi block chứa cả hai mode và mỗi mode có ba lượt, mỗi lượt một trăm gói. Đợt ứng dụng có ba block. Mỗi block thử đủ hai đường mạng, hai mức slots và hai mức tải, tức tám điều kiện. Nhóm đổi thứ tự các điều kiện theo lịch đã khóa. Kế hoạch xác nhận ban đầu là mười sáu block nhưng đã rút gọn vì ngân sách. Vì vậy kết quả hôm nay là thống kê mô tả, không trình bày p-value xác nhận.

## Slide 6. Chỉ số gắn với chất lượng dịch vụ

Thời lượng: khoảng 55 giây.

RTT là thời gian gói đi đến đích và phản hồi về máy gửi, đơn vị mili giây. Với ứng dụng, nhóm dùng P95 để nhìn các yêu cầu chậm, thay vì chỉ nhìn trung bình. Nhóm sắp độ trễ tăng dần và lấy vị trí làm tròn lên của không phẩy chín mươi lăm nhân số mẫu. SLI đúng hạn là số yêu cầu thành công trong năm mươi mili giây chia toàn bộ yêu cầu theo lịch. Năm mươi mili giây là ngưỡng thí nghiệm của nhóm. Yêu cầu HTTP thành công nhưng trả chậm vẫn không đạt deadline. P95 chỉ dùng các yêu cầu hoàn thành thành công, còn mẫu số SLI vẫn gồm cả lỗi và trễ.

## Slide 7. RTT Peering thấp hơn trong cả 5 block

Thời lượng: khoảng 50 giây.

Biểu đồ cho thấy RTT trung bình của hai mode trong từng block. Để so sánh, nhóm lấy TGW trừ Peering trong cùng block. Cả năm chênh lệch đều dương, với trung bình khoảng không phẩy ba một hai mili giây và khoảng từng block từ không phẩy hai ba không đến không phẩy bốn hai sáu. Không ghi nhận thiếu phản hồi trong ba nghìn probe được phân tích. Kết luận là Peering có RTT thấp hơn trong cấu hình và những block này. Nhóm không gọi phần chênh lệch là thời gian xử lý nội bộ của TGW, vì RTT còn gồm endpoint và toàn bộ đường đi.

## Slide 8. 16 slots cải thiện rõ tỷ lệ đúng hạn

Thời lượng: khoảng 55 giây.

Đây là kết quả tại tám trăm yêu cầu mỗi giây, tổng hợp ba block. Khi chỉ có tám slots, tỷ lệ đúng hạn khoảng ba phẩy không bốn phần trăm qua Peering và ba phẩy hai bảy phần trăm qua TGW. Khi tăng lên mười sáu slots, cả hai mode đạt đủ ba mươi sáu nghìn yêu cầu đúng hạn trên ba mươi sáu nghìn yêu cầu theo lịch. Hiệu ứng tăng slots, tính trong cùng block và mode rồi trung bình, là chín mươi sáu phẩy tám bốn điểm phần trăm. Đây là điểm phần trăm, không phải phần trăm tăng tốc. Một trăm phần trăm trong cửa sổ đo cũng không bảo đảm mọi phiên tương lai đều như vậy.

## Slide 9. P95 cho thấy độ trễ tăng mạnh ở 8 slots

Thời lượng: khoảng 40 giây.

Bảng này bổ sung ý nghĩa cho tỷ lệ deadline. Qua Peering, tám slots có P95 khoảng một phẩy ba năm đến một phẩy năm giây, còn mười sáu slots chỉ khoảng mười hai phẩy bảy mili giây. TGW có cùng hiện tượng tăng mạnh ở tám slots và giảm về khoảng mười ba mili giây ở mười sáu slots. Các khoảng là giá trị nhỏ nhất và lớn nhất của P95 từng block, không phải khoảng tin cậy. Tại sáu trăm yêu cầu mỗi giây, cả bốn điều kiện đều đạt một trăm phần trăm đúng hạn trong dữ liệu đã đo.

## Slide 10. Định luật Little giải thích số lời gọi chờ

Thời lượng: khoảng 65 giây.

Định luật Little trong bài giảng liên hệ số công việc trung bình, tốc độ và thời gian. Với phần hàng đợi, nhóm viết L q bằng lambda nhân W q. L q là số lời gọi chờ trung bình, lambda là lời gọi mỗi giây và W q là thời gian chờ trung bình tính bằng giây. Ví dụ worker C, Peering, tám slots, block ba: bảy trăm ba mươi hai phẩy hai tám bảy nhân không phẩy bảy không không chín năm một cho khoảng năm trăm mười ba phẩy hai chín bảy lời gọi chờ. Tốc độ này tính trên cửa sổ chứa trọn nhóm lời gọi và đuôi xử lý, nên khác tám trăm cấu hình. Hai vế cùng lấy từ log để kiểm tra nhất quán, không phải một kiểm định thống kê độc lập.

## Slide 11. 8 slots gần công suất phục vụ danh nghĩa

Thời lượng: khoảng 45 giây.

Nhóm dùng một ước lượng đơn giản để đọc cơ chế. Nếu M slots và mỗi lời gọi giữ slot s giây, công suất danh nghĩa là M chia s. Với tám slots và mười mili giây, công suất là tám trăm lời gọi mỗi giây. Tải tám trăm vì thế gần công suất danh nghĩa, ít dư địa cho overhead. Mười sáu slots cho công suất danh nghĩa một nghìn sáu trăm, tức mức tải chỉ bằng một nửa. Đây là mô hình slots và I/O giả lập, không phải giới hạn AWS, không phải phần trăm CPU, và nhóm không giả định traffic Poisson để dùng công thức M/M/1.

## Slide 12. OpenTelemetry theo dõi một yêu cầu

Thời lượng: khoảng 45 giây.

Nhóm giữ trace của hai phiên smoke thật, tổng cộng mười hai trace và một trăm hai mươi span. Collector nhận trace, Tempo lưu và Grafana hiển thị. Ảnh cho thấy một yêu cầu có mười span, tổng khoảng mười hai phẩy ba mili giây. Hai nhánh gọi C và D chồng thời gian nhau, thể hiện chạy song song. Worker queue khoảng mười ba đến mười bốn micro giây trong yêu cầu tải nhẹ này. Đây là trace nhập lại giữ nguyên ID và thời gian, không phải trace của phiên tám trăm rps. Log của thí nghiệm chính mới giải thích backlog khi tải, còn trace giúp hiểu luồng dịch vụ.

## Slide 13. Lựa chọn mạng và phạm vi kết luận

Thời lượng: khoảng 55 giây.

Hai phương án có ưu điểm ở những khía cạnh khác nhau. Trong phép đo của nhóm, Peering có RTT thấp hơn. Với topology cần kết nối nhiều VPC, TGW cung cấp hub và quản lý định tuyến tập trung, nhưng nhóm chưa đo công sức quản trị để lượng hóa lợi ích đó. Với bốn VPC, Peering full mesh cần sáu kết nối, TGW cần bốn attachment. Kết quả ứng dụng cho thấy ở tám trăm rps, đổi đường mạng vẫn không giải quyết deadline thấp khi worker có tám slots. Tăng khả năng phục vụ mới tạo cải thiện lớn trong workload này. Kết luận có cấu hình và điều kiện rõ ràng, không suy thành một phương án thắng mọi hệ thống.

## Slide 14. Kết luận và minh chứng demo

Thời lượng: khoảng 35 giây.

Đóng góp của nhóm là một quy trình so sánh trên cùng hạ tầng, có can thiệp slots để làm rõ điểm nghẽn ứng dụng, và có log hàng đợi kiểm tra bằng Little. Raw, code, số liệu tổng hợp và các bước demo đã lưu trong repository. Trong video, nhóm sẽ cho thấy bốn máy, route hoặc kết quả đo đã lưu, rồi mở một trace trên Grafana. Dữ liệu lịch sử được ghi rõ là kết quả đã đo. Nhóm không cần đo lại toàn bộ chỉ để quay màn hình. Em cảm ơn thầy và xin nhận câu hỏi.

## Slide 15. Phụ lục · TCP và fan-in lịch sử

Phụ lục: không đọc hết trong phần chính.

Nếu thầy hỏi phần TCP: mỗi bộ lịch sử có năm lượt. TCP một luồng phía nhận trung bình khoảng bốn phẩy bảy tám ba Gbps qua Peering và bốn phẩy sáu không tám qua TGW. Tổng fan-in ba nguồn về B khoảng mười một phẩy sáu một một và mười một phẩy năm chín một Gbps, là tổng xấp xỉ các trung bình luồng. Hai cặp độc lập dùng để quan sát tổng hoạt động đồng thời, không tạo chung một receiver. Fan-in dùng chung B nên phù hợp hơn để xem chia sẻ endpoint. Bộ đếm ENA phải đọc chênh trước và sau, không đọc giá trị tích lũy thành số lỗi của một lượt. Không gộp cohort lịch sử này vào đợt RTT mới.

## Slide 16. Phụ lục · Đủ 8 điều kiện ứng dụng

Phụ lục: không đọc hết trong phần chính.

Bảng có đầy đủ hai mode, hai mức slots và hai mức tải. Sáu trăm rps có hai mươi bảy nghìn yêu cầu mỗi điều kiện qua ba block. Tám trăm rps có ba mươi sáu nghìn. Tổng tất cả điều kiện là hai trăm năm mươi hai nghìn yêu cầu theo lịch. Không có lỗi HTTP/JSON được ghi nhận, nhưng nhiều yêu cầu ở tám slots, tám trăm rps hoàn thành quá deadline. Số request lớn không biến thành số block độc lập lớn. Đơn vị lặp để so sánh điều kiện vẫn là block.

## Slide 17. Phụ lục · Câu hỏi thường gặp

Phụ lục: không đọc hết trong phần chính.

Nếu hỏi vì sao không kiểm định với hàng trăm nghìn request: các request cùng một phiên chia sẻ tài nguyên và phụ thuộc nhau, nên không coi tất cả là lần lặp độc lập. Nếu hỏi một trăm phần trăm đúng hạn có chắc chắn không: đó là tần suất trong cửa sổ đã quan sát. Nếu hỏi Little có chứng minh hệ thống Poisson không: không, quan hệ hữu hạn của cohort đầy đủ không cần giả định đó. Nếu hỏi có chứng minh giới hạn TGW không: không, nhóm chỉ quan sát hiệu năng end-to-end và hàng đợi ứng dụng. Nếu hỏi Grafana CPU: hostmetrics EC2 chưa triển khai, CPU nghiên cứu lấy từ mpstat, không diễn giải dashboard trống thành CPU bằng không.

## Slide 18. Phụ lục · Nguồn và liên hệ bài giảng

Phụ lục: không đọc hết trong phần chính.

Nguồn chính gồm hai bài giảng giảng viên cung cấp, tài liệu chính thức AWS và raw do nhóm thu. Little liên hệ trang PDF sáu mươi hai đến sáu mươi sáu của bài Arrival Processes. SLI, trace và phân vị liên hệ bài Internet Performance tại các trang được ghi trên slide. Thuật toán nearest rank là lựa chọn triển khai của nhóm. Nhóm chưa có slide Xác suất thống kê UIT để tự gán chương học cho các kiểm định nâng cao. Phần AI hỗ trợ và phân công thực tế cần nhóm khai đúng yêu cầu môn học.

## Trước buổi báo cáo

Mở PowerPoint ở Presenter View để nhìn Notes. Không đọc nguyên văn chữ trên slide. Chỉ vào trục, đơn vị và số block trước khi nêu kết quả. Nếu thầy yêu cầu thời gian ngắn hơn, giữ slide 1, 3, 4, 5, 7, 8, 10, 13, 14 và tóm tắt phần còn lại.

Bộ dữ liệu chốt 5/3 block là thống kê mô tả. Không dùng bản kế hoạch 16 block như kết quả đã hoàn thành. Không gọi tổng TCP fan-in là giới hạn TGW. Khi quay trace, nói rõ smoke replay, không giả làm phiên tải live.

Hạ tầng AWS chưa bị xóa trong lúc chuẩn bị slide. Việc stop hoặc destroy cần thực hiện và kiểm tra riêng sau khi đã lưu video. Chỉ giữ máy chạy trong khoảng cần quay.
