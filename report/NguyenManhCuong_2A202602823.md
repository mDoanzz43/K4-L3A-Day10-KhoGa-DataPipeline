# Báo cáo vai trò cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | **Nguyễn Mạnh Cường** |
| MSSV | **2A202602823** |
| Khóa/Lớp | K4 |
| Tên nhóm | KhoGa |
| Vai trò chính | Baseline Pipeline & Data Corruption Owner — Checkpoint 3 và Checkpoint 4 |
| Git identity | `nmc2004nd` |
| Repository | `https://github.com/mDoanzz43/K4-L3A-Day10-KhoGa-DataPipeline` |
| Commit bằng chứng | `02f8a21` — `feat: complete baseline corruption and repair pipelines` |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Checkpoint 3 — Baseline orchestration | `src/pipelines/phase1.py`, `main()` | Raw records, clean/testset/quality/index modules | Clean CSV/JSON, Chroma baseline, baseline metrics và báo cáo Pha 1 | Hoàn thành |
| Checkpoint 4 — Synthetic corruption | `src/ingestion/corruption.py`, `corrupt_clean_dataframe()` | Clean dataframe 24 bài báo | Corrupted dataframe và log đủ 6 kịch bản | Hoàn thành |
| Checkpoint 4 — Đánh giá suy giảm | Phần corrupted trong `src/pipelines/corruption_flow.py` | Clean dataset, test set baseline | Corrupted Chroma collection, quality/freshness alerts và corrupted metrics | Hoàn thành |
| Báo cáo kết quả | `src/observability/reporting.py` | Metrics, quality và freshness artifacts | `phase1_report.md` và phần impact analysis | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tích hợp CP0–CP2 vào pipeline | Ingestion, cleaning, testset, GX và Chroma modules | Giữ tương thích schema và chạy thành công end-to-end sau merge |
| Kiểm tra RAG Agent offline | `src/retrieval/agent.py`, `src/retrieval/llm.py` | Mock Agent truy vấn được Chroma và không còn lỗi `bind_tools()` |
| Kiểm tra portability | `src/retrieval/index.py` | Manifest lưu `data/chroma` thay vì đường dẫn tuyệt đối trên máy cá nhân |
| Đối chiếu kết quả nhóm | Luồng repaired thuộc Checkpoint 5 | Xác nhận repaired quay về cùng metrics baseline; không nhận ownership CP5 |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Điều phối baseline end-to-end | `src/pipelines/phase1.py` | 24 bài sạch, collection `papers-baseline` có 24 documents | `LLM_PROVIDER=mock python script/run_phase1.py` |
| Đo baseline benchmark | `data/results/baseline_metrics.json` | Hit Rate `1.0000`, Token F1 `1.0000` | Đọc metrics JSON và `phase1_report.md` |
| Triển khai sáu lỗi dữ liệu | `src/ingestion/corruption.py` | Drop latest, blank summary, noise, truncate title, stale date, duplicate rows | Kiểm tra `scenario_count = 6` trong corruption log |
| Đánh giá dữ liệu corrupted | `data/results/corrupted_metrics.json` | Hit Rate `0.0000`, Token F1 `0.2546` | `LLM_PROVIDER=mock python script/run_corruption_flow.py` |
| Chứng minh observability alert | `data/quality/corrupted_quality_report.json`, `corrupted_freshness_report.json` | Quality Gate FAIL, Freshness FAIL, stale ratio `42.86%` | Đối chiếu JSON và corruption report |
| Ghi nhận impact | `data/reports/corruption_report.md` | Có bảng Baseline/Corrupted/Repaired và phân tích tác động sáu lỗi | Mở báo cáo Markdown |

Output chính của phần việc là một baseline có thể tái hiện và một corrupted dataset có log kiểm toán. Baseline đạt Hit Rate và Token F1 bằng `1.0`; khi áp dụng đồng thời sáu lỗi, Hit Rate giảm xuống `0.0`, Token F1 còn `0.2546`, Quality Gate và Freshness SLA đều báo FAIL. Đây là bằng chứng định lượng của silent failure: chương trình vẫn chạy và trả lời nhưng chất lượng đã suy giảm mạnh.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Checkpoint 3 cần nối các module rời rạc thành một pipeline có thứ tự rõ ràng: đọc raw, làm sạch, kiểm định, tạo testset, index Chroma, đánh giá và sinh báo cáo. Pipeline phải dừng nếu baseline không qua Quality Gate để tránh index dữ liệu không hợp lệ.

Checkpoint 4 cần tạo lỗi có kiểm soát nhưng vẫn giữ pipeline chạy được. Mục tiêu không phải gây crash mà là mô phỏng silent failure, sau đó đo xem retrieval và câu trả lời thay đổi bao nhiêu so với baseline trên cùng một test set.

### Cách triển khai

Baseline flow được triển khai theo thứ tự:

