# NT531 LaTeX Report

Báo cáo: **Performance Evaluation of AWS VPC Peering and Transit Gateway**.

## Nguồn dữ liệu

- Nội dung và số liệu phải truy được về `../docs/`, `../results/`,
  `../scripts/` hoặc `../infra/terraform/`.
- Không dùng `../legacy/` làm kết quả thực nghiệm.
- Mapping chi tiết nằm trong `REPORT-SOURCE-MAP.md`.

## Build

Với TeX Live có `latexmk` và BibTeX:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Hoặc dùng Docker từ thư mục gốc repository trên PowerShell:

```powershell
docker run --rm -v "${PWD}\report:/work" -w /work `
  texlive/texlive:latest `
  latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

File đầu ra: `main.pdf`.

## Trạng thái nộp bài

PDF hiện build được và nội dung thực nghiệm đã được đối chiếu, nhưng
**chưa sẵn sàng để nộp**. Repository chưa có nguồn đáng tin cậy cho:

- mã lớp, giảng viên, họ tên và MSSV trên trang bìa;
- thành viên, phân công và tỷ lệ đóng góp tại Phụ lục A;
- câu hỏi phản biện và giải trình chính thức tại Phụ lục B.

Source giữ comment đánh dấu các trường chờ người dùng cung cấp; PDF hiển thị
`CHƯA CUNG CẤP` và đánh dấu rõ là bản chưa hoàn thiện. Không thay placeholder
bằng dữ liệu suy đoán.

TeX Live 2026 vẫn phát cảnh báo tổng quát yêu cầu chạy lại BibTeX dù đã chạy
đủ chu kỳ với `backend=bibtex`. Audit PDF và source không phát hiện citation,
label hoặc reference thiếu; giữ backend theo `uit-report.sty`.
