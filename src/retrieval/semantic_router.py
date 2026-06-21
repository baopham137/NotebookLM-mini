import logging
from typing import Literal

logger = logging.getLogger(__name__)

IntentType = Literal["chitchat", "factoid", "summarize"]

class SemanticRouter:
    """
    Intelligent Query Router using fast heuristics + regex for Chitchat/Summary detection,
    falling back to Factoid for detailed questions.
    This avoids adding 1-2 seconds of LLM overhead just for routing.
    """
    
    def __init__(self):
        # Very lightweight keyword-based detection
        self.chitchat_keywords = [
            "xin chào", "hello", "hi", "chào", "bạn là ai", "bạn làm được gì",
            "tên bạn là gì", "cảm ơn", "tạm biệt", "bye", "ok", "tuyệt", "giỏi",
            "hello bot", "hi bot", "chào bot"
        ]
        self.summarize_keywords = [
            "tóm tắt", "tổng hợp", "nội dung chính", "chủ đề chính", 
            "khái quát", "ý chính", "summarize", "summary", "tóm lược"
        ]
        
    def route(self, query: str) -> IntentType:
        """Phân loại ý định người dùng."""
        q_lower = query.lower().strip()
        
        # 1. Chitchat check (ngắn và chứa từ khóa giao tiếp)
        if len(q_lower.split()) <= 6:
            # Nếu câu quá ngắn và nằm hoàn toàn trong tập keywords
            for kw in self.chitchat_keywords:
                if q_lower == kw or q_lower.startswith(kw):
                    logger.info(f"Router: Phân loại '{query}' -> CHITCHAT")
                    return "chitchat"
                    
        # 2. Summarize check
        for kw in self.summarize_keywords:
            if kw in q_lower:
                logger.info(f"Router: Phân loại '{query}' -> SUMMARIZE")
                return "summarize"
                
        # 3. Mặc định là Factoid (Hỏi đáp cần RAG)
        logger.info(f"Router: Phân loại '{query}' -> FACTOID")
        return "factoid"

# Module-level singleton
_semantic_router = None

def get_semantic_router() -> SemanticRouter:
    global _semantic_router
    if _semantic_router is None:
        _semantic_router = SemanticRouter()
    return _semantic_router
