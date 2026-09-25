# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đỗ Mạnh Đoan |
| MSSV | 2A202602839 |
| Khóa/Lớp | K4-L3 |
| Tên nhóm | Khô Gà |
| Vai trò chính | Integration, final verification, demo và reporting |
| Repository | `https://github.com/mDoanzz43/K4-L3A-Day10-KhoGa-DataPipeline` |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

Phân công ban đầu của nhóm là: Tú phụ trách CP0–CP1, Thương phụ trách CP2, Cường phụ trách CP3–CP4; tôi phụ trách phần tích hợp và nghiệm thu cuối: gồm chạy lại pipeline từ dữ liệu gốc, so sánh kết quả, kiểm tra lại từng checkpoint, chuẩn bị demo và hoàn thiện báo cáo.

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Final integration và rerun | `script/run_phase1.py`, `script/run_corruption_flow.py` | Raw data và test set CP2 từ `origin/thuong` | Bộ artifacts Baseline/Corrupted/Repaired mới | Hoàn thành |
| Verification và impact analysis | `data/results/`, `data/quality/`, `data/chroma/` | Metrics, quality reports và ChromaDB | Bảng so sánh ba trạng thái, bằng chứng idempotence | Hoàn thành |
| Dashboard demo | `streamlit_app.py`, `.streamlit/config.toml` | Toàn bộ artifacts của pipeline | Dashboard workflow có visualization và live execution | Hoàn thành |
| Báo cáo nhóm | `report/group_report.md` | Kết quả chạy thật và artifact paths | Báo cáo nhóm khớp với data CP2 gốc | Hoàn thành |
| Báo cáo cá nhân | `report/Do_Manh_Doan_2A202602839_Report.md` | Phạm vi công việc và bằng chứng cá nhân | Báo cáo vai trò cá nhân | Hoàn thành |

Tôi không nhận ownership đối với implementation CP0–CP4 do các thành viên khác trực tiếp thực hiện. Phần tôi sở hữu là tích hợp, tái hiện, kiểm tra chéo, demo và reporting cuối.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra CP0–CP1 | Ingestion, cleaning và observability | Xác nhận 24 raw/clean records, schema hợp lệ, GX và Freshness PASS |
| Kiểm tra CP2 | Test set, embeddings và ChromaDB | Xác nhận 10 câu hỏi, 24 documents và nguồn dữ liệu |
| Kiểm tra CP3–CP5 | Pipeline orchestration | Chạy lại hai entrypoint với exit code 0 và đối chiếu artifacts |
| Dọn dữ liệu tích hợp | ChromaDB | Loại bỏ vector directories mồ côi, giữ đúng ba collection đang được SQLite tham chiếu |
| Chuẩn bị live demo | Toàn nhóm | Dashboard Streamlit gồm bảy khu vực, font/theme tối ưu cho trình chiếu |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Khôi phục nguồn CP2 gốc | `data/raw/`, `data/eval/test_set.json` | Raw response, raw records và test set khớp `origin/thuong` | So sánh Git blob hash |
| Chạy lại baseline | `script/run_phase1.py` | 24 documents; Hit Rate 1.0; F1 0.9044 | Exit code 0 và `baseline_metrics.json` |
| Chạy corruption và repair | `script/run_corruption_flow.py` | 21 corrupted và 24 repaired documents | Exit code 0 và comparison report |
| Kiểm tra idempotence | `papers_clean_repaired.json`, `repaired_metrics.json` | Hash giữ nguyên sau hai lần chạy | `Get-FileHash` trước và sau rerun |
| Dựng dashboard | `streamlit_app.py` | Bảy màn hình, chạy pipeline và hiển thị live log | AppTest 0 exception, HTTP 200 |
| Cập nhật báo cáo nhóm | `report/group_report.md` | Báo cáo dùng đúng metrics mới | Đối chiếu với `data/results/` và `data/quality/` |

