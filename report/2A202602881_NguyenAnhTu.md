# Báo cáo vai trò cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Anh Tú |
| MSSV | 2A202602881 |
| Khóa/Lớp | K4 |
| Tên nhóm | KhoGa |
| Vai trò chính | Data Ingestion, Cleaning & Data Observability — Checkpoint 0 và 1 |
| Repository | `K4-L3A-Day10-KhoGa-DataPipeline` |
| Phạm vi báo cáo | Checkpoint 0 và Checkpoint 1 |
| Ngày xác nhận | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

Tôi phụ trách phần tạo nền dữ liệu cho các checkpoint sau: đọc/parse dữ liệu Crossref, duy trì raw lineage, làm sạch dữ liệu để tạo schema dùng chung và dựng chốt kiểm soát chất lượng bằng Great Expectations 1.x. Phần việc của tôi dừng ở CP0–CP1; tôi không nhận ownership cho embedding/index, evaluation, corruption, repair hay orchestration end-to-end.

| Checkpoint | Module/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| CP0 — Raw ingestion | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref payload hoặc snapshot local | Danh sách `PaperRecord`; `data/raw/crossref_response.json`; `data/raw/crossref_records.json` | Hoàn thành |
| CP1 — Cleaning | `src/ingestion/cleaning.py`: `build_clean_dataframe` | `list[PaperRecord]`, thời điểm chạy UTC | DataFrame 24 dòng; `papers_clean.csv`; `papers_clean.json` | Hoàn thành |
| CP1 — Quality/freshness | `src/observability/quality.py`: `run_data_quality_checks`, `build_freshness_report` | Clean DataFrame, `Settings` | GX validation và freshness reports trong `data/quality/` | Hoàn thành |

## 3. Kết quả và bằng chứng

### 3.1. Checkpoint 0 — Ingestion và raw lineage

Pipeline hỗ trợ hai chế độ. Ở chế độ mặc định cho lab, nó đọc snapshot local để kết quả ổn định khi không có mạng. Khi `REFRESH_SOURCE=true`, module gọi Crossref REST API; nếu request lỗi, bao gồm rate limit hoặc lỗi mạng, module quay về snapshot thay vì làm gián đoạn pipeline. Payload gốc được giữ tại `data/raw/crossref_response.json`; danh sách đã parse được ghi tại `data/raw/crossref_records.json`.

Các trường được chuẩn hóa khi parse gồm DOI (`paper_id`), title, summary, authors, categories, `published` và `updated`. Summary được bỏ markup HTML/JATS bằng regex trước khi chuẩn hóa khoảng trắng. Record thiếu DOI, title, summary hoặc ngày xuất bản hợp lệ không được đưa vào output.

| Artifact | Bằng chứng hiện có |
| --- | --- |
| `data/raw/crossref_response.json` | 24 items trong `message.items`; là snapshot raw dùng cho offline mode |
| `data/raw/crossref_records.json` | 24 đối tượng `PaperRecord` đã parse |
| Smoke test ingestion | `ingestion_count=24` |

Lệnh xác minh đã dùng:

```powershell
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print('ingestion_count={}'.format(len(r)))"
```

Kết quả thực tế:

```text
ingestion_count=24
```

### 3.2. Checkpoint 1 — Cleaning và data contract

Hàm `build_clean_dataframe` chuẩn hóa DOI, title, summary, authors và categories; loại bản ghi thiếu trường thiết yếu; parse ngày xuất bản theo UTC; khử trùng lặp bằng `paper_id`; sau đó sắp xếp dữ liệu theo `paper_id`. `age_days` được tính theo công thức `(run_date - published).days`.

Schema clean có các cột chính: `paper_id`, `title`, `summary`, `authors`, `categories`, `published`, `updated`, `authors_joined`, `categories_joined`, `summary_chars`, `age_days` và `text_for_embedding`.

`text_for_embedding` được tạo thống nhất theo năm phần:

```text
Title: <title>
Authors: <authors_joined>
Published: <published>
Categories: <categories_joined>
Summary: <summary>
```

| Artifact | Kết quả thực tế |
| --- | --- |
| `data/clean/papers_clean.csv` | 24 dòng dữ liệu đã clean, tiện kiểm tra bằng bảng tính |
| `data/clean/papers_clean.json` | 24 record cho các module Python đọc lại |
| Kiểm tra uniqueness | `paper_id.is_unique=True` |
| Kiểm tra embedding text | `text_for_embedding` không null cho toàn bộ 24 dòng |

Lệnh xác minh đã dùng:

```powershell
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print('clean_count={} unique={} embedding_complete={}'.format(len(df), df.paper_id.is_unique, df.text_for_embedding.notna().all()))"
```

Kết quả thực tế:

```text
clean_count=24 unique=True embedding_complete=True
```

### 3.3. Checkpoint 1 — Quality Gate và Freshness SLA

Module quality dùng API Great Expectations 1.x với ephemeral context trên RAM, không dùng API cũ `context.sources.pandas_default`. Sáu validation cụ thể thuộc bốn loại expectation:

1. Số dòng từ 5 đến 5000.
2. `paper_id`, `title`, `text_for_embedding` đều không null.
3. `paper_id` là duy nhất.
4. `summary` có độ dài tối thiểu 30 ký tự.

