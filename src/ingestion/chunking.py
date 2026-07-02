import re
import numpy as np
from typing import List, Dict, Any
from .document_tree import DocumentNode, HeadingNode, ParagraphNode, Node
from ..utils.config import settings

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

class RecursiveCharacterChunker:
    """Chia văn bản dựa trên số lượng ký tự đệ quy (Nhanh, cho CPU)."""
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )

    def chunk_text(self, text: str) -> List[str]:
        # Sử dụng thư viện LangChain để cắt chữ thông minh, bảo tồn câu
        return self.splitter.split_text(text)

class SemanticChunker:
    """Chia văn bản dựa trên khoảng cách ngữ nghĩa (Chậm, cần GPU)."""
    def __init__(self, embedder, threshold: float = 0.75):
        self.embedder = embedder
        self.threshold = threshold

    def chunk_text(self, text: str) -> List[str]:
        # Tách thành từng câu
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if not sentences:
            return []
            
        # Tính embedding cho tất cả các câu một lúc (Batching)
        embeddings = self.embedder.embed_documents(sentences)
        
        chunks = []
        current_chunk = [sentences[0]]
        
        for i in range(1, len(sentences)):
            sim = cosine_similarity(embeddings[i-1], embeddings[i])
            # Nếu 2 câu giống nhau về ý tưởng (similarity > threshold), gộp chung
            if sim >= self.threshold:
                current_chunk.append(sentences[i])
            else:
                # Nếu khác chủ đề, cắt ra tạo chunk mới
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i]]
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks

class AdaptiveChunker:
    """Tự động lựa chọn phương pháp Chunking phù hợp với phần cứng."""
    
    def __init__(self, embedder=None):
        self.tier = self._get_hardware_tier()
        
        # Kiểm tra thực tế xem Embedder có được lên GPU hay không (tránh báo cáo giả)
        is_embedder_on_gpu = False
        if embedder and hasattr(embedder, 'device'):
            is_embedder_on_gpu = str(embedder.device) != "cpu"
            
        if self.tier in [1, 2] and is_embedder_on_gpu:
            if not embedder:
                raise ValueError("Semantic Chunking cần một Embedder object.")
            print("[AdaptiveChunker] Chế độ GPU: Kích hoạt Semantic Chunking.")
            self.chunker = SemanticChunker(embedder=embedder, threshold=0.75)
        else:
            print("[AdaptiveChunker] Chế độ CPU: Kích hoạt Recursive Character Chunking.")
            self.chunker = RecursiveCharacterChunker(
                chunk_size=settings.chunk_size, 
                chunk_overlap=settings.chunk_overlap
            )

    def _get_hardware_tier(self) -> int:
        from ..utils.hardware_profiler import ModelZooManager
        manager = ModelZooManager()
        if manager.has_cuda:
            return 1 if manager.vram_gb >= 12 else 2
        return 3

    def process_document(self, document_node: DocumentNode) -> List[Dict[str, Any]]:
        """Duyệt Cây Tài liệu (DFS) và chunking các Paragraph, bảo lưu Metadata."""
        final_chunks = []
        
        def traverse(node: Node):
            # Chỉ chunking các node chứa văn bản dài như ParagraphNode
            if isinstance(node, ParagraphNode) and node.content.strip():
                # Băm nhỏ nội dung
                text_chunks = self.chunker.chunk_text(node.content)
                for chunk_text in text_chunks:
                    final_chunks.append({
                        "content": chunk_text,
                        "metadata": node.metadata # Metadata đã được kế thừa từ cha (Heading)
                    })
            
            # Duyệt tiếp các node con
            for child in node.children:
                traverse(child)

        traverse(document_node)
        return final_chunks