Raw response, raw records và evaluation set đã được đối chiếu hash; baseline, corrupted và repaired sau đó được chạy lại trên cùng test set. Đã có streamlit để demo workflow bài lab.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Sau khi các thành viên hoàn thành checkpoint được phân công, nhóm cần một bước nghiệm thu cuối để chắc chắn các file có thể hoạt động cùng nhau, artifacts khớp với code và báo cáo phản ánh đúng kết quả thực tế. Phần việc của tôi tập trung vào ba yêu cầu:

1. Đối chiếu các file và chạy lại CP0–CP4 do các thành viên bàn giao.
2. Chạy `run_corruption_flow.py` trên dataset đã hoàn thiện để lấy số liệu Baseline/Corrupted/Repaired và viết báo cáo.
3. Xây dựng giao diện Streamlit để trực quan hóa và demo toàn bộ workflow.

### Cách triển khai

Trước tiên, tôi đọc lại tài liệu `CHECKPOINTS.md`, `Guide.md`, `RUBRIC.md` và đối chiếu lần lượt source code, artifact và pass signal của từng checkpoint:

- CP0: kiểm tra Python, dependencies, raw response, raw records và số lượng bản ghi.
- CP1: kiểm tra clean schema, `paper_id`, `title`, `summary`, `age_days`, `text_for_embedding`, GX và freshness.
- CP2: kiểm tra test set 10 câu, embedding manifest và ChromaDB collection.
- CP3: chạy baseline end-to-end, kiểm tra metrics và `phase1_report.md`.
- CP4: kiểm tra đủ sáu corruption scenarios, quality alerts và mức suy giảm metrics.

Sau đó, tôi chạy `run_corruption_flow.py`. Script lấy clean dataset và fixed evaluation set, tạo corrupted dataset, chạy lại Quality/Freshness, index collection corrupted và tính metrics. Tiếp theo script đọc lại trusted raw records, tái tạo repaired dataset, validate, index và đánh giá lại. Kết quả ba trạng thái được ghi vào JSON và Markdown report để sử dụng trong báo cáo nhóm.

Tôi chạy corruption/repair hai lần liên tiếp và so sánh hash của repaired dataset cùng repaired metrics. Hash không thay đổi, chứng minh repair có tính idempotent và không tích lũy duplicate qua nhiều lần chạy.

Cuối cùng, tôi xây dựng dashboard Streamlit đọc trực tiếp các artifact thực tế. Dashboard có các màn hình Overview, Data Explorer, Quality & Freshness, RAG Evaluation, Corruption & Repair, Control Center và Artifact Registry. Control Center cho phép chạy trực tiếp pipeline và xem live log; giao diện không hiển thị API key hoặc nội dung `.env`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `crossref_response.json`, `crossref_records.json`, clean dataset và fixed `test_set.json` do các checkpoint trước bàn giao |
| Output | Clean/corrupted/repaired datasets, ba Chroma collections, quality reports, metrics, answers và Markdown reports |
| Module phụ thuộc | `ingestion`, `evaluation`, `retrieval`, `observability`, `pipelines` |
| Module sử dụng output | Streamlit dashboard, group report và live demo |
| Điều kiện lỗi cần xử lý | Thiếu artifact đầu vào, model chưa cache, dependency/Python không tương thích, quality gate thất bại và Chroma directories mồ côi |

### Cách xác minh

