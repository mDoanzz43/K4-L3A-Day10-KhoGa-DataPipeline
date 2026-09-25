# Báo cáo triển khai Data Pipeline và Data Observability

## 1. Tổng quan

Tài liệu này tổng hợp các phần đã triển khai cho pipeline thu thập và xử lý bài báo khoa học từ Crossref. Pipeline hoàn chỉnh thực hiện các bước:

1. Thu thập dữ liệu Crossref và hỗ trợ snapshot offline.
2. Làm sạch, chuẩn hóa và khử trùng lặp dữ liệu.
3. Kiểm định dữ liệu bằng Great Expectations 1.x và Freshness SLA.
4. Sinh bộ benchmark gồm 10 câu hỏi.
5. Tạo embedding bằng `all-MiniLM-L6-v2` và lưu vào ChromaDB.
6. Đánh giá baseline bằng Retrieval Hit Rate, Token F1 và LLM Judge.
7. Tiêm sáu loại lỗi dữ liệu để mô phỏng sự cố production.
8. Đo mức suy giảm của hệ thống RAG.
9. Khôi phục idempotent từ raw snapshot đáng tin cậy.
10. Sinh báo cáo so sánh Baseline, Corrupted và Repaired.

Luồng xử lý tổng quát:

```text
Crossref API / Offline Snapshot
              |
              v
       Raw Paper Records
              |
              v
     Cleaning & Normalization
              |
              v
 Great Expectations + Freshness
              |
              v
 MiniLM Embedding -> ChromaDB
              |
              v
     Benchmark Evaluation
              |
       +------+------+
       |             |
   Baseline      Corruption
                     |
                     v
              Trusted Raw Repair
                     |
                     v
                  Repaired
```

## 2. Thu thập dữ liệu Crossref

File triển khai: `src/ingestion/crossref.py`.

### Các trường được bóc tách

- `paper_id`: DOI được bỏ tiền tố URL hoặc `doi:` và chuyển về chữ thường.
- `title`: loại bỏ HTML/XML và chuẩn hóa khoảng trắng.
- `summary`: loại bỏ các thẻ HTML/JATS như `<jats:p>` và giải mã HTML entity.
- `authors`: ghép tên và họ của từng tác giả.
- `categories`: lấy danh sách lĩnh vực do Crossref cung cấp.
- `published`, `updated`: chuyển cấu trúc ngày của Crossref về chuỗi ISO 8601.
- Các URL và thông tin phụ như `abs_url`, `pdf_url`, `comment`.

### Cơ chế dual-mode

Pipeline ưu tiên gọi Crossref REST API. Nếu API trả về `429`, `503`, mất mạng hoặc response không hợp lệ, pipeline tự động đọc snapshot tại:

```text
data/raw/crossref_response.json
```

Cơ chế này giúp bài lab vẫn chạy được khi Crossref quá tải hoặc môi trường không có Internet. Một response online thành công được lưu lại làm snapshot mới; response lỗi không ghi đè snapshot đang hoạt động.

## 3. Làm sạch dữ liệu

File triển khai: `src/ingestion/cleaning.py`.

Hàm chính:

```python
build_clean_dataframe(records, run_date)
```

### Các quy tắc cleaning

- Xóa thẻ HTML/XML và chuẩn hóa khoảng trắng.
- Chuẩn hóa DOI thành khóa `paper_id` duy nhất.
- Loại record thiếu `paper_id`, `title` hoặc ngày xuất bản hợp lệ.
- Khử trùng lặp theo `paper_id`, giữ bản ghi xuất hiện đầu tiên.
- Chuẩn hóa `published` và `updated` về `YYYY-MM-DD`.
- Ghép tác giả thành `authors_joined`.
- Ghép lĩnh vực thành `categories_joined`.
- Tính độ dài summary trong `summary_chars`.
- Sắp xếp dữ liệu theo ngày xuất bản mới nhất.

### Tính tuổi dữ liệu

Tuổi dữ liệu được tính theo ngày UTC:

```python
age_days = (run_date - published).days
```

### Chuẩn bị văn bản embedding

