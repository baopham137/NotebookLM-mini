import os
import base64
import requests
import json
from typing import Optional
from PIL import Image

from ..document_tree import DocumentNode, ImageNode, ParagraphNode

class ImageParser:
    """Parser xử lý hình ảnh sử dụng Vision Model qua Ollama API và OCR (Tesseract) fallback."""

    def __init__(self, ollama_url: str = "http://localhost:11434", vision_model: str = "moondream"):
        self.ollama_url = ollama_url
        self.vision_model = vision_model
        
        from ...utils.config import settings
        self.vision_mode = settings.vision_mode
        if settings.vision_model:
            self.vision_model = settings.vision_model

    def _image_to_base64(self, image_path: str) -> str:
        """Chuyển đổi file ảnh sang chuỗi Base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _describe_with_ollama(self, image_path: str) -> Optional[str]:
        """Gửi ảnh tới Ollama API nội bộ (localhost) để mô tả. Không cần internet."""
        try:
            # 0. Kiểm tra xem model đã được tải chưa (Lazy loading)
            try:
                tags_resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if tags_resp.status_code == 200:
                    models = [m.get("name", "") for m in tags_resp.json().get("models", [])]
                    # Ollama model names might have tags like moondream:latest
                    if not any(self.vision_model in m for m in models):
                        print(f"[ImageParser] Lần đầu tiên đọc ảnh. Đang tự động tải model {self.vision_model} từ internet...")
                        import subprocess
                        subprocess.run(["ollama", "pull", self.vision_model], check=True)
                        print(f"[ImageParser] Đã tải xong {self.vision_model}!")
            except Exception as e:
                print(f"[ImageParser] Cảnh báo khi kiểm tra model Ollama: {e}")

            # Mã hóa ảnh sang Base64
            img_base64 = self._image_to_base64(image_path)
            
            # Tạo payload gửi tới Ollama
            payload = {
                "model": self.vision_model,
                "prompt": "Describe this image in detail. Extract and transcribe any text visible in the image. If there are charts or diagrams, describe their content and data.",
                "images": [img_base64],
                "stream": False
            }
            
            print(f"[ImageParser] Đang gửi ảnh tới Ollama ({self.vision_model})...")
            
            # Gọi API nội bộ (localhost:11434) - KHÔNG CẦN INTERNET
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=120  # Timeout 2 phút cho ảnh phức tạp
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "").strip()
                if description:
                    print(f"[ImageParser] Ollama đã phân tích ảnh thành công ({len(description)} ký tự)")
                    return description
                else:
                    print("[ImageParser] Ollama trả về kết quả rỗng.")
                    return None
            else:
                print(f"[ImageParser] Ollama trả về lỗi HTTP {response.status_code}: {response.text[:200]}")
                return None
                
        except requests.exceptions.ConnectionError:
            print("[ImageParser] Không thể kết nối tới Ollama (localhost:11434). Ollama có đang chạy không?")
            return None
        except Exception as e:
            print(f"[ImageParser] Lỗi khi gọi Ollama API: {e}")
            return None

    def _extract_text_with_ocr(self, image_path: str) -> Optional[str]:
        """Sử dụng Tesseract OCR để trích xuất chữ (Fallback)."""
        try:
            import pytesseract
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='vie+eng')
            return text.strip()
        except Exception as e:
            print(f"[ImageParser] Lỗi OCR (Tesseract): {e}")
            return None

    def parse(self, image_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_path}")

        # Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(image_path)
        meta["parser"] = "ImageParser"

        # 1. Thử dùng Ollama Vision API (Ưu tiên - nhẹ nhàng, không chiếm VRAM của Python)
        description = None
        if self.vision_mode == "ollama":
            print(f"[ImageParser] Đang phân tích ảnh bằng Ollama Vision ({self.vision_model}): {os.path.basename(image_path)}")
            description = self._describe_with_ollama(image_path)
        
        # 2. Nếu thất bại hoặc dùng chế độ OCR -> Fallback sang Tesseract
        if not description:
            print("[ImageParser] Chuyển sang OCR Fallback (Tesseract)...")
            description = self._extract_text_with_ocr(image_path)
            if description:
                description = "OCR Trích xuất văn bản:\n" + description

        if not description:
            description = "[Không thể phân tích ảnh hoặc ảnh không có nội dung văn bản]"

        # Khởi tạo Document Tree
        doc_node = DocumentNode(metadata=meta)
        
        # Tạo ImageNode (có chứa text mô tả)
        img_node = ImageNode(
            alt_text=os.path.basename(image_path),
            url=f"file://{os.path.abspath(image_path)}",
            description=description,
            metadata={"description_source": "ollama" if "OCR" not in description else "ocr"}
        )
        
        # Đưa đoạn văn bản vào dưới ImageNode để Chunking xử lý dễ hơn
        img_node.add_child(ParagraphNode(content=description))
        
        doc_node.add_child(img_node)
        
        return doc_node
