# FINAL PLAN: ĐÁNH GIÁ RAG BẰNG RAGBENCH + RAGAS (Version 5)

Đây là kế hoạch tổng thể cuối cùng bao gồm 4 bước nối tiếp nhau, trong đó **Bước 4 đã được thiết kế lại hoàn toàn** dựa trên 4 tiêu chí đánh giá Ragas chính thức, phân tích kỹ từng model trên account của bạn, và tính toán chính xác thời gian chạy.

---

## Bước 1: Thu thập Dữ liệu (Data Acquisition)
- Xóa data test cũ. Dùng `datasets` tải trực tiếp tập `hotpotqa` (~2700 mẫu) từ `galileo-ai/ragbench`.
- **Output:** `test_data/ragbench/hotpotqa_raw.jsonl`.

## Bước 2: Lọc "Ground Truth" chất lượng (Data Filtering)
- Tính tổng điểm 4 tiêu chí TRACE. Sắp xếp giảm dần, lấy **đúng 500 dòng đầu tiên**. Đổi tên `response` thành `ground_truth`.
- **Output:** `test_data/ragbench/hotpotqa_top500.jsonl`.

## Bước 3: Chạy hệ thống RAG nội bộ (RAG Runner)
- Đưa 500 mẫu qua pipeline RAG nội bộ để sinh `response_AI` và lấy `top_chunks`. (Phần này không dùng API ngoài nên chạy một lèo xong luôn).
- **Output:** `tests/results/rag_results.jsonl` chứa đủ 500 kết quả thô.

---

## Bước 4: Chấm điểm bằng RAGAS (Thiết kế lại hoàn toàn)

### 4.0. Phân tích 5 Model trên Account của bạn

Từ screenshot AI Studio, bạn có 5 model khả dụng:

| Model | Loại | RPM | TPM | RPD | Dùng được cho Ragas? |
|---|---|---|---|---|---|
| **Gemini 3.1 Flash Lite** | Text-out models | 15 | 250K | 500 | ✅ LLM Judge |
| **Gemini Embedding 1** | Other models (Embedding) | 100 | 30K | 1,000 | ✅ Embedding only |
| **Gemini Embedding 2** | Other models (Embedding) | 100 | 30K | 1,000 | ✅ Embedding only |
| **Gemma 4 26B** | Other models (Text Gen) | 15 | Unlimited | 1,500 | ✅ LLM Judge |
| **Gemma 4 31B** | Other models (Text Gen) | 15 | Unlimited | 1,500 | ✅ LLM Judge |

> [!IMPORTANT]
> **Phân loại quan trọng:**
> - **Gemini Embedding 1 & 2** → CHỈ dùng cho embedding (chuyển text thành vector), **KHÔNG THỂ** dùng làm LLM judge vì không sinh text được.
> - **Gemma 4 26B & 31B** → Mặc dù AI Studio xếp vào "Other models", nhưng đây thực chất là **model text generation** (Gemma 4 là open-weight LLM của Google). Hoàn toàn dùng được làm LLM judge cho Ragas, và có **1,500 RPD** — gấp 3 lần Gemini 3.1 Flash Lite!

### 4.1. Ragas cần gọi API như thế nào?

Ragas dùng 2 loại API call:
- **LLM call** (text generation): Cho 3 metric — Faithfulness, Context Precision, Context Recall
- **LLM call + Embedding call**: Cho 1 metric — Answer Relevance

Chi tiết từng metric:

| Metric | Bước 1 | Bước 2 | Tổng calls/mẫu |
|---|---|---|---|
| **Faithfulness** | LLM tách answer → claims | LLM verify từng claim vs context | **2 LLM calls** |
| **Answer Relevance** | LLM sinh 3 câu hỏi từ answer | Embedding tính cosine similarity | **1 LLM + 1 Embedding** |
| **Context Precision** | LLM đánh giá từng chunk relevant? | — | **1 LLM call** |
| **Context Recall** | LLM tách ground_truth → claims | LLM verify claims vs context | **2 LLM calls** |
| **TỔNG mỗi mẫu** | | | **6 LLM + 1 Embedding** |

### 4.2. Tính toán cho 500 mẫu

| Loại call | Calls/mẫu | Tổng (500 mẫu) |
|---|---|---|
| LLM calls | 6 | **3,000** |
| Embedding calls | 1 | **500** |

### 4.3. So sánh 3 combo Model — Thời gian chạy 500 mẫu

