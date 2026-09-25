# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4-L3 |
| Tên nhóm | KhoGa (Khô Gà) |
| Repository | `https://github.com/mDoanzz43/K4-L3A-Day10-KhoGa-DataPipeline` |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Anh Tú | 2A202602881 | Data Foundation Owner | CP0–CP1: môi trường, ingestion, cleaning, data quality và freshness |
| 2 | Lê Thị Hoài Thương | 2A202602898 | Evaluation & Vector Index Owner | CP2: `testset.py`, embeddings và ChromaDB baseline index |
| 3 | Nguyễn Mạnh Cường | 2A202602823 | Baseline & Corruption Owner | CP3–CP4: baseline pipeline, corruption flow và metrics |
| 4 | Đỗ Mạnh Đoan | 2A202602839 | Final Verification, Demo & Reporting | Chạy lại pipeline, đối chiếu kết quả, Streamlit và reports |


## 2. Tóm tắt kết quả

Nhóm đã hoàn thành pipeline end-to-end cho dữ liệu bài báo Crossref, gồm lưu raw artifacts, cleaning, Great Expectations 1.x, Freshness SLA, MiniLM embedding, ChromaDB indexing và đánh giá RAG. Baseline có 24 tài liệu sạch, 10 câu hỏi benchmark và đạt retrieval hit rate 1.0, mean token F1 0.9044. Sáu corruption scenarios làm dataset còn 21 dòng, khiến Quality Gate và Freshness SLA cùng FAIL; retrieval hit rate giảm còn 0.6 và mean token F1 còn 0.8832. Repair đọc lại trusted raw records, chạy cleaning, validation, indexing và evaluation bằng cùng test set. Trạng thái repaired trở lại 24 tài liệu, Quality/Freshness PASS và toàn bộ metrics trở về đúng baseline. Nhóm cũng xây dựng dashboard Streamlit để trực quan hóa workflow, xem artifacts và chạy live CP3–CP5. Giới hạn hiện tại là Ragas mặc định chưa bật và lần nghiệm thu sử dụng mock provider để không phụ thuộc API key.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API / offline snapshot
    -> raw response và raw records
    -> cleaning và data modeling
    -> Great Expectations + Freshness SLA
    -> MiniLM embedding + ChromaDB index
    -> evaluation baseline
    -> six controlled corruptions
    -> quality/freshness alerts + corrupted evaluation
    -> repair từ trusted raw
    -> re-index và re-evaluate
    -> comparison report + Streamlit dashboard
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref response hoặc offline snapshot | Fetch/fallback, parse và lưu raw | `data/raw/crossref_response.json`, `crossref_records.json` | Thành viên CP0–CP1 |
| Cleaning | Raw paper records | Normalize, deduplicate, tính `age_days`, tạo embedding text | `data/clean/papers_clean.csv/json` | Thành viên CP0–CP1 |
| Embedding/index | Clean dataframe | MiniLM embedding và ChromaDB indexing | `data/embeddings/`, `data/chroma/` | Lê Thị Hoài Thương |
| Evaluation | Fixed test set và Chroma index | Retrieval, QA, Token F1 và Judge | `data/results/*metrics.json`, `*answers.json` | Thành viên CP3–CP4 |
| Observability | Clean/corrupted/repaired dataframe | GX expectations và Freshness SLA | `data/quality/` | Thành viên CP0–CP1, hỗ trợ bởi nhóm |
| Corruption/repair | Baseline dataframe và trusted raw | Inject 6 lỗi, rebuild từ raw và đánh giá lại | Corrupted/repaired datasets và metrics | Thành viên CP3–CP4, Đỗ Mạnh Đoàn kiểm chứng |
| Orchestration/reporting | Toàn bộ artifacts | Chạy end-to-end, so sánh và trực quan hóa | Markdown reports và Streamlit dashboard | Đỗ Mạnh Đoàn |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `mock` |
| `LLM_MODEL` | Không gọi model ngoài trong lần nghiệm thu |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; tối đa 25% stale records |
| Random seed, nếu có | Corruption chọn record theo logic xác định trong module |

Không đưa API key hoặc nội dung file `.env` vào báo cáo.

### Lệnh cài đặt

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### Lệnh chạy

Baseline:

```powershell
$env:LLM_PROVIDER="mock"
$env:REFRESH_SOURCE="false"
$env:REFRESH_TEST_SET="false"
.\.venv\Scripts\python.exe script\run_phase1.py
```

Corruption flow:

