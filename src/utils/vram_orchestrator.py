"""
VRAM Orchestrator - Nhạc trưởng Quản lý Bộ nhớ AI
===================================================
Quản lý vòng đời (nạp/xả) của tất cả model Python nặng để đảm bảo
tại bất kỳ thời điểm nào, chỉ có 1 model nặng chiếm bộ nhớ.

Nguyên tắc vàng: NẠP KHI CẦN, XẢ KHI XONG.
"""

import gc
import threading
import logging

logger = logging.getLogger(__name__)


class VRAMOrchestrator:
    """
    Singleton quản lý tập trung tất cả model AI nặng trong hệ thống.
    
    Các model được quản lý:
    - Embedding (~2GB RAM): GreenNode hoặc sBERT
    - Reranker (~2GB RAM): BAAI BGE hoặc mMiniLM
    - Whisper (~1-2GB RAM): Base/Small/Medium
    
    Các model KHÔNG quản lý (do Ollama/llama-server tự lo):
    - LLM (Qwen): Ollama tự nạp/xả
    - Vision (Moondream): Ollama tự nạp/xả
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton: Chỉ có 1 instance duy nhất trong toàn bộ ứng dụng."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Theo dõi các model đang được nạp
        self._embedder = None
        self._reranker = None
        self._whisper_model = None
        self._whisper_size = None
        
        # Lock cho thread-safety
        self._model_lock = threading.Lock()
        
        logger.info("[Orchestrator] Khởi tạo VRAM Orchestrator thành công.")
    
    def _free_memory(self):
        """Giải phóng bộ nhớ Python và GPU cache."""
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
    
    def _unload_embedder(self):
        """Xả Embedding model khỏi bộ nhớ."""
        if self._embedder is not None:
            logger.info("[Orchestrator] 🔻 Đang xả Embedding model khỏi bộ nhớ...")
            self._embedder = None
            self._free_memory()
            logger.info("[Orchestrator] ✅ Đã xả Embedding model.")
    
    def _unload_reranker(self):
        """Xả Reranker model khỏi bộ nhớ."""
        if self._reranker is not None:
            logger.info("[Orchestrator] 🔻 Đang xả Reranker model khỏi bộ nhớ...")
            self._reranker = None
            self._free_memory()
            logger.info("[Orchestrator] ✅ Đã xả Reranker model.")
    
    def _unload_whisper(self):
        """Xả Whisper model khỏi bộ nhớ."""
        if self._whisper_model is not None:
            logger.info("[Orchestrator] 🔻 Đang xả Whisper model khỏi bộ nhớ...")
            try:
                del self._whisper_model
            except Exception as e:
                logger.warning(f"[Orchestrator] Lỗi khi xả Whisper: {e}")
            self._whisper_model = None
            self._free_memory()
            logger.info("[Orchestrator] ✅ Đã xả Whisper model.")
    
    def _unload_all_except(self, keep: str = None):
        """Xả tất cả model trừ model được chỉ định."""
        if keep != "embedder":
            self._unload_embedder()
        if keep != "reranker":
            self._unload_reranker()
        if keep != "whisper":
            self._unload_whisper()
    
    # ===========================
    # PUBLIC API: Nạp model
    # ===========================
    
    def get_embedder(self):
        """
        Nạp Embedding model. Tự động xả các model khác trước khi nạp.
        Trả về instance LocalEmbedder đã sẵn sàng sử dụng.
        """
        with self._model_lock:
            if self._embedder is not None:
                return self._embedder
            
            # Xả các model khác để nhường bộ nhớ
            self._unload_all_except(keep="embedder")
            
            logger.info("[Orchestrator] 🔺 Đang nạp Embedding model...")
            from src.ingestion.embedding import LocalEmbedder
            self._embedder = LocalEmbedder()
            logger.info("[Orchestrator] ✅ Embedding model đã sẵn sàng.")
            return self._embedder
    
    def get_reranker(self):
        """
        Nạp Reranker model. Tự động xả các model khác trước khi nạp.
        Trả về instance CrossEncoder đã sẵn sàng sử dụng.
        """
        with self._model_lock:
            if self._reranker is not None:
                return self._reranker
            
            # Xả các model khác để nhường bộ nhớ
            self._unload_all_except(keep="reranker")
            
            logger.info("[Orchestrator] 🔺 Đang nạp Reranker model...")
            from src.retrieval.reranker import load_cross_encoder
            self._reranker = load_cross_encoder()
            if self._reranker:
                logger.info("[Orchestrator] ✅ Reranker model đã sẵn sàng.")
            else:
                logger.warning("[Orchestrator] ⚠️ Không thể nạp Reranker model.")
            return self._reranker
    
    def get_whisper(self, model_size: str = "base"):
        """
        Nạp Whisper model. Tự động xả các model khác trước khi nạp.
        Trả về instance Whisper model đã sẵn sàng sử dụng.
        """
        with self._model_lock:
            # Nếu đã nạp đúng size thì dùng lại
            if self._whisper_model is not None and self._whisper_size == model_size:
                return self._whisper_model
            
            # Xả các model khác để nhường bộ nhớ
            self._unload_all_except(keep="whisper")
            
            # Nếu đang giữ whisper khác size thì xả luôn
            if self._whisper_model is not None and self._whisper_size != model_size:
                self._unload_whisper()
            
            logger.info(f"[Orchestrator] 🔺 Đang nạp Whisper model ({model_size})...")
            import warnings
            import os
            try:
                import whisper
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    cache_dir = os.path.join(os.getcwd(), "cache", "whisper")
                    os.makedirs(cache_dir, exist_ok=True)
                    self._whisper_model = whisper.load_model(model_size, download_root=cache_dir)
                    self._whisper_size = model_size
                    logger.info(f"[Orchestrator] ✅ Whisper model ({model_size}) đã sẵn sàng.")
            except Exception as e:
                logger.error(f"[Orchestrator] ❌ Lỗi khi nạp Whisper: {e}")
                self._whisper_model = None
            
            return self._whisper_model
    
    # ===========================
    # PUBLIC API: Xả model
    # ===========================
    
    def release_embedder(self):
        """Xả Embedding model sau khi dùng xong. Gọi hàm này khi không cần embed nữa."""
        with self._model_lock:
            self._unload_embedder()
    
    def release_reranker(self):
        """Xả Reranker model sau khi dùng xong."""
        with self._model_lock:
            self._unload_reranker()
    
    def release_whisper(self):
        """Xả Whisper model sau khi dùng xong."""
        with self._model_lock:
            self._unload_whisper()
    
    def release_all(self):
        """Xả toàn bộ model. Dùng khi shutdown hoặc cần giải phóng bộ nhớ khẩn cấp."""
        with self._model_lock:
            self._unload_all_except(keep=None)
            logger.info("[Orchestrator] 🧹 Đã xả toàn bộ model khỏi bộ nhớ.")
    
    def status(self) -> dict:
        """Trả về trạng thái hiện tại của các model."""
        return {
            "embedder_loaded": self._embedder is not None,
            "reranker_loaded": self._reranker is not None,
            "whisper_loaded": self._whisper_model is not None,
            "whisper_size": self._whisper_size,
        }


# Module-level singleton
_orchestrator = None

def get_orchestrator() -> VRAMOrchestrator:
    """Lấy instance singleton của VRAM Orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VRAMOrchestrator()
    return _orchestrator