---

#### Combo 1: Gemma 4 31B (LLM) + Gemini Embedding 1 (Embedding) ⭐ KHUYẾN NGHỊ

| Thông số | LLM (Gemma 4 31B) | Embedding (Gemini Embedding 1) |
|---|---|---|
| RPM | 15 | 100 |
| RPD | **1,500** | **1,000** |
| Calls cần | 3,000 | 500 |
| Số ngày cần | 3,000 ÷ 1,500 = **2 ngày** | 500 ÷ 1,000 = **< 1 ngày** ✅ |

**Tính thời gian runtime/ngày:**
- 15 RPM → an toàn chạy ~10 calls/phút (có sleep buffer)
- Mỗi giờ: 10 × 60 = 600 calls
- Ngày 1: chạy ~2.5 giờ → hit 1,500 RPD → đã chấm ~250 mẫu
- Ngày 2: chạy ~2.5 giờ → nốt 1,500 calls → xong 500 mẫu

> **Tổng: 2 ngày, mỗi ngày ~2.5 giờ runtime**

**Ưu điểm:**
- Gemma 4 31B là model Dense, chất lượng cao nhất trong danh sách
- RPD cao nhất (1,500), Unlimited TPM → không lo bị giới hạn token
- Gemma 4 31B có reasoning tốt → phù hợp làm judge

---

#### Combo 2: Gemma 4 26B (LLM) + Gemini Embedding 1 (Embedding)

| Thông số | LLM (Gemma 4 26B) | Embedding (Gemini Embedding 1) |
|---|---|---|
| RPM | 15 | 100 |
| RPD | **1,500** | **1,000** |
| Calls cần | 3,000 | 500 |
| Số ngày cần | **2 ngày** | **< 1 ngày** ✅ |

> **Tổng: 2 ngày, mỗi ngày ~2.5 giờ** (giống Combo 1)

**So với Combo 1:** Gemma 4 26B dùng kiến trúc MoE (chỉ activate 4B params), nhanh hơn nhưng chất lượng reasoning kém hơn 31B một chút. Cũng là lựa chọn tốt.

---

#### Combo 3: Gemini 3.1 Flash Lite (LLM) + Gemini Embedding 1 (Embedding)

| Thông số | LLM (Gemini 3.1 Flash Lite) | Embedding (Gemini Embedding 1) |
|---|---|---|
| RPM | 15 | 100 |
| RPD | **500** ❌ | **1,000** |
| Calls cần | 3,000 | 500 |
| Số ngày cần | 3,000 ÷ 500 = **6 ngày** ❌ | **< 1 ngày** ✅ |

> **Tổng: 6 ngày, mỗi ngày ~50 phút** — Quá chậm!

---

### 4.4. Tóm tắt lựa chọn

| | Combo 1 ⭐ | Combo 2 | Combo 3 |
|---|---|---|---|
| LLM Model | Gemma 4 31B | Gemma 4 26B | Gemini 3.1 Flash Lite |
| Embedding | Gemini Embedding 1 | Gemini Embedding 1 | Gemini Embedding 1 |
| Thời gian (1 key) | **2 ngày** | **2 ngày** | **6 ngày** |
| Thời gian (2 keys) | **1 ngày** (~5h) | **1 ngày** (~5h) | **3 ngày** |
| Chất lượng judge | ⭐⭐⭐ Tốt nhất | ⭐⭐ Tốt | ⭐⭐ Tốt |

> [!TIP]
> **Muốn chạy 1 lượt xong luôn (1 ngày)?** Cần **2 API keys** + dùng **Gemma 4 31B**. Khi key 1 hết 1,500 RPD → tự chuyển key 2 → tổng 3,000 calls vừa đủ.

### 4.5. Cơ chế API Key Rotation + Resume

#### A. File API Keys
Tạo file `api_keys.txt` — mỗi dòng 1 API key:
```
AIzaSy...key1...
AIzaSy...key2...
```

#### B. Cơ chế hoạt động

