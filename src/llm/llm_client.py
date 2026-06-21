import os
import json
import requests
import logging
from typing import Generator, Optional
from src.utils.config import settings

logger = logging.getLogger(__name__)

class LLMEngine:
    """
    LLM Engine sử dụng Cơ chế Gọi API tới Ollama Bridge.
    Đã được thiết kế động theo cấu hình từ file .env
    """
    def __init__(self):
        # Không tự đoán phần cứng nữa, đọc thẳng từ config đã được Host cấu hình
        self.ollama_url = settings.ollama_base_url
        # Default model cho Ollama
        self.model_tag = "qwen2.5:3b" if settings.use_reranker else "qwen2.5:0.5b"
        
        # Thử lấy tên model chính xác từ Ollama API nếu có thể
        try:
            tags = requests.get(f"{self.ollama_url}/api/tags", timeout=2).json()
            if "models" in tags and len(tags["models"]) > 0:
                # Lấy model đầu tiên làm mặc định (vì Host đã pull model tốt nhất)
                self.model_tag = tags["models"][0]["name"]
        except Exception:
            pass

    def generate(self, prompt: str, system_prompt: str = "", is_private: bool = True, gemini_api_key: Optional[str] = None) -> Generator[str, None, None]:
        """Tạo phản hồi dạng Stream (nhả từng chữ)."""
        if not is_private and gemini_api_key:
            from google import genai
            from google.genai import types
            try:
                client = genai.Client(api_key=gemini_api_key)
                response = client.models.generate_content_stream(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Content(role="user", parts=[types.Part.from_text(text=system_prompt + "\n\n" + prompt)])
                    ]
                )
                for chunk in response:
                    yield chunk.text
                return
            except Exception as e:
                logger.error(f"Lỗi Gemini API: {e}")
                yield f"Lỗi Gemini API: {e}. Đang fallback về Local Model..."
                
        # Gọi Ollama REST API qua Bridge
        try:
            payload = {
                "model": self.model_tag,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": True
            }
            
            with requests.post(f"{self.ollama_url}/api/chat", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk_data = json.loads(line)
                        if "message" in chunk_data and "content" in chunk_data["message"]:
                            yield chunk_data["message"]["content"]
                            
        except requests.exceptions.ConnectionError:
            error_msg = (
                f"⚠️ **Lỗi hệ thống: Không thể kết nối tới Ollama tại {self.ollama_url}!**\n\n"
                "Hệ thống LLM trên Windows (Host) chưa sẵn sàng hoặc cổng 11434 bị chặn."
            )
            logger.error("Không thể kết nối Ollama.")
            yield error_msg
            
        except Exception as e:
            logger.error(f"Lỗi không xác định khi gọi Local LLM: {e}")
            yield "Đã có lỗi xảy ra trong quá trình sinh văn bản từ AI nội bộ."

    def build_rag_prompt(self, query: str, context: str, history: list = None) -> str:
        """Tạo Prompt hoàn chỉnh cho RAG có bao gồm Lịch sử Chat."""
        prompt = (
            f"Bạn là trợ lý AI chuyên nghiệp tên là NotebookLM Mini. Dưới đây là các thông tin tôi tìm thấy trong tài liệu của bạn:\n"
            f"====================\n{context}\n====================\n\n"
        )
        
        if history and len(history) > 0:
            prompt += "Đây là lịch sử trò chuyện gần đây (để làm ngữ cảnh):\n"
            for msg in history[-5:]: # Chỉ lấy 5 tin nhắn gần nhất
                role = "User" if msg['role'] == 'user' else "AI"
                prompt += f"{role}: {msg['content']}\n"
            prompt += "\n"
            
        prompt += (
            f"Dựa KHÔNG CHỈ vào trí nhớ mà HÃY DỰA VÀO thông tin trên và ngữ cảnh trò chuyện, hãy trả lời câu hỏi sau một cách chi tiết và chính xác nhất. Nếu tài liệu không có thông tin, hãy nói rõ là tài liệu không đề cập.\n"
            f"Câu hỏi mới: {query}"
        )
        return prompt