```powershell
$env:LLM_PROVIDER="mock"
$env:REFRESH_SOURCE="false"
$env:REFRESH_TEST_SET="false"
.\.venv\Scripts\python.exe script\run_phase1.py
.\.venv\Scripts\python.exe script\run_corruption_flow.py
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

- **Kết quả mong đợi:** Hai pipeline exit code 0; Quality/Freshness PASS → FAIL → PASS; repaired metrics trở lại baseline; dashboard hoạt động.
- **Kết quả thực tế:** CP3 và CP4–CP5 đều exit code 0. ChromaDB có 24 baseline, 21 corrupted và 24 repaired documents. Dashboard trả HTTP 200 và cả bảy màn hình có 0 exception trong AppTest.
- **Artifact/log:** `data/results/`, `data/quality/`, `data/reports/`, `data/chroma/`, `report/group_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Báo cáo cuối cần so sánh công bằng tác động của corruption và khả năng phục hồi của pipeline.
- **Các phương án đã cân nhắc:** (1) Chạy riêng từng corruption với test set khác nhau; (2) sửa trực tiếp corrupted data rồi đo lại; (3) giữ nguyên một test set cho cả ba trạng thái và repair bằng cách rebuild từ trusted raw.
- **Phương án đã chọn:** Phương án 3 — dùng cùng evaluation set và rebuild hoàn toàn từ raw data.
- **Lý do:** Fixed test set giữ điều kiện đánh giá không đổi, còn rebuild từ raw bảo đảm repair không che lỗi hoặc tiếp tục sử dụng dữ liệu đã bị corruption. Collection được tạo lại thay vì append nên tránh duplicate tích lũy.
- **Bằng chứng quyết định phù hợp:** Baseline và repaired có cùng 24 documents, Quality/Freshness PASS và metrics giống nhau. Hai lần chạy repair tạo cùng hash cho repaired dataset và repaired metrics.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi chạy lại checkpoint, pipeline không chạy được trên Python 3.10 do `ImportError: cannot import name 'UTC' from 'datetime'`. Sau khi chuyển Python, bước embedding báo chưa tìm thấy model MiniLM trong local cache.
- **Lệnh hoặc bước tái hiện:** Chạy `script/run_phase1.py` trong virtual environment cũ, sau đó chạy lại bằng `.venv` Python 3.11 khi model chưa được cache.
- **Nguyên nhân gốc:** Source sử dụng `datetime.UTC`, yêu cầu Python 3.11+. Đồng thời `sentence-transformers/all-MiniLM-L6-v2` chưa có trên máy nên lần đầu cần mạng.
- **Cách xử lý:** Cài Python 3.11.9, thêm Python và Scripts vào User PATH, tạo `.venv`, cài dependencies và tải MiniLM một lần. Các lần chạy sau sử dụng cache local.
- **Cách xác minh sau khi sửa:** Smoke test import ChromaDB, Great Expectations và sentence-transformers PASS; baseline pipeline chạy exit code 0 và index đủ 24 documents.
- **Điều học được:** Reproducibility không chỉ phụ thuộc code mà còn phụ thuộc version contract, dependency và model artifacts. Môi trường phải được kiểm tra trước khi đánh giá checkpoint.

## 7. Hiểu biết về luồng end-to-end

**1. Dữ liệu đi từ Crossref đến vector index như thế nào?**

Crossref response được giữ nguyên để bảo đảm lineage, sau đó parse thành stable `PaperRecord`. Cleaning chuẩn hóa văn bản, loại record thiếu dữ liệu, deduplicate theo `paper_id`, tính `age_days` và ghép năm trường thành `text_for_embedding`. Great Expectations và Freshness SLA kiểm tra dữ liệu trước khi MiniLM tạo embedding và ChromaDB lưu documents cùng metadata.

**2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**

Mỗi câu hỏi có đáp án chuẩn và danh sách `ground_truth_doc_ids`. Retrieval Hit Rate kiểm tra kết quả tìm kiếm có chứa tài liệu chuẩn không. Token F1 so sánh token trong câu trả lời với ground truth; Judge đánh giá mức đúng của answer. Test set của CP2 gồm 10 câu thuộc `summary`, `authors`, `date`, `category` và `multi_hop`.

**3. Quality checks khác freshness monitoring ở điểm nào?**

Quality checks xác minh contract cấu trúc và nội dung như row count, not-null, uniqueness và minimum summary length. Freshness monitoring tập trung vào tuổi dữ liệu, tính stale ratio từ `age_days > 180` và cảnh báo nếu tỷ lệ này vượt 25%. Một dataset có thể đúng schema nhưng vẫn quá cũ.

**4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**

