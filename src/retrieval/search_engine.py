from typing import List, Dict, Any, Tuple
from ..ingestion.indexing import VectorStoreManager
from ..utils.config import settings
from .hybrid_search import HybridSearcher
from .compressor import get_compressor

class SearchEngine:
    """Công cụ truy xuất dữ liệu lai (Hybrid Search: Vector + Keyword)."""
    def __init__(self, vector_store: VectorStoreManager):
        self.vector_store = vector_store
        self.hybrid_searcher = HybridSearcher(vector_store)

    def retrieve(self, query: str, notebook_id: str, top_k: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Tìm kiếm các đoạn văn bản liên quan bằng Hybrid Search và định dạng chúng thành Context cho LLM.
        """
        results = self.hybrid_searcher.search(query, k=top_k, notebook_id=notebook_id)
        
        if not results:
            return "Không tìm thấy thông tin liên quan trong tài liệu.", []
            
        # Nén ngữ cảnh (Contextual Compression)
        compressor = get_compressor()
        compressed_results = compressor.compress(query, results)
        
        if not compressed_results:
            return "Không có thông tin nào đủ sát với câu hỏi trong tài liệu.", []

        context_parts = []
        for i, res in enumerate(compressed_results):
            content = res["content"]
            metadata = res["metadata"]
            source = metadata.get("source_file") or metadata.get("title") or metadata.get("source_url") or metadata.get("filename") or "Tài liệu"
            heading = metadata.get("heading_level_1", "")
            
            # Formatting the chunk for LLM
            context_parts.append(f"[Nguồn {i+1} - {source}]:\n{content}")
            
        return "\n\n---\n\n".join(context_parts), results
