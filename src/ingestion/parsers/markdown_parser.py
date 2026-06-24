import re
from typing import List, Optional
from ..document_tree import DocumentNode, HeadingNode, ParagraphNode, CodeBlockNode, Node

class MarkdownParser:
    """Phân tích chuỗi Markdown thô thành Cây Tài Liệu (Document Tree)."""
    
    def _preprocess_pseudo_headings(self, text: str) -> str:
        lines = text.split('\n')
        processed = []
        for line in lines:
            stripped = line.strip()
            
            # 1. Bắt đầu bằng số La Mã in đậm: **II BÀI TẬP...**
            if re.match(r'^\*\*\\?[IVXLCDM]+\.?\s+.*\*\*$', stripped, re.IGNORECASE):
                clean_text = stripped.replace('**', '').replace('\\*', '*').strip()
                processed.append(f"## {clean_text}")
                continue
            
            # 2. Bắt đầu bằng **Câu x:**
            if re.match(r'^\*\*Câu\s+\d+[:\.\-]?.*\*\*$', stripped, re.IGNORECASE):
                clean_text = stripped.replace('**', '').replace('\\*', '*').strip()
                processed.append(f"### {clean_text}")
                continue
            
            # 3. Bắt đầu bằng số thứ tự và in đậm: 1. **LÝ THUYẾT...**
            if re.match(r'^\d+\.\s+\*\*.*\*\*$', stripped):
                clean_text = stripped.replace('**', '').replace('\\*', '*').strip()
                processed.append(f"## {clean_text}")
                continue
                
            # 4. In đậm và viết hoa phần lớn (VD: **\* DẠNG BÀI TẬP...**)
            if re.match(r'^\*\*.*\*\*$', stripped):
                inner_text = stripped.replace('**', '').replace('\\*', '*').strip()
                if len(inner_text) > 3:
                    letters = [c for c in inner_text if c.isalpha()]
                    if letters:
                        upper_count = sum(1 for c in letters if c.isupper())
                        if upper_count / len(letters) > 0.7:  # >70% là chữ in hoa
                            processed.append(f"## {inner_text}")
                            continue

            processed.append(line)
        return '\n'.join(processed)

    def parse(self, markdown_text: str, source_metadata: dict = None) -> DocumentNode:
        root = DocumentNode(metadata=source_metadata or {})
        
        # Tiền xử lý các heading giả (pseudo-headings)
        markdown_text = self._preprocess_pseudo_headings(markdown_text)
        
        # Một regex đơn giản để tách Markdown thành các block
        # Tìm các heading (# Heading)
        blocks = re.split(r'(?m)^(#+ .*)$', markdown_text)
        
        current_parent: Node = root
        heading_stack: List[HeadingNode] = []
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
                
            # Kiểm tra xem block có phải là heading không
            heading_match = re.match(r'^(#+)\s+(.*)$', block)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_node = HeadingNode(level=level, content=title)
                
                # Quản lý cấu trúc phân cấp (Hierarchical Tree)
                # Tìm parent phù hợp dựa vào level
                while heading_stack and heading_stack[-1].level >= level:
                    heading_stack.pop()
                    
                if heading_stack:
                    heading_stack[-1].add_child(heading_node)
                else:
                    root.add_child(heading_node)
                    
                heading_stack.append(heading_node)
                current_parent = heading_node
            else:
                # Nếu không phải heading, nó có thể là paragraph hoặc code block
                if block.startswith("```"):
                    # Xử lý code block đơn giản
                    lines = block.split('\n')
                    lang = lines[0].replace('```', '').strip()
                    code = '\n'.join(lines[1:-1]) if len(lines) > 2 else ""
                    current_parent.add_child(CodeBlockNode(language=lang, code=code))
                else:
                    # Tách block thành nhiều paragraphs dựa trên \n\n
                    sub_paragraphs = re.split(r'\n\s*\n', block)
                    for sp in sub_paragraphs:
                        sp = sp.strip()
                        if sp:
                            current_parent.add_child(ParagraphNode(content=sp))
                    
        return root