```powershell
$env:LLM_PROVIDER="mock"
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

Dashboard:

```powershell
$env:LLM_PROVIDER="mock"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công, exit code 0 | 2026-09-25 | `baseline_metrics.json`, `phase1_report.md` |
| Corruption flow | Thành công, exit code 0 | 2026-09-25 | `corruption_log.json`, corrupted/repaired metrics và comparison report |
| Streamlit dashboard | Thành công, HTTP 200 | 2026-09-25 | AppTest 7/7 màn hình có 0 exception |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API / offline snapshot |
| Query/filter | Agentic retrieval augmented generation và large language model; có abstract |
| Thời điểm lấy dữ liệu | Theo timestamp trong raw response artifact |
| Số record nhận được | 24 |
| Cơ chế retry/backoff | Request có timeout; khi API lỗi/rate limit thì dùng snapshot cục bộ |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | DOI/document identity ổn định | Loại record nếu rỗng; deduplicate |
| `title` | string | Có | Tiêu đề bài báo | Normalize whitespace; loại nếu rỗng |
| `summary` | string | Có | Abstract/tóm tắt | Xóa markup; loại nếu rỗng; GX yêu cầu ≥30 ký tự |
| `authors` | list[string] | Không | Danh sách tác giả | Normalize từng giá trị và tạo `authors_joined` |
| `categories` | list[string] | Không | Lĩnh vực bài báo | Normalize và tạo `categories_joined` |
| `published` | date/string | Có | Ngày xuất bản | Parse UTC; loại record nếu không hợp lệ |
| `age_days` | integer | Có ở clean schema | Tuổi dữ liệu tại thời điểm chạy | Tính từ run date và published date |
| `text_for_embedding` | string | Có ở clean schema | Nội dung đưa vào MiniLM | Ghép năm phần theo data contract |

### Quy tắc cleaning

| Quy tắc | Quality dimension liên quan | Số record bị tác động | Cách xác minh |
| --- | --- | ---: | --- |
| Xóa JATS/XML tags và normalize whitespace | Validity | Theo dữ liệu raw | So sánh raw summary với clean summary |
| Loại record thiếu ID/title/summary/date | Completeness | 0 trong lần chạy cuối | Raw và clean đều 24 records |
| Deduplicate theo `paper_id` | Uniqueness | 0 trong baseline | 24 unique IDs trên 24 dòng |
| Tính `age_days` | Freshness | 24 | Kiểm tra clean schema và freshness report |
| Tạo `text_for_embedding` | Completeness/Consistency | 24 | GX not-null và Data Explorer |

`text_for_embedding` gồm Title, Authors, Published, Categories và Summary. Document ID dùng `paper_id` và được giữ ổn định trong test set, metadata và kết quả retrieval.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| Các `question_type` | `summary`, `authors`, `date`, `category`, `multi_hop` |
| Ground-truth document ID | DOI trong `ground_truth_doc_ids` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection | ChromaDB: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | `mock`; heuristic fallback cho Judge khi không gọi LLM ngoài |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

Test set được giữ nguyên để chỉ có dữ liệu/index thay đổi giữa ba lần đánh giá. Nếu thay câu hỏi hoặc ground truth, chênh lệch metrics có thể do đề đánh giá thay đổi thay vì do corruption hoặc repair.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | 24 records |
| Cleaned dataset | `data/clean/papers_clean.csv/json` | Có | 24 clean rows |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | `papers-baseline`: 24 docs |
| Evaluation set | `data/eval/test_set.json` | Có | 10 questions |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | Sinh từ pipeline thực tế |
| Quality/freshness | `data/quality/` | Có | Baseline PASS |
| Baseline report | `data/reports/phase1_report.md` | Có | Báo cáo tự động |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | Tất cả câu hỏi retrieve được ít nhất một ground-truth document |
| `mean_token_f1` | 0.9044 | Câu trả lời có mức token overlap cao với ground truth |
| `judge_accuracy` | 0.9000 | 9/10 câu được judge xác định materially correct |
| `mean_judge_score` | 4.4000 | Điểm trung bình cao trên thang 1–5 |
| Ragas, nếu có | N/A | Mặc định skip; bật bằng `RUN_RAGAS=1` khi có cấu hình phù hợp |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| Row count | Volume | 5–5000 | PASS, 24 rows | `baseline_quality_report.json` |
| Required values | Completeness | `paper_id`, `title`, `text_for_embedding` không null | PASS | GX results |
| Unique ID | Uniqueness | `paper_id` unique | PASS | GX results |
| Summary length | Validity | Tối thiểu 30 ký tự | PASS | GX results |

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | Cleaned dataset qua `age_days` |
| Timestamp mới nhất | 2026-07-22 |
| Ngưỡng freshness | Stale khi `age_days > 180`; fail nếu stale ratio >25% |
| Trạng thái baseline | Fresh/PASS |
| Lý do | 1/24 stale records, stale ratio khoảng 4.17%, thấp hơn ngưỡng 25% |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | ---: | --- | --- | --- |
| Drop latest records | Loại 20% records mới nhất | 5 | Row count/coverage thay đổi | Retrieval Hit Rate giảm | Rebuild từ raw |
| Blank summary | Đặt summary thành chuỗi rỗng | 3 | Summary length FAIL | Thiếu answer-bearing context | Rebuild từ raw |
| Inject noise | Thêm synthetic noise vào summary | 3 | Semantic quality suy giảm | Embedding/retrieval bị ảnh hưởng | Rebuild từ raw |
| Truncate title | Cắt title xuống dưới 8 ký tự | 5 | Title validity suy giảm | Exact lookup và embedding yếu hơn | Rebuild từ raw |
| Stale date | Lùi published date 365 ngày | 7 | Freshness FAIL | Stale ratio vượt 25% | Rebuild từ raw |
| Duplicate rows | Append bản sao record | 2 | Unique ID FAIL | Dữ liệu bị over-represent | Rebuild từ raw và recreate collection |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đủ sáu scenario, số record bị tác động và danh sách `paper_id`.