```
Bắt đầu chạy
    │
    ▼
Đọc file CSV → Đã chấm N mẫu? → Bỏ qua N mẫu, bắt đầu từ N+1
    │
    ▼
Lấy API Key #1 từ api_keys.txt
    │
    ▼
┌── Chấm 1 mẫu (4 metrics) ──── Lưu ngay vào CSV ──── Sleep 6 giây ──┐
│                                                                        │
│   Gặp lỗi 429? ───Yes──→ Chuyển sang Key tiếp theo                   │
│       │                       │                                        │
│       No                      Hết key? ───Yes──→ DỪNG + In thông báo  │
│       │                       │                                        │
│       ▼                       No → Tiếp tục chấm                      │
│   Hết 500 mẫu? ───Yes──→ XONG! In kết quả tổng hợp                  │
│       │                                                                │
│       No ──────────────────────────────────────────────────────────────┘
```

#### C. Khi tất cả key hết quota
```
═══════════════════════════════════════════════════════
⚠️  TẤT CẢ API KEY ĐÃ HẾT QUOTA
═══════════════════════════════════════════════════════
Đã chấm được: 287/500 mẫu
Tiến trình đã lưu tại: tests/results/ragbench_evaluation_final.csv

Cách tiếp tục:
  1. Thêm API key mới vào api_keys.txt → chạy lại script
  2. Đợi 24h cho Google reset quota → chạy lại script
  
Script sẽ TỰ ĐỘNG tiếp tục từ mẫu 288.
═══════════════════════════════════════════════════════
```

#### D. Rate Limiting
```python
from ragas.run_config import RunConfig

run_config = RunConfig(
    max_workers=1,          # Chạy tuần tự, không song song
    max_wait=180,           # Đợi tối đa 3 phút nếu bị rate limit
    max_retries=5,          # Thử lại 5 lần khi gặp lỗi
)
```
- Sleep **6 giây** sau mỗi mẫu (10 calls/phút < 15 RPM)
- Chạy **từng mẫu 1** (không batch) để kiểm soát chính xác

### 4.6. Code Setup

```python
# LLM Judge — Gemma 4 31B
from langchain_google_genai import ChatGoogleGenerativeAI
from ragas.llms import LangchainLLMWrapper

llm = ChatGoogleGenerativeAI(
    model="gemma-4-31b-it",
    google_api_key=current_api_key
)
ragas_llm = LangchainLLMWrapper(llm)

# Embedding — Gemini Embedding 1
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=current_api_key
)
ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)

# Ragas Evaluate — chạy từng mẫu
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

score = evaluate(
    dataset=single_sample_dataset,
    llm=ragas_llm,
    embeddings=ragas_embeddings,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    run_config=run_config
)
```

### 4.7. Cấu trúc File Output

File `tests/results/ragbench_evaluation_final.csv`:

| id | question | ground_truth | top_chunks | faithfulness | answer_relevancy | context_precision | context_recall |
|---|---|---|---|---|---|---|---|
| 5ab67... | Which has more... | Disporum has... | ["Boltonia is..."] | 0.75 | 0.82 | 1.0 | 0.5 |

### 4.8. Quy trình thực tế

#### Kịch bản 1: Có 2 API keys — Chạy 1 lượt xong luôn (~5 giờ)
1. Cho 2 key vào `api_keys.txt`
2. Chạy script → Key 1 chấm ~250 mẫu (~2.5h) → hết 1,500 RPD
3. Tự chuyển Key 2 → chấm nốt ~250 mẫu (~2.5h)
4. **XONG trong 1 ngày!** 🎉

#### Kịch bản 2: Chỉ có 1 API key — 2 ngày
1. Ngày 1: Chạy script → chấm ~250 mẫu (~2.5h) → hết 1,500 RPD → dừng
2. Ngày 2: Chạy lại script → tự resume từ mẫu 251 → chấm nốt → **XONG!**

### 4.9. Files cần tạo

| File | Mô tả |
|---|---|
| `scripts/step4_ragas_evaluate.py` | Script chính chấm 4 metrics Ragas với API key rotation + resume |
| `api_keys.txt` | Danh sách API keys (mỗi dòng 1 key), nằm trong `.gitignore` |
| `tests/results/ragbench_evaluation_final.csv` | Kết quả đánh giá cuối cùng |

---

## Open Questions

> [!IMPORTANT]
> **Q1:** Bạn có bao nhiêu API key (bao nhiêu Google Cloud project)? Nếu có 2 key thì chạy xong trong 1 ngày (~5 giờ) với Gemma 4 31B.

> [!IMPORTANT]
> **Q2:** Bạn muốn dùng **Gemma 4 31B** (chất lượng cao hơn, dense model) hay **Gemma 4 26B** (MoE, nhanh hơn)? Cả 2 đều có 1,500 RPD.
