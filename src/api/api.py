import os
import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from src.ingestion.parsers.markitdown_parser import MarkItDownParser
from src.ingestion.parsers.web_parser import WebParser
from src.ingestion.chunking import AdaptiveChunker
from src.ingestion.embedding import LocalEmbedder
from src.ingestion.indexing import VectorStoreManager
from src.retrieval.search_engine import SearchEngine
from src.llm.llm_client import LLMEngine
from src.db.session_manager import SessionManager
from src.learning.guide_generator import GuideGenerator
from src.learning.podcast_generator import PodcastGenerator

app = FastAPI(title="NotebookLM Mini API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instances (Lazy load)
embedder = None
vector_store = None
search_engine = None
llm_engine = None
session_manager = None

@app.on_event("startup")
def startup_event():
    global session_manager
    print("[System] Khoi dong cac Module Loi cua he thong...")
    # Khởi tạo DB manager trước vì nó rất nhẹ và cần thiết ngay
    session_manager = SessionManager()

def get_embedder():
    global embedder
    if embedder is None:
        embedder = LocalEmbedder()
    return embedder

def get_vector_store():
    global vector_store
    if vector_store is None:
        vector_store = VectorStoreManager(embedder=get_embedder())
    return vector_store

def get_search_engine():
    global search_engine
    if search_engine is None:
        search_engine = SearchEngine(vector_store=get_vector_store())
    return search_engine

def get_llm_engine():
    global llm_engine
    if llm_engine is None:
        llm_engine = LLMEngine()
    return llm_engine

class NotebookCreate(BaseModel):
    id: str
    title: str
    is_private: bool = True
    gemini_api_key: Optional[str] = None

@app.post("/api/notebooks")
def create_notebook(data: NotebookCreate):
    session_manager.create_notebook(data.id, data.title, data.is_private, data.gemini_api_key)
    return {"status": "success", "notebook": data.dict()}

@app.get("/api/notebooks")
def list_notebooks():
    return session_manager.list_notebooks()

@app.delete("/api/notebooks/{notebook_id}")
def delete_notebook(notebook_id: str):
    session_manager.delete_notebook(notebook_id)
    store = get_vector_store()
    store.delete_notebook_chunks(notebook_id)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/documents")
def get_documents(notebook_id: str):
    return session_manager.get_documents(notebook_id)

@app.delete("/api/notebooks/{notebook_id}/documents")
def delete_document(notebook_id: str, filename: str):
    session_manager.delete_document(notebook_id, filename)
    store = get_vector_store()
    store.delete_document_chunks(notebook_id, filename)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/messages")
def get_messages(notebook_id: str):
    return session_manager.get_chat_history(notebook_id)

@app.get("/api/notebooks/{notebook_id}/study-guide")
def get_study_guide(notebook_id: str):
    return session_manager.get_study_guide(notebook_id)

class ChatRequest(BaseModel):
    query: str
    notebook_id: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Xử lý câu hỏi của người dùng và stream câu trả lời."""
    notebook = session_manager.get_notebook(request.notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
        
    # Lưu tin nhắn người dùng
    session_manager.save_message(request.notebook_id, "user", request.query)
    
    # Hàm stream và lưu tin nhắn AI
    def stream_and_save():
        full_response = ""
        is_private = notebook.get('is_private', True)
        api_key = notebook.get('gemini_api_key')
        citations = []
        
        try:
            # Gửi status: Đang tìm kiếm
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tìm kiếm dữ liệu trong Sổ tay...'})}\n\n"
            
            # 1. Truy xuất dữ liệu (Retrieval)
            engine = get_search_engine()
            context_str, results = engine.retrieve(request.query, notebook_id=request.notebook_id)
            
            # Gửi status: Phân tích
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang đọc và phân tích ngữ cảnh...'})}\n\n"
            
            for doc in results:
                citations.append({
                    "marker": f"[{len(citations)+1}]",
                    "filename": doc['metadata'].get('source_file') or doc['metadata'].get('title') or doc['metadata'].get('source_url') or doc['metadata'].get('filename') or 'Tài liệu'
                })
            
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

            # 2. Xây dựng Prompt
            llm = get_llm_engine()
            rag_prompt = llm.build_rag_prompt(request.query, context_str)
            system_prompt = "Bạn là một trợ lý ảo thông minh. Hãy trả lời câu hỏi dựa trên tài liệu được cung cấp."
            
            # Gửi status: Gọi AI
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI đang suy nghĩ câu trả lời...'})}\n\n"

            # 3. Gửi từng chunk text (Hỗ trợ Batching tự nhiên)
            for chunk in llm.generate(rag_prompt, system_prompt, is_private=is_private, gemini_api_key=api_key):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                
            # Xóa status khi hoàn thành
            yield f"data: {json.dumps({'type': 'status', 'message': ''})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'chunk', 'text': f'Lỗi hệ thống: {e}'})}\n\n"
        finally:
            session_manager.save_message(request.notebook_id, "assistant", full_response, citations=citations)

    # 3. Stream phản hồi
    return StreamingResponse(
        stream_and_save(),
        media_type="text/event-stream"
    )

@app.post("/api/ingest/url")
async def ingest_url(background_tasks: BackgroundTasks, notebook_id: str = Form(...), url: str = Form(...)):
    """Nạp dữ liệu từ URL."""
    parser = WebParser()
    tree = parser.parse(url, source_metadata={"notebook_id": notebook_id})
    
    filename = tree.metadata.get("title", url)
    chunker = AdaptiveChunker(embedder=get_embedder())
    chunks = chunker.process_document(tree)
    
    for chunk in chunks:
        chunk["metadata"]["notebook_id"] = notebook_id
        chunk["metadata"]["filename"] = filename
    
    store = get_vector_store()
    store.index_chunks(chunks)
    
    session_manager.add_document(notebook_id, filename)
    
    document_text = "\n\n".join([chunk["content"] for chunk in chunks])
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None

    # Sinh Study Guide ngầm
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    background_tasks.add_task(
        guide_gen.generate, 
        notebook_id, 
        document_text, 
        is_private=is_private,
        gemini_api_key=api_key
    )
    
    return {"status": "success", "chunks_indexed": len(chunks)}

@app.post("/api/ingest/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    notebook_id: str = Form(...), 
    file: UploadFile = File(...)
):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    if file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
        from src.ingestion.parsers.audio_parser import AudioParser
        parser = AudioParser()
    else:
        parser = MarkItDownParser()
        
    tree = parser.parse(file_path, source_metadata={"notebook_id": notebook_id})
    
    chunker = AdaptiveChunker(embedder=get_embedder())
    chunks = chunker.process_document(tree)
    
    for chunk in chunks:
        chunk["metadata"]["notebook_id"] = notebook_id
        chunk["metadata"]["filename"] = file.filename
    
    store = get_vector_store()
    store.index_chunks(chunks)
    
    session_manager.add_document(notebook_id, file.filename)
    
    document_text = "\n\n".join([chunk["content"] for chunk in chunks])
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None

    # Sinh Study Guide ngầm
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    background_tasks.add_task(
        guide_gen.generate, 
        notebook_id, 
        document_text, 
        is_private=is_private,
        gemini_api_key=api_key
    )
    
    return {"status": "success", "chunks_indexed": len(chunks)}

@app.post("/api/podcast/generate")
async def generate_podcast(background_tasks: BackgroundTasks, notebook_id: str = Form(...)):
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None
    
    llm = get_llm_engine()
    generator = PodcastGenerator(llm, session_manager)
    background_tasks.add_task(
        generator.generate_podcast, 
        notebook_id,
        is_private=is_private,
        gemini_api_key=api_key
    )
    return {"status": "processing"}

@app.post("/api/evaluate")
async def evaluate_knowledge(notebook_id: str = Form(...)):
    notebook = session_manager.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
        
    is_private = notebook.get('is_private', True)
    api_key = notebook.get('gemini_api_key')
    
    from src.learning.evaluator import Evaluator
    llm = get_llm_engine()
    evaluator = Evaluator(llm, session_manager)
    
    try:
        metrics = evaluator.evaluate_knowledge(notebook_id, is_private=is_private, gemini_api_key=api_key)
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# Phục vụ giao diện React (Frontend SPA)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")
    
    @app.get("/{catchall:path}")
    def serve_react_app(catchall: str):
        """Bắt mọi route không có trong API và trả về index.html của React Router."""
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend chưa được build. Vui lòng chạy npm run build trong thư mục frontend."}
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Hệ thống đang chạy ngầm. Giao diện React chưa được build (thiếu thư mục frontend/dist)."}