Nếu thay câu hỏi hoặc ground truth giữa các trạng thái thì chênh lệch metrics có thể do đề đánh giá thay đổi, không phải do corruption hoặc repair. Fixed evaluation set giúp giữ biến kiểm soát và tạo phép so sánh có ý nghĩa.

**5. Repair được xem là thành công dựa trên artifact và metric nào?**

Repair thành công khi repaired dataset trở lại 24 unique papers, GX và Freshness đều PASS, Chroma repaired collection có 24 documents, và các metrics repaired bằng baseline. Việc hai lần chạy tạo cùng SHA-256 cho repaired dataset và metrics chứng minh tính idempotent.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | Corruption làm mất 40% retrieval hit; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0.9044 | 0.8832 | 0.9044 | Answer quality giảm nhẹ và trở lại đúng baseline |
| `judge_accuracy` | 0.9000 | 0.9000 | 0.9000 | Không đổi; judge chưa nhạy với mọi retrieval degradation |
| `mean_judge_score` | 4.4000 | 4.2000 | 4.4000 | Chất lượng tổng thể giảm rồi phục hồi |
| Quality checks | PASS | FAIL | PASS | Phát hiện blank summary và duplicate ID |
| Freshness status | PASS | FAIL | PASS | Phát hiện stale ratio vượt ngưỡng 25% |

### Kết luận từ số liệu

1. Sáu data corruptions làm mất, rỗng, nhiễu, cũ và trùng dữ liệu → Quality Gate và Freshness chuyển từ PASS sang FAIL → retrieval Hit Rate giảm từ 1.0 xuống 0.6, Token F1 giảm từ 0.9044 xuống 0.8832 và mean judge score giảm từ 4.4 xuống 4.2.
2. Repair loại bỏ derived corrupted state và rebuild từ trusted raw → Quality/Freshness trở lại PASS → Hit Rate, F1 và judge score trở lại đúng baseline.

Corruption ảnh hưởng rõ nhất đến retrieval là `drop_latest_records`, vì nó loại trực tiếp 20% bài báo mới nhất và có thể xóa các document IDs được test set tham chiếu. `stale_date` tạo ảnh hưởng rõ nhất lên observability vì đẩy stale ratio vượt 25%. Blank summary và duplicate rows trực tiếp làm GX expectations thất bại.

Kết quả khác kỳ vọng ban đầu là `judge_accuracy` vẫn giữ 0.9 dù retrieval Hit Rate giảm xuống 0.6. Giả thuyết là một số câu trả lời vẫn được tạo đúng từ exact lookup, context còn lại hoặc heuristic judge chưa đủ nhạy. Tôi kiểm tra giả thuyết bằng cách xem `corrupted_answers.json`, retrieved document IDs, Token F1 và mean judge score. Hai metric sau vẫn giảm, cho thấy corruption có tác động dù accuracy nhị phân không đổi.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Việc đối chiếu source code, artifact và pass signal của từng checkpoint giúp phát hiện lỗi mà chỉ nhìn vào file output sẽ không thấy.
2. Data Quality Gate và Freshness bổ sung cho nhau: một bên kiểm tra contract, một bên kiểm tra tính cập nhật; cả hai cần được liên kết với agent metrics để chứng minh silent failure.
3. Retrieval và answer metrics không luôn thay đổi cùng mức. Cần đọc nhiều tín hiệu và xem câu trả lời chi tiết thay vì kết luận chỉ từ một chỉ số như judge accuracy.

### Nếu có thêm thời gian

Tôi sẽ bổ sung pytest và GitHub Actions để tự động kiểm tra provenance, schema, GX suite, collection counts và metric recovery trong mỗi pull request. Dashboard cũng có thể lưu lịch sử nhiều lần chạy để biểu diễn drift theo thời gian. Cải thiện được đo bằng test coverage trên 80%, pipeline CI exit code 0 và cảnh báo tự động khi repaired metrics lệch baseline quá tolerance định trước.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đỗ Mạnh Đoan  
**Ngày xác nhận:** 2026-09-25
