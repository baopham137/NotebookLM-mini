import os
from typing import List
from sentence_transformers import SentenceTransformer
from ..utils.config import settings

def _resolve_device(device_str: str) -> str:
    """Tự động phát hiện GPU nếu device='auto' và bảo vệ chống tràn VRAM."""
    if device_str == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                # Lấy tổng dung lượng VRAM của GPU 0 (tính bằng GB)
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                print(f"[DEBUG_VRAM] Detected VRAM: {vram_gb} GB")
                # Hạ ngưỡng an toàn xuống 3.5GB (để card 4GB gánh chung được Qwen3B + GreenNode)
                if vram_gb < 3.5:
                    return "cpu"
                return "cuda"
            
            # Hỗ trợ Apple Silicon Mac (M1/M2/M3/M4)
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
                
            return "cpu"
        except ImportError:
            return "cpu"
    return device_str

class LocalEmbedder:
    """Quản lý Embedding Model với khả năng tự động chọn Device theo Hardware Profiler."""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or getattr(settings, "embedding_model", "keepitreal/vietnamese-sbert")
        self.device = _resolve_device(settings.hf_device)
        
        print(f"[LocalEmbedder] Đang tải mô hình {self.model_name} lên thiết bị: {self.device} (Chế độ Offline)")
        
        # Load model using sentence-transformers, chặn hoàn toàn gọi mạng bằng local_files_only=True
        self.model = SentenceTransformer(self.model_name, device=self.device, local_files_only=True)
        
        # Nếu thiết bị là CPU và config cấu hình là int8_onnx, 
        # (Lưu ý: sentence-transformers không hỗ trợ export onnx trực tiếp dễ dàng,
        # Trong hệ thống thực tế, ta có thể dùng thư viện optimum để tải bản ONNX.
        # Ở đây ta sử dụng cấu hình CPU native của PyTorch đã được tối ưu hóa).
        if getattr(settings, "embedding_quantization", None) == "int8_onnx" and self.device == "cpu":
            print("[LocalEmbedder] Đang tối ưu hóa chạy CPU cho môi trường Tier 3/4...")

    def unload(self):
        """Xả mô hình khỏi bộ nhớ."""
        if hasattr(self, 'model'):
            del self.model
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

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