1. Đọc `crossref_records.json`; nếu không có dữ liệu thì sử dụng ingestion dual-mode.
2. Làm sạch và ghi `papers_clean.csv` cùng `papers_clean.json`.
3. Chạy GX Quality Gate và Freshness SLA trước khi index.
4. Tạo hoặc sử dụng lại benchmark 10 câu hỏi.
5. Xây mới collection `papers-baseline` bằng `all-MiniLM-L6-v2`.
6. Chạy evaluation, ghi metrics/answers và sinh `phase1_report.md`.

Corruption được triển khai deterministic để có thể tái hiện:

- Xóa `ceil(24 × 20%) = 5` bài mới nhất.
- Xóa summary của 3 dòng.
- Chèn noise lặp lại vào summary của 3 dòng.
- Cắt title của 5 dòng xuống tối đa 7 ký tự.
- Lùi ngày của 7 dòng đi 365 ngày.
- Thêm 2 dòng trùng lặp.

Sau khi sửa title, summary hoặc ngày, `summary_chars` và `text_for_embedding` được xây lại. Nhờ đó lỗi đi vào vector index thật, không chỉ xuất hiện ở cột hiển thị. Corrupted data được index vào collection riêng `papers-corrupted` và đánh giá bằng đúng test set baseline.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input baseline | `list[PaperRecord]`, run date, settings và `data/eval/test_set.json` |
| Output baseline | Clean dataframe có `paper_id`, `title`, `summary`, `age_days`, `text_for_embedding`; Chroma index; metrics/report |
| Input corruption | Clean dataframe đã qua Quality Gate, gồm các cột identity, text, date và joined metadata |
| Output corruption | Dataframe 21 dòng sau drop/add duplicate; corruption log; corrupted metrics và quality/freshness reports |
| Module phụ thuộc | `ingestion.cleaning`, `observability.quality`, `evaluation.metrics`, `retrieval.index` |
| Module sử dụng output | QA/evaluation pipeline, reporting và repair flow của Checkpoint 5 |
| Điều kiện lỗi cần xử lý | Không có raw records, baseline quality fail, thiếu cột corruption bắt buộc, testset/index chưa tồn tại |

### Cách xác minh

```bash
LLM_PROVIDER=mock python script/run_phase1.py
LLM_PROVIDER=mock python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline chạy thành công; corruption có đủ sáu loại; Quality/Freshness chuyển từ PASS sang FAIL; metrics corrupted thấp hơn baseline.
- **Kết quả thực tế:** baseline có 24 documents, Hit Rate/F1 `1.0000/1.0000`; corrupted có 21 dòng, Hit Rate/F1 `0.0000/0.2546`, Quality/Freshness đều FAIL.
- **Artifact/log:** `data/results/baseline_metrics.json`, `data/results/corruption_log.json`, `data/results/corrupted_metrics.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần so sánh baseline và corrupted mà không để dữ liệu hai trạng thái trộn lẫn trong vector store.
- **Các phương án đã cân nhắc:** (1) ghi đè cùng một Chroma collection sau mỗi trạng thái; (2) dùng collection riêng cho baseline, corrupted và repaired.
- **Phương án đã chọn:** Dùng các collection độc lập `papers-baseline`, `papers-corrupted`, `papers-repaired`, đồng thời xóa và xây lại collection cùng tên khi chạy lại.
- **Lý do:** Tách trạng thái giúp tránh leakage, dễ kiểm tra document count và giữ phép so sánh có thể tái hiện. Xóa rồi rebuild giúp chạy lặp không tích lũy duplicate.
- **Bằng chứng quyết định phù hợp:** Collection active lần lượt có 24, 21 và 24 documents; baseline/repaired cùng đạt Hit Rate và F1 bằng `1.0`, trong khi corrupted giảm rõ rệt.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `NotImplementedError` tại `request.model.bind_tools(...)` khi gọi RAG Agent với `LLM_PROVIDER=mock`.
- **Lệnh hoặc bước tái hiện:** Build Agent bằng mock provider, sau đó gọi `run_agent_question()` với một câu hỏi tác giả trong benchmark.
- **Nguyên nhân gốc:** `FakeListChatModel` của LangChain tạo được model nhưng không triển khai `bind_tools()`, trong khi `create_agent()` cần tool binding lúc invoke.
- **Cách xử lý:** Bổ sung `MockPaperAgent` cho chế độ offline. Adapter này dùng cùng Chroma index và `answer_question()` để truy xuất context; các provider thật vẫn dùng LangChain tool-calling Agent.
- **Cách xác minh sau khi sửa:** Agent trả về đúng danh sách `Muhamad Komarudin, Chelly Sabrina, Yessy Mulyani, Puput Budi Wintoro` từ corpus.
- **Điều học được:** Smoke test chỉ build object là chưa đủ; cần invoke Agent thật vì nhiều lỗi integration chỉ xuất hiện ở runtime.

