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

Nội dung, số liệu, bìa, phân công, kiến trúc, công thức, kết luận và phụ lục
minh bạch AI đã được cập nhật. Phụ lục câu hỏi phản biện chưa được đưa vào PDF
vì nhóm chưa nhận câu hỏi chính thức. Mã lớp được bỏ trống thay vì suy đoán.

Trước khi nộp, nhóm chỉ cần điền mã lớp nếu giảng viên yêu cầu và kiểm tra lại
PDF cuối sau khi biên dịch trên máy nộp bài.
