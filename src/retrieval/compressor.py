import logging
import re
from typing import List, Dict, Any

from .reranker import _load_cross_encoder

logger = logging.getLogger(__name__)

class ContextualCompressor:
    """
    Contextual Compression: Extract only relevant sentences from retrieved chunks
    to avoid LLM distraction (Lost in the middle) and reduce token usage.
    """
    def __init__(self, threshold: float = -2.0): 
        # Threshold depends on the cross-encoder model. 
        # mmarco-mMiniLM usually has scores from -10 to 10. -2.0 is a safe threshold for "some relevance".
        self.threshold = threshold
        
    def _split_into_sentences(self, text: str) -> List[str]:
        # Tách câu cơ bản dựa trên dấu câu tiếng Việt/Anh
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Bỏ qua các câu quá ngắn (vd: "Yes.", "1.")
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def compress(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Nén từng chunk bằng cách lọc bỏ các câu văn không liên quan đến câu hỏi.
        """
        if not chunks:
            return []
            
        model = _load_cross_encoder()
        if model is None:
            logger.warning("Cross-Encoder unavailable. Bỏ qua bước Compression.")
            return chunks
            
        compressed_chunks = []
        for chunk in chunks:
            text = chunk["content"]
            sentences = self._split_into_sentences(text)
            
            if not sentences:
                compressed_chunks.append(chunk) # Nếu không tách được câu, giữ nguyên
                continue
                
            # Tạo các cặp (Câu hỏi, Câu văn) để chấm điểm
            pairs = [[query, s] for s in sentences]
            try:
                scores = model.predict(pairs)
            except Exception as e:
                logger.error(f"Compression prediction failed: {e}")
                compressed_chunks.append(chunk)
                continue
            
            # Lọc các câu văn có điểm số >= threshold
            relevant_sentences = []
            for s, score in zip(sentences, scores):
                if float(score) >= self.threshold:
                    relevant_sentences.append(s)
                    
            # Chỉ giữ lại chunk nếu còn ít nhất 1 câu liên quan
            if relevant_sentences:
                new_chunk = chunk.copy()
                new_chunk["content"] = " ".join(relevant_sentences)
                compressed_chunks.append(new_chunk)
                
        logger.info(f"Compression: Nén từ {len(chunks)} chunks nguyên bản xuống {len(compressed_chunks)} chunks cô đặc.")
        return compressed_chunks

# Module-level singleton
_compressor = None

def get_compressor() -> ContextualCompressor:
    global _compressor
    if _compressor is None:
        _compressor = ContextualCompressor()
    return _compressor