## 7. Hiểu biết về luồng end-to-end

1. Crossref payload được lưu nguyên bản để bảo toàn lineage, sau đó parse thành `PaperRecord`. Cleaning chuẩn hóa DOI, text, ngày, tính `age_days`, deduplicate và tạo `text_for_embedding`. GX/Freshness kiểm tra dữ liệu trước khi MiniLM sinh vector và lưu vào ChromaDB.
2. Mỗi câu hỏi evaluation chứa đáp án chuẩn và `ground_truth_doc_ids`. Retrieval hit đúng khi ít nhất một DOI chuẩn xuất hiện trong các tài liệu truy xuất; Token F1 so sánh token giữa câu trả lời và ground truth để đo chất lượng nội dung.
3. Quality checks đo tính hợp lệ cấu trúc và giá trị hiện tại như null, unique, length và row count. Freshness monitoring đo tuổi dữ liệu theo `age_days`, cảnh báo khi tỷ lệ bài quá 180 ngày vượt 25%.
4. Phải giữ cùng test set để biến độc lập duy nhất là trạng thái dữ liệu. Nếu đổi câu hỏi giữa baseline và corrupted thì chênh lệch metric không còn chứng minh được tác động của corruption.
5. Repair được xem là thành công khi dữ liệu được rebuild từ raw đáng tin cậy, Quality/Freshness quay lại PASS, document count và uniqueness được phục hồi, đồng thời Hit Rate/F1 trở lại mức baseline. Đây là kết quả Checkpoint 5 của luồng nhóm mà tôi dùng để đối chiếu, không phải phạm vi ownership chính của tôi.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | Corruption làm mất toàn bộ retrieval hit trên 10 câu hỏi; repaired quay lại baseline |
| `mean_token_f1` | 1.0000 | 0.2546 | 1.0000 | Agent vẫn sinh câu trả lời nhưng phần lớn không còn khớp đáp án chuẩn |
| `judge_accuracy` | 1.0000 | 0.2000 | 1.0000 | Chỉ 20% câu corrupted được judge xem là đúng |
| `mean_judge_score` | 5.0000 | 1.8000 | 5.0000 | Chất lượng câu trả lời giảm từ mức tối đa xuống thấp |
| Quality checks | PASS | FAIL | PASS | Summary rỗng và DOI trùng kích hoạt cảnh báo |
| Freshness status | PASS | FAIL | PASS | Corrupted stale ratio `42.86%`, vượt SLA `25%` |

### Kết luận từ số liệu

1. Sáu corruption tích lũy → Quality Gate và Freshness chuyển sang FAIL → Hit Rate giảm `1.0000`, Token F1 giảm khoảng `0.7454`, Judge Accuracy giảm `0.8000`.
2. Rebuild từ raw đáng tin cậy ở luồng Checkpoint 5 → Quality/Freshness quay lại PASS → các metric repaired trở lại đúng baseline.

Corruption ảnh hưởng retrieval rõ nhất là `drop_latest_records`, vì nó loại trực tiếp 5 tài liệu mới và có thể làm ground-truth DOI không còn trong index. `blank_summary`, `inject_noise` và `truncate_title` tiếp tục làm giảm tín hiệu embedding và chất lượng câu trả lời. Vì sáu lỗi được áp dụng tích lũy trong cùng một run, tôi không khẳng định một lỗi duy nhất gây toàn bộ mức giảm; muốn định lượng riêng cần chạy ablation cho từng scenario.

Kết quả khác kỳ vọng ban đầu là corrupted dataframe có 21 dòng thay vì 19 dòng: xóa 5 trong 24 còn 19, sau đó kịch bản duplicate thêm 2 dòng thành 21. Retrieval Hit Rate giảm hẳn về `0.0` cũng mạnh hơn dự kiến. Tôi kiểm tra lại bằng cùng test set và corruption log để loại trừ nguyên nhân do đổi benchmark.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Pipeline end-to-end cần quality gate trước vector indexing; từng module chạy riêng không đảm bảo toàn luồng đúng.
2. Observability cần cả schema/content checks và freshness SLA vì hai nhóm lỗi phản ánh các rủi ro khác nhau.
3. RAG có thể tiếp tục trả lời dù dữ liệu đã hỏng; chỉ metric và quality signal mới làm silent failure nhìn thấy được.

### Nếu có thêm thời gian

Tôi sẽ bổ sung ablation experiment: tạo sáu dataset riêng, mỗi dataset chỉ chứa một corruption, sau đó đo Hit Rate/F1 và freshness/quality cho từng loại. Cải thiện này giúp quy mức suy giảm cho từng nguyên nhân thay vì chỉ đánh giá tác động tích lũy của cả suite.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Ngày xác nhận:** 2026-09-25