Mỗi bài báo được chuyển thành một context thống nhất:

```text
Title: <tiêu đề>
Authors: <danh sách tác giả>
Published: <ngày xuất bản>
Categories: <lĩnh vực>
Summary: <tóm tắt>
```

Context này được lưu trong `text_for_embedding` để mô hình embedding nhận đủ thông tin của tài liệu.

Kết quả hiện tại: **24 bản ghi sạch**, không có DOI trùng lặp.

## 4. Data Quality Gate với Great Expectations 1.x

File triển khai: `src/observability/quality.py`.

Pipeline sử dụng API mới của Great Expectations 1.x:

```python
context = gx.get_context(mode="ephemeral")
data_source = context.data_sources.add_pandas(name="papers_source")
data_asset = data_source.add_dataframe_asset(name="papers_asset")
batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
```

`mode="ephemeral"` giữ cấu hình GX trong RAM và không tạo thư mục cấu hình tạm trong repository.

### Các expectation

| Expectation | Mục đích |
| --- | --- |
| `ExpectTableRowCountToBeBetween` | Số dòng phải từ 5 đến 5000 |
| `ExpectColumnValuesToNotBeNull` | `paper_id`, `title`, `text_for_embedding` không được null |
| `ExpectColumnValuesToBeUnique` | `paper_id` không được trùng |
| `ExpectColumnValueLengthsToBeBetween` | `summary` phải dài tối thiểu 30 ký tự |

Ba cột bắt buộc được kiểm tra not-null riêng, vì vậy validation suite có tổng cộng sáu phép kiểm tra thuộc bốn loại expectation.

### Freshness SLA

- Một bài báo bị xem là stale khi `age_days > 180`.
- Tính `stale_ratio = stale_rows / total_rows`.
- Nếu `stale_ratio > 25%`, kết quả là `is_fresh = false`.
- Đúng tại ngưỡng 25% vẫn được xem là đạt SLA.

Freshness report còn ghi ngày xuất bản mới nhất, cũ nhất, tổng số dòng và cảnh báo cập nhật dữ liệu.

## 5. Benchmark Test Set

File triển khai: `src/evaluation/testset.py`.

Pipeline sinh cố định 10 câu hỏi với phân bố:

| Nhóm câu hỏi | Số lượng |
| --- | ---: |
| `summary` | 3 |
| `authors` | 3 |
| `date` | 2 |
| `categories` | 2 |

Mỗi câu hỏi có cấu trúc:

```json
{
  "id": "eval_001",
  "question_type": "summary",
  "question": "What is the summary of the paper '<Title>'?",
  "ground_truth": "<Reference answer>",
  "ground_truth_doc_ids": ["<DOI>"]
}
```

Nếu Crossref không cung cấp category hoặc author, ground truth sử dụng câu trả lời rõ ràng như `No categories listed.` thay vì để chuỗi rỗng. Bộ test được lưu tại:

```text
data/eval/test_set.json
```

## 6. MiniLM Embedding và ChromaDB

Các file liên quan:

- `src/retrieval/embeddings.py`
- `src/retrieval/index.py`

Mô hình sử dụng:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Mỗi vector có **384 chiều** và được normalize trước khi lưu. ChromaDB sử dụng cosine distance.

Ba collection độc lập được dùng để tránh trộn trạng thái dữ liệu:

| Trạng thái | Collection |
| --- | --- |
| Baseline | `papers-baseline` |
| Corrupted | `papers-corrupted` |
| Repaired | `papers-repaired` |

Mỗi document lưu nội dung `text_for_embedding` và metadata gồm DOI, title, ngày xuất bản, tác giả, category, summary và URL.

Model loader ưu tiên cache cục bộ bằng `local_files_only=True`. Khi cache chưa có model, loader mới tải từ Hugging Face. Nhờ vậy những lần chạy sau hoạt động offline và không chờ các request kiểm tra mạng không cần thiết.

### 6.1. Multi-Provider QA Agent

