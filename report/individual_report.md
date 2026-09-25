# Báo cáo cá nhân — Checkpoint 2: Benchmark Test Set & ChromaDB Vector Store

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Thị Hoài Thương |
| MSSV | 2A202602898 |
| Khóa/Lớp | K4 |
| Tên nhóm | Khô Gà |
| Vai trò | Test |
| Repository | https://github.com/mDoanzz43/K4-L3A-Day10-KhoGa-DataPipeline |
| Phạm vi báo cáo | Chỉ Checkpoint 2 |
| Ngày cập nhật | 25/09/2026 |

## 2. Mục tiêu Checkpoint 2

Xây dựng bộ câu hỏi benchmark có ground truth từ dữ liệu bài báo đã làm sạch và lập chỉ mục vector cục bộ bằng ChromaDB. Bộ benchmark dùng để kiểm tra việc retrieval có lấy đúng tài liệu được gắn trong `ground_truth_doc_ids` hay không.

## 3. Phần việc đã thực hiện

| Hạng mục | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Sinh benchmark test set | `src/evaluation/testset.py` — `build_test_set` | DataFrame từ `data/clean/papers_clean.json` | `data/eval/test_set.json` | Hoàn thành |
| Nạp/đọc benchmark | `src/evaluation/testset.py` — `load_or_create_test_set` | Cleaned DataFrame và đường dẫn test set | `TestSet.samples` | Hoàn thành |
| Lập chỉ mục ChromaDB | `src/retrieval/index.py` — `LocalEmbeddingIndex.build_from_clean` | `data/clean/papers_clean.json` | Collection `papers-baseline`, manifest `data/embeddings/papers_embeddings.json` | Hoàn thành theo artifact |
| Truy vấn semantic | `src/retrieval/index.py` — `semantic_search` | Query và `top_k` | Danh sách `SearchResult` | Đã triển khai |

## 4. Benchmark Test Set

Artifact `data/eval/test_set.json` hiện có **10 câu hỏi**, với hai câu cho mỗi loại:

| Loại | Số câu | ID |
| --- | ---: | --- |
| `summary` | 2 | `eval_001`, `eval_002` |
| `authors` | 2 | `eval_003`, `eval_004` |
| `date` | 2 | `eval_005`, `eval_006` |
| `category` | 2 | `eval_007`, `eval_008` |
| `multi_hop` | 2 | `eval_009`, `eval_010` |

Mỗi sample gồm các trường bắt buộc:

```json
{
  "id": "eval_001",
  "type": "summary",
  "question": "...",
  "ground_truth": "...",
  "ground_truth_doc_ids": ["10.1145/3637528.3671801"]
}
```

File cũng giữ trường `question_type` để tương thích với evaluator hiện có. Ground truth được lấy trực tiếp từ các cột cleaned data: `summary`, `authors_joined`, `published`, `categories_joined`; `paper_id` được đưa vào `ground_truth_doc_ids`. Hai câu `multi_hop` có hai document ID vì kết hợp nội dung của hai bài báo.

## 5. ChromaDB Vector Index

Manifest `data/embeddings/papers_embeddings.json` xác nhận các thông tin sau:

| Thuộc tính | Giá trị |
| --- | --- |
| Backend | `chroma` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Collection | `papers-baseline` |
| Persistent path | `data/chroma` |
| Nguồn documents | Cleaned papers, với `text_for_embedding` làm nội dung embedding |

Mỗi document index gồm `record_id`, `paper_id`, `title`, `content` và metadata phục vụ trả lời gồm ngày xuất bản, tác giả, categories, summary, URL.

## 6. Cách xác minh CP2

Sinh lại bộ 10 câu benchmark:

```powershell
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

Kết quả cần nhận:

```text
Tín hiệu hoàn thành: Sinh được 10 câu hỏi test
```

Smoke test tạo index và truy vấn hai tài liệu:

```powershell
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); idx=LocalEmbeddingIndex(s, collection_name='papers-baseline'); idx.build_from_clean(); res=idx.semantic_search('machine learning', top_k=2); print(f'Tín hiệu hoàn thành: Tìm thấy {len(res)} tài liệu liên quan')"
```

Kết quả cần nhận:

```text
Tín hiệu hoàn thành: Tìm thấy 2 tài liệu liên quan
```

## 7. Lỗi đã gặp trong phạm vi CP2

- **Triệu chứng:** `ModuleNotFoundError: No module named 'core'` khi chạy lệnh CP2 trong virtual environment.
- **Nguyên nhân:** project sử dụng layout `src/`, nhưng package chưa được cài ở editable mode nên Python không tìm thấy module `core`.
- **Cách xử lý:** tại thư mục gốc project, sau khi kích hoạt `.venv`, chạy:

```powershell
python -m pip install -e .
```

- **Cách kiểm tra:**

```powershell
python -c "from core.config import load_settings; print('Import core thành công')"
```

## 8. Cam kết phạm vi

Báo cáo này chỉ ghi nhận công việc, artifact và lệnh xác minh của **Checkpoint 2**. Không bao gồm nội dung, kết quả hoặc metric của các checkpoint khác.

**Họ và tên:** Lê Thị Hoài Thương  
**Ngày xác nhận:** 2026-09-25