"""
Hybrid Search — Tầng Truy xuất Lai
Chạy song song Semantic (Qdrant) và Keyword (BM25),
sau đó kết hợp kết quả bằng Reciprocal Rank Fusion (RRF).
"""
import logging
import uuid
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from ..utils.config import settings
from ..ingestion.indexing import VectorStoreManager
from .bm25_index import get_bm25_index, BM25Document

logger = logging.getLogger(__name__)

# Hệ số RRF tiêu chuẩn
RRF_K = 60

def _semantic_search(
    query: str,
    k: int,
    notebook_id: str,
    vector_store: VectorStoreManager
) -> List[Dict[str, Any]]:
    """Tìm kiếm ngữ nghĩa (Semantic vector search) qua Qdrant."""
    return vector_store.search(query=query, limit=k, notebook_id=notebook_id)

def _bm25_search(query: str, k: int, notebook_id: str) -> List[Dict[str, Any]]:
    """Tìm kiếm từ khóa (Keyword search) qua BM25 index."""
    bm25_index = get_bm25_index(notebook_id)

    if bm25_index.is_empty:
        logger.debug("BM25 index rỗng, bỏ qua tìm kiếm từ khóa.")
        return []

    results = bm25_index.search(query, top_k=k)

    # Chuyển đổi tuple (BM25Document, score) thành định dạng chuẩn Dict
    formatted_results = []
    for doc, score in results:
        formatted_results.append({
            "score": float(score),
            "content": doc.text,
            "metadata": doc.metadata
        })
    return formatted_results

def _reciprocal_rank_fusion(
    semantic_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """
    Kết hợp kết quả bằng Reciprocal Rank Fusion (RRF).
    RRF_score(d) = Σ 1 / (k + rank_i(d))
    """
    rrf_scores = {}
    chunk_map = {}

    def get_chunk_id(chunk):
        # Lấy chunk_id nếu có, không có thì băm nội dung để tạo ID
        return chunk["metadata"].get("chunk_id", hash(chunk["content"]))

    for rank, chunk in enumerate(semantic_results, start=1):
        cid = get_chunk_id(chunk)
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1.0 / (k + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    for rank, chunk in enumerate(bm25_results, start=1):
        cid = get_chunk_id(chunk)
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1.0 / (k + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    # Sắp xếp theo RRF score giảm dần
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    fused = []
    for cid in sorted_ids:
        chunk = chunk_map[cid].copy()
        chunk["score"] = rrf_scores[cid] # Ghi đè score cũ bằng RRF score
        fused.append(chunk)

    return fused

class HybridSearcher:
    """
    Hybrid Search: chạy song song 2 luồng (Semantic + Keyword), kết hợp bằng RRF.
    """
    def __init__(self, vector_store: VectorStoreManager):
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        k: int = 15,
        notebook_id: str = "default",
    ) -> List[Dict[str, Any]]:
        search_k = k or settings.hybrid_initial_k

        # Chạy song song 2 luồng tìm kiếm
        with ThreadPoolExecutor(max_workers=2) as executor:
            semantic_future = executor.submit(
                _semantic_search, query, search_k, notebook_id, self.vector_store
            )
            bm25_future = executor.submit(
                _bm25_search, query, settings.bm25_top_k, notebook_id
            )

            semantic_results = semantic_future.result()
            bm25_results = bm25_future.result()

        # Combine bằng RRF
        fused = _reciprocal_rank_fusion(semantic_results, bm25_results)
        
        return fused