Repair không sửa trực tiếp corrupted dataframe. Pipeline đọc lại `data/raw/crossref_records.json`, chạy cleaning, validation, embedding, indexing và evaluation từ đầu. Hai lần chạy liên tiếp tạo cùng SHA-256 cho repaired dataset và repaired metrics, xác nhận tính idempotent.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | -0.4000 | 100% | Retrieval phục hồi đúng baseline |
| `mean_token_f1` | 0.9044 | 0.8832 | 0.9044 | -0.0212 | 100% | Answer overlap phục hồi đúng baseline |
| `judge_accuracy` | 0.9000 | 0.9000 | 0.9000 | 0.0000 | Không suy giảm | Binary judge chưa nhạy với mọi lỗi retrieval |
| `mean_judge_score` | 4.4000 | 4.2000 | 4.4000 | -0.2000 | 100% | Judge score phục hồi |
| Quality checks pass/fail | PASS | FAIL | PASS | Chuyển sang FAIL | Full | Phát hiện completeness và uniqueness violations |
| Freshness status | PASS | FAIL | PASS | Chuyển sang FAIL | Full | Phát hiện stale ratio vượt SLA |

Hai kết luận nhân quả có artifact hỗ trợ:

1. Sáu corruptions làm mất/rỗng/nhiễu/cũ/trùng dữ liệu → Quality Gate và Freshness cùng FAIL → retrieval Hit Rate giảm 1.0 xuống 0.6, F1 giảm còn 0.8832 và mean judge score giảm còn 4.2.
2. Repair rebuild từ trusted raw → Quality/Freshness trở lại PASS → Hit Rate, F1 và judge score trở lại đúng baseline.

`judge_accuracy` không giảm dù Hit Rate giảm. Kiểm tra `corrupted_answers.json` cho thấy một số câu vẫn có thể nhận câu trả lời đạt ngưỡng của heuristic judge. Vì vậy nhóm không kết luận chỉ từ accuracy mà đối chiếu thêm Hit Rate, Token F1, mean judge score và quality signals.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Pipeline không chạy được trên môi trường Python 3.10 và bước embedding thiếu model local.
- **Nguyên nhân:** Source sử dụng `datetime.UTC`, yêu cầu Python 3.11+; MiniLM chưa được tải vào cache.
- **Cách xử lý:** Cài Python 3.11.9, tạo `.venv`, cài dependencies và tải `all-MiniLM-L6-v2` một lần.
- **Cách xác minh:** Smoke test imports PASS; hai entrypoint exit code 0; ChromaDB có ba collection 24/21/24 documents.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Lần nghiệm thu dùng mock provider | Không phản ánh đầy đủ chất lượng LLM thương mại | Chạy lại với provider thật và so sánh metrics/cost/latency |
| Ragas mặc định bị skip | Thiếu faithfulness/context metrics nâng cao | Bật `RUN_RAGAS=1`, lưu kết quả và kiểm tra report |
| Chưa có CI tự động | Verification còn phụ thuộc thao tác thủ công | Thêm pytest + GitHub Actions với coverage >80% |
| Dashboard hiển thị snapshot hiện tại | Chưa theo dõi drift qua thời gian | Lưu run history và biểu diễn time-series metrics |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [X] Hoàn thiện họ tên/MSSV còn trống trong bảng thành viên.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [X] Mỗi thành viên hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source.

