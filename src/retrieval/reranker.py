"""
Cross-Encoder Reranker — Tầng Truy xuất
Sử dụng mô hình Cross-Encoder để chấm điểm lại các chunks.
"""
import logging
from typing import List, Dict, Any, Optional
from functools import lru_cache

from ..utils.config import settings

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def load_cross_encoder():
    """Lazy-load the Cross-Encoder model."""
    try:
        from sentence_transformers import CrossEncoder
        import torch
    except ImportError:
        logger.warning("Không tìm thấy thư viện sentence-transformers hoặc torch. Bỏ qua Reranker.")
        return None

    model_name = settings.reranker_model
    if settings.low_vram_mode:
        model_name = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    
    # Tự động phát hiện GPU và bảo vệ VRAM
    device = settings.hf_device
    if device == "auto":
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            # Hạ ngưỡng an toàn xuống 3.5GB để Reranker có thể dùng chung GPU 4GB với Qwen
            device = "cuda" if vram_gb > 3.5 else "cpu"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        
    logger.info(f"Loading Cross-Encoder model: {model_name} on {device}...")
    try:
        model = CrossEncoder(
            model_name,
            device=device,
            model_kwargs={"torch_dtype": torch.float16 if device != "cpu" else torch.float32}
        )
        logger.info("Cross-Encoder loaded successfully.")
        return model
    except Exception as exc:
        logger.error(f"Failed to load Cross-Encoder: {exc}")
        return None

class CrossEncoderReranker:
    """
    Cross-Encoder Reranker.
    Nhận N chunks thô → tính điểm tương quan chéo → lọc sạch giữ lại top-K chunks.
    """

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rerank chunks using Cross-Encoder.
        """
        rerank_k = top_k or settings.hybrid_rerank_k

        if not chunks:
            return []

        # Nếu số lượng chunk ít hơn top_k, không cần rerank
        if len(chunks) <= rerank_k:
            return chunks

        model = load_cross_encoder()
        if model is None:
            logger.warning("Cross-Encoder unavailable. Trả về top chunks mặc định.")
            # Sort by existing score just in case
            sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0), reverse=True)
            return sorted_chunks[:rerank_k]

        # Chuẩn bị cặp (query, chunk_text)
        pairs = [[query, chunk["content"]] for chunk in chunks]
        
        # Dự đoán điểm
        scores = model.predict(pairs)

        # Cập nhật điểm mới và sắp xếp
        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            new_chunk = chunk.copy()
            new_chunk["score"] = float(score)
            scored_chunks.append(new_chunk)

        scored_chunks.sort(key=lambda c: c["score"], reverse=True)

        return scored_chunks[:rerank_k]
