import os
import re
import tempfile
import logging
from typing import Optional
from markitdown import MarkItDown

from ..document_tree import DocumentNode
from .markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)

class MarkItDownParser:
    """Sử dụng thư viện MarkItDown (Microsoft) để parse PDF, Office, Excel, v.v. thành Document Tree."""
    
    def __init__(self):
        self.md_parser = MarkdownParser()
        self.markitdown = MarkItDown()

    def parse(self, file_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
            
        # 1. Parse tệp thô thành Markdown string thông qua MarkItDown
        try:
            result = self.markitdown.convert(file_path)
            raw_markdown = result.text_content
        except Exception as e:
            raise RuntimeError(f"Lỗi khi MarkItDown xử lý file {file_path}: {str(e)}")

        # 2. Hậu xử lý: Nếu là PDF, trích xuất ảnh và dùng LLaVA phân tích
        if file_path.lower().endswith('.pdf'):
            raw_markdown = self._enrich_images_from_pdf(file_path, raw_markdown)
            
        # 3. Hậu xử lý cho các file khác (DOCX, PPTX, XLSX, HTML): 
        # MarkItDown thường nhúng ảnh dưới dạng Base64 (data:image/png;base64,...)
        raw_markdown = self._enrich_base64_images(raw_markdown)

        # 4. Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(file_path)
        meta["parser"] = "MarkItDownParser"

        # 4. Chuyển chuỗi Markdown thô thành Cây phân cấp (Document Tree)
        document_tree = self.md_parser.parse(raw_markdown, source_metadata=meta)
        
        return document_tree

    def _enrich_images_from_pdf(self, pdf_path: str, markdown_text: str) -> str:
        """Trích xuất ảnh từ PDF bằng PyMuPDF, gọi LLaVA phân tích, thay thế tại chỗ vào Markdown."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("[MarkItDownParser] PyMuPDF chưa được cài. Bỏ qua bước phân tích ảnh trong PDF.")
            return markdown_text

        # Tìm tất cả dòng ảnh trong Markdown
        image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        image_matches = list(image_pattern.finditer(markdown_text))
        
        if not image_matches:
            logger.info("[MarkItDownParser] PDF không chứa ảnh nào. Bỏ qua.")
            return markdown_text

        # Trích xuất ảnh vật lý từ PDF
        temp_dir = tempfile.mkdtemp(prefix="pdf_images_")
        extracted_images = []
        
        try:
            doc = fitz.open(pdf_path)
            img_index = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                for img_info in image_list:
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        img_filename = f"pdf_img_{img_index}.{image_ext}"
                        img_path = os.path.join(temp_dir, img_filename)
                        
                        with open(img_path, "wb") as f:
                            f.write(image_bytes)
                        
                        extracted_images.append({
                            "path": img_path,
                            "page": page_num + 1,
                            "index": img_index
                        })
                        img_index += 1
                    except Exception as e:
                        logger.warning(f"[MarkItDownParser] Không thể trích xuất ảnh xref={xref}: {e}")
            doc.close()
        except Exception as e:
            logger.error(f"[MarkItDownParser] Lỗi khi mở PDF bằng PyMuPDF: {e}")
            return markdown_text

        if not extracted_images:
            logger.info("[MarkItDownParser] PyMuPDF không tìm thấy ảnh nhúng nào trong PDF.")
            return markdown_text

        # Khởi tạo ImageParser để gọi LLaVA
        try:
            from .image_parser import ImageParser
            img_parser = ImageParser()
        except Exception as e:
            logger.error(f"[MarkItDownParser] Không thể khởi tạo ImageParser: {e}")
            return markdown_text

        # Ghép nối: Mỗi dòng ![alt](image) trong Markdown tương ứng với 1 ảnh trích xuất
        # Thay thế theo thứ tự từ cuối lên đầu để không làm lệch vị trí (offset)
        enriched_markdown = markdown_text
        num_replacements = min(len(image_matches), len(extracted_images))

        for i in range(num_replacements - 1, -1, -1):
            match = image_matches[i]
            img_info = extracted_images[i]
            
            # Gọi LLaVA phân tích ảnh
            description = img_parser._describe_with_ollama(img_info["path"])
            
            if description:
                alt_text = match.group(1) or "Hình ảnh"
                replacement = f"[Mô tả hình ảnh - {alt_text} (Trang {img_info['page']})]: {description}"
                enriched_markdown = (
                    enriched_markdown[:match.start()] + 
                    replacement + 
                    enriched_markdown[match.end():]
                )
                logger.info(f"[MarkItDownParser] Đã phân tích ảnh {i+1}/{num_replacements} bằng LLaVA.")
            else:
                logger.warning(f"[MarkItDownParser] LLaVA không thể phân tích ảnh {i+1}. Giữ nguyên dòng gốc.")

        # Dọn dẹp thư mục tạm
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

        return enriched_markdown

    def _enrich_base64_images(self, markdown_text: str) -> str:
        """Trích xuất ảnh Base64 (từ DOCX, PPTX), lưu tạm, gọi LLaVA phân tích, thay thế tại chỗ."""
        import base64
        
        # Biểu thức chính quy tìm ![alt](data:image/png;base64,...)
        image_pattern = re.compile(r'!\[([^\]]*)\]\(data:image/([^;]+);base64,([^)]+)\)')
        image_matches = list(image_pattern.finditer(markdown_text))
        
        if not image_matches:
            return markdown_text
            
        logger.info(f"[MarkItDownParser] Tìm thấy {len(image_matches)} ảnh Base64 nhúng. Đang xử lý bằng LLaVA...")
        
        try:
            from .image_parser import ImageParser
            img_parser = ImageParser()
        except Exception as e:
            logger.error(f"[MarkItDownParser] Không thể khởi tạo ImageParser: {e}")
            return markdown_text

        temp_dir = tempfile.mkdtemp(prefix="base64_images_")
        enriched_markdown = markdown_text
        
        # Xử lý từ cuối lên đầu để không làm lệch index thay thế
        for i in range(len(image_matches) - 1, -1, -1):
            match = image_matches[i]
            alt_text = match.group(1) or "Hình ảnh"
            img_ext = match.group(2)
            b64_data = match.group(3)
            
            try:
                # Giải mã Base64
                img_bytes = base64.b64decode(b64_data)
                img_filename = f"img_{i}.{img_ext}"
                img_path = os.path.join(temp_dir, img_filename)
                
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                    
                # Gọi LLaVA phân tích ảnh
                description = img_parser._describe_with_ollama(img_path)
                
                if description:
                    replacement = f"[Mô tả hình ảnh - {alt_text}]: {description}"
                    enriched_markdown = (
                        enriched_markdown[:match.start()] + 
                        replacement + 
                        enriched_markdown[match.end():]
                    )
                    logger.info(f"[MarkItDownParser] Đã phân tích ảnh Base64 {i+1}/{len(image_matches)} bằng LLaVA.")
                else:
                    logger.warning(f"[MarkItDownParser] LLaVA không thể phân tích ảnh Base64 {i+1}. Giữ nguyên dòng gốc.")
                    
            except Exception as e:
                logger.error(f"[MarkItDownParser] Lỗi khi xử lý ảnh Base64 {i+1}: {e}")
                
        # Dọn dẹp thư mục tạm
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
            
        return enriched_markdown
