import os
import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from ..utils.config import settings

class VectorStoreManager:
    """Quản lý việc lưu trữ Vector vào Qdrant Local."""
    
    def __init__(self):
        
        # Tạo thư mục chứa database nếu chưa có
        os.makedirs(settings.storage_dir, exist_ok=True)
        
        # Khởi tạo Qdrant Local Mode (Ghi trực tiếp ra ổ cứng, không cần Docker)
        self.client = QdrantClient(path=str(settings.storage_dir))
        self.collection_name = settings.qdrant_collection
        
        # Test 1 embedding để lấy vector size
        from src.utils.vram_orchestrator import get_orchestrator
        embedder = get_orchestrator().get_embedder()
        dummy_vector = embedder.embed_query("test")
        self.vector_size = len(dummy_vector)
        
        self._init_collection()

    def _init_collection(self):
        """Tạo collection nếu chưa tồn tại."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            print(f"[Qdrant] Đang tạo Collection mới: {self.collection_name} (Size: {self.vector_size})")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
        else:
            print(f"[Qdrant] Đã kết nối tới Collection: {self.collection_name}")

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """Nhúng và lưu các đoạn văn bản vào Database."""
        if not chunks:
            return
            
        print(f"[Qdrant] Đang tính toán Vector cho {len(chunks)} đoạn văn bản...")
        from src.utils.vram_orchestrator import get_orchestrator
        embedder = get_orchestrator().get_embedder()
        texts = [chunk["content"] for chunk in chunks]
        embeddings = embedder.embed_documents(texts)
        
        points = []
        for i, chunk in enumerate(chunks):
            point = PointStruct(
                id=str(uuid.uuid4()), # Sinh ID duy nhất
                vector=embeddings[i],
                payload={
                    "content": chunk["content"],
                    **chunk["metadata"] # Gắn kèm siêu dữ liệu (Metadata)
                }
            )
            points.append(point)
            
        print(f"[Qdrant] Đang lưu {len(points)} Vectors vào Database...")
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print("[Qdrant] Lưu dữ liệu hoàn tất!")

    def delete_notebook_chunks(self, notebook_id: str):
        """Xóa tất cả các chunk thuộc về một notebook."""
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="notebook_id",
                        match=MatchValue(value=notebook_id)
                    )
                ]
            )
        )

    def delete_document_chunks(self, notebook_id: str, filename: str):
        """Xóa tất cả các chunk thuộc về một tài liệu trong notebook."""
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue, FilterSelector
        # Qdrant delete bằng filter
        # Chúng ta xóa các chunk có notebook_id = notebook_id VÀ (source_file = filename HOẶC title = filename HOẶC source_url = filename)
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(key="notebook_id", match=MatchValue(value=notebook_id))
                ],
                should=[
                    FieldCondition(key="source_file", match=MatchValue(value=filename)),
                    FieldCondition(key="title", match=MatchValue(value=filename)),
                    FieldCondition(key="source_url", match=MatchValue(value=filename))
                ]
            )
        )

    def search(self, query: str, limit: int = 5, notebook_id: str = None) -> List[Dict[str, Any]]:
        """Tìm kiếm dữ liệu tương tự."""
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        from src.utils.vram_orchestrator import get_orchestrator
        embedder = get_orchestrator().get_embedder()
        
        query_vector = embedder.embed_query(query)
        
        query_filter = None
        if notebook_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="notebook_id",
                        match=MatchValue(value=notebook_id)
                    )
                ]
            )
        
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        hits = res.points
        
        results = []
        for hit in hits:
            results.append({
                "score": hit.score,
                "content": hit.payload.get("content", ""),
                "metadata": {k: v for k, v in hit.payload.items() if k != "content"}
            })
        return results