Freshness được đo độc lập: record có `age_days > 180` được xem là stale; dataset chỉ bị gắn cờ không fresh khi stale ratio vượt 25%.

| Artifact | Kết quả thực tế |
| --- | --- |
| `data/quality/cp1_verify_quality_report.json` | 6/6 validation thành công; `success=true` |
| `data/quality/cp1_verify_freshness_report.json` | 1/24 record stale, tỷ lệ `0.0416667`; `is_fresh=true` |
| `data/quality/freshness_report.json` | Báo cáo freshness canonical hiện hành |

Lệnh xác minh đã dùng:

```powershell
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); res=run_data_quality_checks(pd.read_json(s.paths.clean_json), s, 'cp1_verify'); print('quality_success={} is_fresh={}'.format(res['success'], res['freshness']['is_fresh']))"
```

Kết quả thực tế:

```text
quality_success=True is_fresh=True
```

## 4. Quyết định kỹ thuật và lý do

### Snapshot offline là chế độ mặc định

**Bối cảnh:** Crossref là nguồn bên ngoài và có thể mất kết nối hoặc giới hạn request. Nếu pipeline phụ thuộc tuyệt đối vào API live thì lab không tái hiện ổn định.

**Quyết định:** Dùng `data/raw/crossref_response.json` làm snapshot mặc định; chỉ thử API live khi bật `REFRESH_SOURCE=true`; nếu request thất bại thì dùng lại snapshot.

**Lý do:** Cách này đảm bảo 24 record đầu vào, giúp các checkpoint tiếp theo có cùng data contract và cho phép CP5 repair từ nguồn raw đáng tin cậy.

### Tách quality checks khỏi freshness signal

**Quyết định:** `success` phản ánh các expectation cấu trúc/nội dung của GX; `is_fresh` là SLA được báo cáo riêng.

**Lý do:** Một dataset có thể đúng schema nhưng cần được cập nhật. Tách hai tín hiệu giúp đội vận hành nhận biết đúng loại vấn đề, thay vì gộp dữ liệu stale với lỗi null, duplicate hoặc summary quá ngắn.

## 5. Lỗi/blocker đã xử lý

| Triệu chứng | Nguyên nhân | Cách xử lý | Xác minh |
| --- | --- | --- | --- |
| `ModuleNotFoundError: No module named 'core'` | Project dùng cấu trúc `src/` nhưng môi trường chưa cài package editable | Kích hoạt `.venv` Python 3.11 và chạy `python -m pip install -e .` | Import `core`, `ingestion`, `observability` và ba smoke test CP0/CP1 chạy được |
| `SyntaxError: f-string expression part cannot include a backslash` | Lệnh PowerShell bị copy kèm escape `\"` trong f-string | Dùng `str.format()` với dấu nháy đơn bên trong lệnh `python -c` | Quality check trả `quality_success=True` |

## 6. Giới hạn hiện tại và bước tiếp theo

- Phạm vi cá nhân mới xác minh CP0 và CP1; baseline orchestration, evaluation, corruption và repair thuộc checkpoint sau/owner khác.
- Live API hiện có cơ chế fallback ngay khi request thất bại. Chưa có retry/backoff nhiều lần riêng cho `429`/`503`; đây là cải tiến nên bổ sung nếu cần chạy API live thường xuyên.
- Artifact quality có nhiều report theo tên lần chạy (`test`, `cp1_verify`). Khi nộp, nên giữ `freshness_report.json` cùng một cặp report xác minh để repository gọn hơn.

## 7. Hiểu biết về luồng end-to-end

1. Payload Crossref được bảo toàn dưới dạng raw artifact rồi parse thành `PaperRecord` để tạo ranh giới rõ ràng giữa dữ liệu nguồn và dữ liệu đã xử lý.
2. Cleaning tạo data contract thống nhất cho embedding, retrieval và evaluation: DOI giữ vai trò document identity, còn `text_for_embedding` là nội dung vector hóa.
3. Quality Gate cần chạy trước index để chặn null, duplicate và summary quá ngắn. Freshness SLA bổ sung góc nhìn thời gian mà các validation schema không phát hiện được.
4. Các checkpoint sau phải dùng output clean này để xây index, tạo benchmark, đo metric và so sánh corruption/repaired trên cùng test set.
5. Repair đáng tin cậy phải đọc lại raw snapshot và chạy lại cleaning/quality, không sửa từng lỗi trực tiếp trên corrupted dataframe.

## 8. Cam kết của thành viên

- [x] Báo cáo chỉ phản ánh Checkpoint 0 và 1 tôi phụ trách.
- [x] Các kết quả 24 records, 24 clean rows, GX `success=true` và Freshness `is_fresh=true` đều có artifact hoặc log để đối chiếu.
- [x] Tôi không nhận ownership cho các checkpoint và metric chưa nằm trong phạm vi báo cáo này.
- [x] Báo cáo không chứa API key, token, nội dung `.env` hoặc secret.
- [x] Tôi có thể giải thích luồng từ raw data đến quality/freshness gate và vai trò của nó trong pipeline RAG.

**Họ và tên:** Nguyễn Anh Tú  
**MSSV:** 2A202602881  
**Ngày xác nhận:** 2026-09-25
