from typing import List
from sentence_transformers import SentenceTransformer
from ..utils.config import settings

class LocalEmbedder:
    """Quản lý Embedding Model với khả năng tự động chọn Device theo Hardware Profiler."""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or getattr(settings, "embedding_model", "keepitreal/vietnamese-sbert")
        self.device = settings.hf_device if settings.hf_device != "auto" else None
        
        print(f"[LocalEmbedder] Đang tải mô hình {self.model_name} lên thiết bị: {self.device}")
        
        # Load model using sentence-transformers
        self.model = SentenceTransformer(self.model_name, device=self.device)
        
        # Nếu thiết bị là CPU và config cấu hình là int8_onnx, 
        # (Lưu ý: sentence-transformers không hỗ trợ export onnx trực tiếp dễ dàng,
        # Trong hệ thống thực tế, ta có thể dùng thư viện optimum để tải bản ONNX.
        # Ở đây ta sử dụng cấu hình CPU native của PyTorch đã được tối ưu hóa).
        if getattr(settings, "embedding_quantization", None) == "int8_onnx" and self.device == "cpu":
            print("[LocalEmbedder] Đang tối ưu hóa chạy CPU cho môi trường Tier 3/4...")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Nhúng danh sách các đoạn văn bản (Dùng cho Ingestion)."""
        if not texts:
            return []
        # Chuyển thành numpy array rồi tolist() để trả về list float tiêu chuẩn
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Nhúng một câu truy vấn duy nhất (Dùng cho Retrieval)."""
        embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()