Các file `src/retrieval/agent.py`, `src/retrieval/llm.py` và `src/retrieval/qa.py` tạo lớp QA trên ChromaDB. Router hỗ trợ `mock`, `google`/`gemini`, `openai`, `anthropic`, `openrouter`, `ollama` và endpoint OpenAI-compatible tùy chỉnh. Provider thật dùng LangChain Agent với hai tool: semantic search và exact paper lookup. System prompt bắt buộc Agent tra cứu corpus trước khi trả lời và phải nói rõ khi context không đủ bằng chứng.

Chế độ `mock` dùng adapter offline truy vấn cùng Chroma index và trích xuất câu trả lời trực tiếp từ metadata/context. Cách này giúp demo và chấm bài không cần API key, đồng thời vẫn kiểm thử được luồng Agent hoàn chỉnh thay vì trả về một chuỗi giả lập không liên quan dữ liệu.

## 7. Baseline Pipeline

File triển khai: `src/pipelines/phase1.py`.

Lệnh chạy:

```bash
python script/run_phase1.py
```

Thứ tự thực hiện:

1. Đọc raw records hoặc fetch Crossref nếu được yêu cầu.
2. Làm sạch và lưu JSON/CSV.
3. Chạy GX Quality Gate và Freshness SLA.
4. Dừng pipeline nếu Quality Gate thất bại.
5. Tạo hoặc tái sử dụng benchmark 10 câu hỏi.
6. Tạo collection `papers-baseline` và index 24 tài liệu.
7. Chạy đánh giá RAG.
8. Lưu metrics, câu trả lời và báo cáo Markdown.

### Baseline metrics thực tế

| Metric | Kết quả |
| --- | ---: |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 1.0000 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5.0000 |

Ragas mặc định không chạy để giữ thời gian lab ngắn. Có thể bật bằng biến môi trường `RUN_RAGAS=1`.

## 8. Synthetic Data Corruption

File triển khai: `src/ingestion/corruption.py`.

Sáu kịch bản được áp dụng theo cách deterministic:

| Kịch bản | Cách triển khai | Số dòng tác động hiện tại |
| --- | --- | ---: |
| `drop_latest_records` | Xóa 20% bài mới nhất | 5 |
| `blank_summary` | Thay summary bằng chuỗi rỗng | 3 |
| `inject_noise` | Chèn chuỗi noise lặp lại vào summary | 3 |
| `truncate_title` | Cắt title xuống dưới 8 ký tự | 5 |
| `stale_date` | Lùi ngày xuất bản 365 ngày | 7 |
| `duplicate_rows` | Sao chép nguyên dòng | 2 |

Sau khi sửa title, summary hoặc ngày, pipeline xây dựng lại `summary_chars` và `text_for_embedding` để lỗi thực sự đi vào vector index, thay vì chỉ tồn tại ở cột hiển thị.

Log ghi rõ thời gian, số dòng đầu vào/đầu ra, mô tả kịch bản, số dòng tác động và danh sách DOI tại:

```text
data/results/corruption_log.json
```

## 9. Đo lường suy giảm

Corrupted dataset được index vào collection riêng và đánh giá bằng đúng test set baseline. Việc giữ nguyên benchmark là cần thiết để so sánh công bằng.

Kết quả thực tế:

| Metric | Baseline | Corrupted | Mức giảm |
| --- | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.2546 | 0.7454 |
| `judge_accuracy` | 1.0000 | 0.2000 | 0.8000 |
| `mean_judge_score` | 5.0000 | 1.8000 | 3.2000 |

Các tín hiệu observability cũng đổi trạng thái:

- Quality Gate: `PASS` thành `FAIL` vì summary rỗng và DOI trùng.
- Freshness SLA: `PASS` thành `FAIL`.
- Tỷ lệ stale của corrupted dataset: **42.86%**.

Đây là bằng chứng cho hiện tượng silent failure: pipeline kỹ thuật vẫn có thể index và trả lời, nhưng chất lượng retrieval và câu trả lời giảm mạnh.

## 10. Idempotent Repair

File điều phối: `src/pipelines/corruption_flow.py`.

Lệnh chạy:

```bash
python script/run_corruption_flow.py
```

Repair không chỉnh sửa từng lỗi trên corrupted dataframe. Thay vào đó, pipeline:

