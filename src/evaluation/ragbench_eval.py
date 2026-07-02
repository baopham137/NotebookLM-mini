"""
Script chính để chạy benchmark hệ thống RAG bằng Ragbench.

Cách dùng:
  # Tải data trước (chỉ cần làm 1 lần):
  python -m src.evaluation.download_ragbench

  # Chạy benchmark:
  python -m src.evaluation.ragbench_eval [subset] [num_samples]

  Ví dụ:
    python -m src.evaluation.ragbench_eval hotpotqa 10
    python -m src.evaluation.ragbench_eval msmarco 5
"""

import os
import sys
import json
import uuid
import logging
import numpy as np
import pandas as pd
from datetime import datetime

# --- Thêm project root vào PATH ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.llm.llm_client import LLMEngine
from src.ingestion.indexing import VectorStoreManager
from src.ingestion.chunking import RecursiveCharacterChunker
from src.retrieval.search_engine import SearchEngine
from src.utils.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = "test_data/ragbench"
RESULTS_DIR = "tests"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_samples(subset: str, num_samples: int) -> list:
    """Đọc dữ liệu từ file JSON đã tải về."""
    path = os.path.join(DATA_DIR, f"{subset}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Không tìm thấy {path}. Hãy chạy: python -m src.evaluation.download_ragbench trước."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    samples = data[:num_samples]
    logger.info(f"Đã tải {len(samples)} mẫu từ {path}")
    return samples


def chunk_text(text: str, notebook_id: str, source_name: str) -> list:
    """Băm văn bản thành các chunk với metadata đầy đủ."""
    chunker = RecursiveCharacterChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )
    texts = chunker.chunk_text(text)
    chunks = []
    for t in texts:
        chunks.append({
            "content": t,
            "metadata": {
                "notebook_id": notebook_id,
                "source_file": source_name,
                "chunk_id": str(uuid.uuid4()),
            }
        })
    return chunks


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Tính cosine similarity giữa 2 vector embedding."""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    norm = np.linalg.norm(v1) * np.linalg.norm(v2)
    if norm == 0:
        return 0.0
    return float(np.dot(v1, v2) / norm)


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def evaluate(subset: str = "hotpotqa", num_samples: int = 10):
    samples = load_samples(subset, num_samples)

    vector_store = VectorStoreManager()
    llm = LLMEngine()
    search_engine = SearchEngine(vector_store)

    # Lấy embedder để tính similarity cuối cùng
    from src.utils.vram_orchestrator import get_orchestrator
    embedder = get_orchestrator().get_embedder()

    records = []

    # Giữ lại notebook_id của mẫu CUỐI CÙNG để không xóa (dùng làm reference)
    last_notebook_id = None

    for i, item in enumerate(samples):
        question      = item.get("question", "")
        documents     = item.get("documents", [])  # list of strings
        ref_response  = item.get("response", "")
        adherence     = item.get("adherence_score", None)

        # Mỗi mẫu dùng 1 notebook_id riêng
        notebook_id = f"ragbench_{subset}_{i:04d}"
        logger.info(f"[{i+1}/{len(samples)}] Question: {question[:80]}...")

        # --- Bước 2: Index tài liệu ---
        full_text = "\n\n".join(documents) if isinstance(documents, list) else str(documents)
        chunks = chunk_text(full_text, notebook_id, source_name=f"ragbench_{subset}")
        if chunks:
            vector_store.index_chunks(chunks)
            logger.info(f"  Đã index {len(chunks)} chunks vào notebook '{notebook_id}'")

        # --- Bước 3a: Retrieve ---
        context_str, raw_chunks = search_engine.retrieve(question, notebook_id=notebook_id, top_k=5)
        retrieved_texts = [r["content"] for r in raw_chunks]

        # --- Bước 3b: Generate ---
        prompt = llm.build_rag_prompt(question, context_str)
        ai_response = "".join(llm.generate(prompt))
        logger.info(f"  AI response: {ai_response[:120]}...")

        # --- Tính Cosine Similarity giữa ref_response và ai_response ---
        try:
            emb_ref = embedder.embed_query(ref_response)
            emb_ai  = embedder.embed_query(ai_response)
            sim = cosine_similarity(emb_ref, emb_ai)
        except Exception as e:
            logger.warning(f"  Không tính được similarity: {e}")
            sim = None

        match = (sim >= 0.75) if sim is not None else None

        records.append({
            "notebook_id":       notebook_id,
            "question":          question,
            "documents":         full_text[:500] + "..." if len(full_text) > 500 else full_text,
            "response":          ref_response,
            "response_AI":       ai_response,
            "similarity_score":  round(sim, 4) if sim is not None else "",
            "true_false":        match,
            "adherence_score_ragbench": adherence,
        })

        # --- Bước 5: Dọn dẹp Qdrant (xóa tất cả trừ mẫu cuối) ---
        if last_notebook_id is not None:
            vector_store.delete_notebook_chunks(last_notebook_id)
            logger.info(f"  Đã xóa notebook tạm: {last_notebook_id}")

        last_notebook_id = notebook_id

    # notebook cuối cùng được giữ lại làm reference, không xóa
    logger.info(f"Giữ lại notebook reference: {last_notebook_id}")

    # --- Bước 5: Xuất kết quả ---
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"ragbench_{subset}_{timestamp}.csv")
    df = pd.DataFrame(records)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"\n{'='*60}")
    logger.info(f"Kết quả lưu tại: {out_path}")

    # In tóm tắt
    valid = df[df["similarity_score"] != ""]
    if not valid.empty:
        avg_sim = valid["similarity_score"].astype(float).mean()
        true_pct = (valid["true_false"].sum() / len(valid)) * 100
        logger.info(f"Tổng mẫu đánh giá : {len(df)}")
        logger.info(f"Avg Similarity    : {avg_sim:.4f}")
        logger.info(f"True (>= 0.75)    : {true_pct:.1f}%")
    logger.info("="*60)

    return out_path


if __name__ == "__main__":
    subset      = sys.argv[1] if len(sys.argv) > 1 else "hotpotqa"
    num_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    evaluate(subset, num_samples)
