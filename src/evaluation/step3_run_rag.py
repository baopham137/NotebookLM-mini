"""
Bước 3: Chạy hệ thống RAG nội bộ trên 500 mẫu hotpotqa đã lọc.

Output: tests/results/rag_results_hotpotqa.jsonl  (append, hỗ trợ resume)
        tests/results/rag_results_hotpotqa.csv     (ghi cuối sau khi xong)

Cách dùng:
    python -m src.evaluation.step3_run_rag
    # hoặc
    python src/evaluation/step3_run_rag.py
"""

import os
import sys

# Bắt buộc stdout UTF-8 (tránh lỗi UnicodeEncodeError trên Windows)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import torch  # Phải import đầu tiên để tránh WinError 1114 (DLL conflict)
import json
import uuid
import time
import logging
import requests
import pandas as pd

# --- Thêm project root vào PATH ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.ingestion.indexing import VectorStoreManager
from src.ingestion.chunking import RecursiveCharacterChunker
from src.retrieval.search_engine import SearchEngine
from src.utils.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INPUT_FILE  = "test_data/ragbench/hotpotqa_top500.jsonl"
RESULTS_DIR = "tests/results"
OUTPUT_JSONL = os.path.join(RESULTS_DIR, "rag_results_hotpotqa.jsonl")
OUTPUT_CSV   = os.path.join(RESULTS_DIR, "rag_results_hotpotqa.csv")

# Gọi thẳng Ollama để tránh vấn đề settings.llama_server_url đã "đóng băng" lúc import
OLLAMA_URL   = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:3b"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def chunk_text(text: str, notebook_id: str, source_name: str) -> list:
    """Băm văn bản thành các chunk với metadata đầy đủ."""
    chunker = RecursiveCharacterChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    texts = chunker.chunk_text(text)
    return [
        {
            "content": t,
            "metadata": {
                "notebook_id": notebook_id,
                "source_file": source_name,
                "chunk_id": str(uuid.uuid4()),
            },
        }
        for t in texts
    ]


def call_ollama(prompt: str) -> str:
    """Gọi Ollama API trực tiếp (non-stream) để lấy câu trả lời."""
    system = (
        "You are a helpful assistant. "
        "Answer questions based ONLY on the provided context. "
        "Be concise and accurate. If the context lacks the answer, say so clearly."
    )
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
    }
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        logger.error(f"Lỗi gọi Ollama: {e}")
        return f"Ollama Error: {e}"


def build_prompt(question: str, context: str) -> str:
    return (
        f"Below is context retrieved from documents:\n"
        f"====================\n{context}\n====================\n\n"
        f"Question: {question}"
    )


def load_done_ids() -> set:
    """Đọc các id đã xử lý từ file JSONL để hỗ trợ resume."""
    done = set()
    if os.path.exists(OUTPUT_JSONL):
        with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        done.add(json.loads(line)["id"])
                    except Exception:
                        pass
    return done


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_rag():
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Không tìm thấy {INPUT_FILE}. Hãy chạy Step 2 trước.")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # --- Resume ---
    done_ids = load_done_ids()
    if done_ids:
        logger.info(f"[Resume] Đã có {len(done_ids)} mẫu, bỏ qua và chạy tiếp phần còn lại.")

    # --- Đọc dữ liệu ---
    samples = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    logger.info(f"Đã tải {len(samples)} mẫu từ {INPUT_FILE}.")

    # --- Khởi tạo pipeline ---
    logger.info("Khởi tạo RAG Pipeline...")
    vector_store  = VectorStoreManager()
    search_engine = SearchEngine(vector_store)

    last_notebook_id = None
    records = []

    for i, item in enumerate(samples):
        q_id        = item.get("id")
        question    = item.get("question", "")
        documents   = item.get("documents", [])
        ground_truth = item.get("ground_truth", "")

        # Bỏ qua mẫu đã có kết quả (resume)
        if q_id in done_ids:
            continue

        notebook_id = f"eval_{q_id}"
        logger.info(f"[{i+1}/{len(samples)}] Q: {question[:90]}...")

        # --- 1. Indexing ---
        full_text = "\n\n".join(documents) if isinstance(documents, list) else str(documents)
        chunks = chunk_text(full_text, notebook_id, source_name="ragbench_hotpotqa")
        if chunks:
            vector_store.index_chunks(chunks)

        # --- 2. Retrieval ---
        t0 = time.time()
        context_str, raw_chunks = search_engine.retrieve(question, notebook_id=notebook_id, top_k=5)
        latency_retrieve_s = round(time.time() - t0, 3)
        retrieved_texts = [r["content"] for r in raw_chunks]

        # --- 3. Generation ---
        t1 = time.time()
        prompt      = build_prompt(question, context_str)
        ai_response = call_ollama(prompt)
        latency_generate_s = round(time.time() - t1, 3)

        logger.info(f"  → response ({latency_generate_s}s): {ai_response[:100]}...")

        record = {
            "id":                  q_id,
            "question":            question,
            "documents":           full_text,
            "ground_truth":        ground_truth,
            "response_AI":         ai_response,
            "top_chunks":          retrieved_texts,
            "latency_retrieve_s":  latency_retrieve_s,
            "latency_generate_s":  latency_generate_s,
        }
        records.append(record)

        # --- 4. Lưu ngay từng dòng vào JSONL (tránh mất dữ liệu nếu crash) ---
        with open(OUTPUT_JSONL, "a", encoding="utf-8") as out_f:
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # --- 5. Cleanup Qdrant của mẫu trước ---
        if last_notebook_id is not None:
            vector_store.delete_notebook_chunks(last_notebook_id)
        last_notebook_id = notebook_id

    # Dọn notebook cuối
    if last_notebook_id is not None:
        vector_store.delete_notebook_chunks(last_notebook_id)

    # --- Xuất CSV tổng hợp từ file JSONL (bao gồm cả các mẫu resume) ---
    all_records = []
    with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_records.append(json.loads(line))

    df = pd.DataFrame(all_records)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    logger.info("=" * 60)
    logger.info(f"Hoàn tất! Tổng cộng {len(df)} mẫu.")
    logger.info(f"  JSONL : {OUTPUT_JSONL}")
    logger.info(f"  CSV   : {OUTPUT_CSV}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_rag()