1. Loại bỏ corrupted dataframe khỏi vai trò nguồn phục hồi.
2. Đọc lại `data/raw/crossref_records.json`.
3. Nếu file trên không có dữ liệu, fallback sang `data/raw/crossref_response.json`.
4. Chạy lại toàn bộ quy tắc cleaning.
5. Chạy lại Quality Gate và Freshness SLA.
6. Xây collection `papers-repaired` từ đầu.
7. Đánh giá bằng đúng benchmark baseline.

Cách rebuild từ nguồn raw đáng tin cậy giúp repair có tính idempotent: chạy nhiều lần vẫn tạo cùng tập 24 DOI duy nhất và collection active vẫn có đúng 24 document, không nhân bản dữ liệu.

### Kết quả ba trạng thái

| Metric/Signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.2546 | 1.0000 |
| `judge_accuracy` | 1.0000 | 0.2000 | 1.0000 |
| `mean_judge_score` | 5.0000 | 1.8000 | 5.0000 |
| Quality Gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |
| Số dòng | 24 | 21 | 24 |

Repair đã được chạy hai lần liên tiếp và xác minh:

```text
idempotent_rebuild: PASS
repaired_rows: 24
repaired_unique_ids: True
repaired_collection_documents: 24
metrics_match_baseline: PASS
```

## 11. Báo cáo tự động

File triển khai: `src/observability/reporting.py`.

Hai báo cáo được tạo tự động từ kết quả pipeline thực tế:

- `data/reports/phase1_report.md`: nguồn dữ liệu, cấu hình index, baseline metrics, GX và Freshness.
- `data/reports/corruption_report.md`: bảng Baseline–Corrupted–Repaired, delta metric, observability signal, phương pháp repair và kết luận.

## 12. Artifact đã sinh

```text
data/
├── clean/
│   ├── papers_clean.csv
│   ├── papers_clean.json
│   ├── papers_clean_corrupted.csv
│   ├── papers_clean_corrupted.json
│   ├── papers_clean_repaired.csv
│   └── papers_clean_repaired.json
├── chroma/
├── embeddings/
│   ├── papers_embeddings.json
│   ├── papers_embeddings_corrupted.json
│   └── papers_embeddings_repaired.json
├── eval/
│   └── test_set.json
├── quality/
│   ├── baseline_quality_report.json
│   ├── corrupted_quality_report.json
│   ├── repaired_quality_report.json
│   ├── freshness_report.json
│   ├── corrupted_freshness_report.json
│   └── repaired_freshness_report.json
├── reports/
│   ├── phase1_report.md
│   └── corruption_report.md
└── results/
    ├── baseline_metrics.json
    ├── baseline_answers.json
    ├── corruption_log.json
    ├── corrupted_metrics.json
    ├── corrupted_answers.json
    ├── repaired_metrics.json
    └── repaired_answers.json
```

## 13. Các lệnh kiểm tra chính

### Kiểm tra cleaning

```bash
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Clean thành công {len(df)} dòng')"
```

### Kiểm tra Quality Gate

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); result=run_data_quality_checks(df, s, 'test'); print(result['success'])"
```

### Chạy baseline

```bash
python script/run_phase1.py
```

### Chạy corruption và repair

```bash
python script/run_corruption_flow.py
```

## 14. Kết luận

Pipeline hiện đáp ứng đầy đủ các mục tiêu chính của bài lab:

- Có thể thu thập dữ liệu online hoặc tiếp tục chạy từ snapshot offline.
- Dữ liệu được làm sạch, chuẩn hóa và khử trùng lặp.
- Dữ liệu lỗi bị phát hiện bởi GX Quality Gate và Freshness SLA.
- Vector index được cô lập theo ba trạng thái để so sánh công bằng.
- Corruption tạo ra suy giảm định lượng rõ rệt.
- Repair từ raw snapshot khôi phục hoàn toàn dữ liệu và metric.
- Việc chạy lại repair không tạo duplicate trong dataset hoặc active collection.
- Các kết quả đều được lưu thành JSON, CSV và Markdown để kiểm tra hoặc nộp bài.
