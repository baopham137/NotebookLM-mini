import os
import json
import requests
import requests
import logging
from typing import Generator, Optional
from src.utils.config import settings
from src.utils.telemetry import trace_execution_generator

logger = logging.getLogger(__name__)

class LLMEngine:
    """
    LLM Engine sử dụng Cơ chế Gọi API tới llama.cpp server.
    Đã được thiết kế động theo cấu hình từ file .env
    """
    def __init__(self):
        self.llama_url = settings.llama_server_url

    @trace_execution_generator(event_name="chat_stream", module="llm_client")
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
                    ],
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )
                for chunk in response:
                    yield chunk.text
                return
            except Exception as e:
                logger.error(f"Lỗi Gemini API: {e}")
                yield f"Lỗi Gemini API: {e}. Đang fallback về Local Model..."
                
        # Gọi llama.cpp REST API (OpenAI format)
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": True
            }
            if settings.llm_provider == "ollama":
                payload["model"] = os.environ.get("RAG_OLLAMA_MODEL", "qwen2.5:3b")
            elif os.environ.get("RAG_OLLAMA_MODEL"):
                payload["model"] = os.environ.get("RAG_OLLAMA_MODEL")
            else:
                payload["model"] = "default"
            
            with requests.post(f"{self.llama_url}/v1/chat/completions", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                pass
                                
        except requests.exceptions.ConnectionError:
            error_msg = (
                f"⚠️ **Lỗi hệ thống: Không thể kết nối tới Llama.cpp tại {self.llama_url}!**\n\n"
                "Tiến trình llama-server chưa được khởi chạy đúng cách."
            )
            logger.error("Không thể kết nối Llama.cpp.")
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