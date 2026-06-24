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
from fastapi.responses import HTMLResponse
from src.utils.telemetry import get_system_resources
from src.utils.logger import app_logger
from src.utils.telemetry import trace_execution

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
from src.retrieval.query_rewriter import QueryRewriter
from src.retrieval.bm25_index import get_bm25_index, BM25Document, delete_bm25_folder
from src.retrieval.semantic_router import get_semantic_router
import uuid
from cachetools import TTLCache

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
    import pydub
    import imageio_ffmpeg
    pydub.AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    pass

app = FastAPI(title="NotebookLM Mini API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import threading

vector_store_lock = threading.Lock()
search_engine_lock = threading.Lock()
llm_engine_lock = threading.Lock()

# Cache LRU + TTL: Tối đa 200 câu hỏi, tự động xóa sau 60 phút (3600 giây) không truy cập
_QUERY_CACHE = TTLCache(maxsize=200, ttl=3600)

def clear_cache(notebook_id: str):
    keys_to_delete = [k for k in _QUERY_CACHE.keys() if k.startswith(f"{notebook_id}_")]
    for k in keys_to_delete:
        del _QUERY_CACHE[k]

query_rewriter = None
def get_query_rewriter():
    global query_rewriter
    if query_rewriter is None:
        query_rewriter = QueryRewriter()
    return query_rewriter

@app.on_event("startup")
def startup_event():
    global session_manager
    print("[System] Khoi dong cac Module Loi cua he thong...")
    # Khởi tạo DB manager trước vì nó rất nhẹ và cần thiết ngay
    session_manager = SessionManager()

def get_embedder():
    from src.utils.vram_orchestrator import get_orchestrator
    return get_orchestrator().get_embedder()

def get_vector_store():
    global vector_store
    if vector_store is None:
        with vector_store_lock:
            if vector_store is None:
                vector_store = VectorStoreManager()
    return vector_store

def get_search_engine():
    global search_engine
    if search_engine is None:
        with search_engine_lock:
            if search_engine is None:
                search_engine = SearchEngine(vector_store=get_vector_store())
    return search_engine

def get_llm_engine():
    global llm_engine
    if llm_engine is None:
        with llm_engine_lock:
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
    delete_bm25_folder(notebook_id)
    clear_cache(notebook_id)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/documents")
def get_documents(notebook_id: str):
    return session_manager.get_documents(notebook_id)

@app.delete("/api/notebooks/{notebook_id}/documents")
def delete_document(notebook_id: str, filename: str):
    session_manager.delete_document(notebook_id, filename)
    store = get_vector_store()
    store.delete_document_chunks(notebook_id, filename)
    
    # Xóa khỏi BM25
    bm25_index = get_bm25_index(notebook_id)
    with bm25_index.transaction():
        bm25_index.load()
        bm25_index.remove_document(filename)
        bm25_index.save()
    
    # Nếu thẻ không còn tài liệu nào → xóa Cẩm nang hồn ma
    remaining_docs = session_manager.get_documents(notebook_id)
    if len(remaining_docs) == 0:
        session_manager.delete_study_guide(notebook_id)
    
    clear_cache(notebook_id)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/messages")
def get_messages(notebook_id: str):
    return session_manager.get_chat_history(notebook_id)

@app.delete("/api/notebooks/{notebook_id}/messages")
def delete_messages(notebook_id: str):
    """Xóa toàn bộ lịch sử chat của một Notebook."""
    session_manager.delete_messages(notebook_id)
    clear_cache(notebook_id)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/study-guide")
def get_study_guide(notebook_id: str):
    return session_manager.get_study_guide(notebook_id)

@app.delete("/api/notebooks/{notebook_id}/study-guide")
def delete_study_guide(notebook_id: str):
    """Xóa Cẩm nang học tập của một Notebook."""
    session_manager.delete_study_guide(notebook_id)
    return {"status": "success"}


class ChatRequest(BaseModel):
    query: str
    notebook_id: str
    mode: str = "normal"

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
        
        # --- PRE-ROUTING (Định tuyến lần 1 - Tốc độ cao) ---
        router = get_semantic_router()
        intent = router.route(request.query)
        
        final_query = request.query
        if intent != "chitchat":
            # --- SMART CACHE: Chạy Query Rewriter để sửa lỗi chính tả ---
            try:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Đang phân tích và tối ưu câu hỏi...'})}\n\n"
                rewriter = get_query_rewriter()
                final_query = rewriter.rewrite(request.query)
                
                # --- RE-ROUTING (Định tuyến lần 2 - Sau khi sửa lỗi) ---
                if final_query != request.query:
                    intent = router.route(final_query)
                    
            except Exception:
                pass
        
        cache_key = f"{request.notebook_id}_{final_query}"
        
        # --- CHECK CACHE (dùng câu hỏi đã chuẩn hóa) ---
        if cache_key in _QUERY_CACHE:
            cached_data = _QUERY_CACHE[cache_key]
            full_response = cached_data["response"]
            citations = cached_data["citations"]
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang lấy dữ liệu từ Cache...'})}\n\n"
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
                
            # Fake streaming for cached content
            chunk_size = 20
            import time
            for i in range(0, len(full_response), chunk_size):
                chunk = full_response[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                time.sleep(0.02)
            
            yield f"data: {json.dumps({'type': 'status', 'message': ''})}\n\n"
            session_manager.save_message(request.notebook_id, "assistant", full_response, citations=citations)
            return
            
        try:
            if intent == "chitchat":
                yield f"data: {json.dumps({'type': 'status', 'message': 'Đang suy nghĩ câu trả lời...'})}\n\n"
                context_str = ""
                results = []
            elif intent == "summarize":
                yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tổng hợp thông tin từ tài liệu...'})}\n\n"
                engine = get_search_engine()
                context_str, results = engine.retrieve(final_query, notebook_id=request.notebook_id, top_k=10)
            else:
                yield f"data: {json.dumps({'type': 'status', 'message': f'Đang tìm kiếm dữ liệu cho: {final_query}'})}\n\n"
                engine = get_search_engine()
                context_str, results = engine.retrieve(final_query, notebook_id=request.notebook_id, top_k=5)
            
            # Gửi status: Phân tích
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang đọc và phân tích ngữ cảnh...'})}\n\n"
            
            for doc in results:
                citations.append({
                    "marker": f"[{len(citations)+1}]",
                    "filename": doc['metadata'].get('source_file') or doc['metadata'].get('title') or doc['metadata'].get('source_url') or doc['metadata'].get('filename') or 'Tài liệu'
                })
            
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

            # --- Lấy lịch sử chat ---
            raw_history = session_manager.get_chat_history(request.notebook_id)
            # Không lấy câu hỏi cuối vì nó chính là request.query vừa mới được save ở trên
            history = raw_history[:-1] if len(raw_history) > 0 else []

            # 2. Xây dựng Prompt
            llm = get_llm_engine()
            rag_prompt = llm.build_rag_prompt(final_query, context_str, history=history)
            system_prompt = "Bạn là một trợ lý ảo thông minh. Hãy trả lời câu hỏi dựa trên tài liệu được cung cấp."
            if request.mode == "escape-room":
                system_prompt = "Bạn là Jigsaw - một Quản Trò (Game Master) đáng sợ trong một trò chơi sinh tồn Escape Room. Bạn đã nhốt người chơi vào một căn phòng ảo. Dựa vào tài liệu được cung cấp, hãy nghĩ ra MỘT câu đố liên quan đến kiến thức trong tài liệu và yêu cầu người chơi giải nó để mở khóa thoát hiểm. Giọng điệu của bạn phải bí ẩn, u ám và có chút đe dọa. KHÔNG trả lời thẳng câu hỏi của người chơi, chỉ đưa ra manh mối và bắt họ giải đố."

            
            # Gửi status: Gọi AI
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI đang suy nghĩ câu trả lời...'})}\n\n"

            # 3. Gửi từng chunk text (Hỗ trợ Batching tự nhiên)
            for chunk in llm.generate(rag_prompt, system_prompt, is_private=is_private, gemini_api_key=api_key):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                
            # Xóa status khi hoàn thành
            yield f"data: {json.dumps({'type': 'status', 'message': ''})}\n\n"
            
            # --- LƯU CACHE ---
            _QUERY_CACHE[cache_key] = {
                "response": full_response,
                "citations": citations
            }
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'chunk', 'text': f'Lỗi hệ thống: {e}'})}\n\n"
        finally:
            from src.utils.vram_orchestrator import get_orchestrator
            get_orchestrator().release_all()
            session_manager.save_message(request.notebook_id, "assistant", full_response, citations=citations)

    # 3. Stream phản hồi
    return StreamingResponse(
        stream_and_save(),
        media_type="text/event-stream"
    )

def _index_all_chunks(notebook_id: str, chunks: list):
    # Vector Indexing
    store = get_vector_store()
    store.index_chunks(chunks)
    
    # BM25 Indexing
    bm25_index = get_bm25_index(notebook_id)
    bm25_docs = [
        BM25Document(
            chunk_id=chunk["metadata"].get("chunk_id", str(uuid.uuid4())),
            text=chunk["content"],
            metadata=chunk["metadata"]
        ) for chunk in chunks
    ]
    with bm25_index.transaction():
        bm25_index.load()
        bm25_index.add_documents(bm25_docs)
        bm25_index.save()

def process_document_bg(notebook_id: str, tree, filename: str, is_private: bool, api_key: Optional[str]):
    try:
        chunker = AdaptiveChunker(embedder=get_embedder())
        chunks = chunker.process_document(tree)
        
        for chunk in chunks:
            chunk["metadata"]["notebook_id"] = notebook_id
            chunk["metadata"]["filename"] = filename
        
        _index_all_chunks(notebook_id, chunks)
        
        # Cập nhật trạng thái thành công
        session_manager.update_document_status(notebook_id, filename, "ready")
        
        document_text = "\n\n".join([chunk["content"] for chunk in chunks])
        
        # Sinh Study Guide ngầm
        llm = get_llm_engine()
        guide_gen = GuideGenerator(llm, session_manager)
        guide_gen.generate(
            notebook_id, 
            document_text, 
            is_private=is_private,
            gemini_api_key=api_key
        )
        
        clear_cache(notebook_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        session_manager.update_document_status(notebook_id, filename, "error")
    finally:
        from src.utils.vram_orchestrator import get_orchestrator
        get_orchestrator().release_all()

@app.post("/api/ingest/url")
@trace_execution(event_name="ingest_url", module="api")
async def ingest_url(background_tasks: BackgroundTasks, notebook_id: str = Form(...), url: str = Form(...)):
    """Nạp dữ liệu từ URL."""
    parser = WebParser()
    tree = parser.parse(url, source_metadata={"notebook_id": notebook_id})
    
    filename = tree.metadata.get("title", url)
    
    session_manager.add_document(notebook_id, filename, status="processing")
    
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None

    background_tasks.add_task(
        process_document_bg, 
        notebook_id, 
        tree, 
        filename, 
        is_private, 
        api_key
    )
    
    return {"status": "success", "message": "URL is processing in background"}

@app.post("/api/ingest/upload")
@trace_execution(event_name="ingest_file", module="api")
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
        tree = parser.parse(file_path, source_metadata={"notebook_id": notebook_id})
    elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
        from src.ingestion.parsers.image_parser import ImageParser
        parser = ImageParser()
        tree = parser.parse(file_path, source_metadata={"notebook_id": notebook_id})
    elif file.filename.lower().endswith(('.md', '.markdown')):
        from src.ingestion.parsers.markdown_parser import MarkdownParser
        parser = MarkdownParser()
        with open(file_path, "r", encoding="utf-8") as f:
            tree = parser.parse(f.read(), source_metadata={"notebook_id": notebook_id})
    else:
        parser = MarkItDownParser()
        tree = parser.parse(file_path, source_metadata={"notebook_id": notebook_id})
    
    filename = file.filename
    
    session_manager.add_document(notebook_id, filename, status="processing")
    
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None

    background_tasks.add_task(
        process_document_bg, 
        notebook_id, 
        tree, 
        filename, 
        is_private, 
        api_key
    )
    
    return {"status": "success", "message": "File is processing in background"}

@app.post("/api/podcast/generate")
async def generate_podcast(background_tasks: BackgroundTasks, notebook_id: str = Form(...), style: str = Form("normal")):
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None
    
    llm = get_llm_engine()
    generator = PodcastGenerator(llm, session_manager)
    background_tasks.add_task(
        generator.generate_podcast, 
        notebook_id,
        is_private=is_private,
        style=style,
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

@app.get("/api/health")
def health_check():
    status = "OK"
    return {"status": status}

@app.get("/api/system-resources")
def system_resources():
    return get_system_resources()

@app.get("/api/metrics")
def get_metrics():
    # Đọc file logs/telemetry.jsonl để phân tích
    import json
    from pathlib import Path
    telemetry_file = Path("logs/telemetry.jsonl")
    total_queries = 0
    total_errors = 0
    recent_latencies = []
    
    if telemetry_file.exists():
        with open(telemetry_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-100:]:
                try:
                    data = json.loads(line)
                    if data.get("event") == "generate_llm" or data.get("event") == "chat_stream":
                        total_queries += 1
                        if not data.get("success", True):
                            total_errors += 1
                        if "latency_ms" in data:
                            recent_latencies.append(data["latency_ms"])
                except:
                    pass
                    
    return {
        "total_queries": total_queries,
        "total_errors": total_errors,
        "recent_latencies": recent_latencies[-20:]
    }

@app.get("/monitoring", response_class=HTMLResponse)
def serve_monitoring():
    html_path = os.path.join(os.path.dirname(__file__), "monitoring.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Dashboard HTML not found."

# --- CUSTOM GENERATION ENDPOINTS ---
class CustomQuizRequest(BaseModel):
    amount: int = 5
    difficulty: str = "Trung bình (Mặc định)"
    topic: str = ""
    language: str = "Tiếng Việt"

@app.post("/api/notebooks/{notebook_id}/quiz/custom")
def generate_custom_quiz(notebook_id: str, req: CustomQuizRequest):
    nb = session_manager.get_notebook(notebook_id)
    if not nb: raise HTTPException(status_code=404)
    engine = get_search_engine()
    context_str, _ = engine.retrieve("tổng hợp toàn bộ ý chính " + req.topic, notebook_id=notebook_id, top_k=30)
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    result = guide_gen.generate_custom_quiz(notebook_id, context_str, req.topic, req.difficulty, req.amount, req.language, nb.get('is_private', True), nb.get('gemini_api_key'))
    # Update DB
    guide = session_manager.get_study_guide(notebook_id) or {}
    session_manager.save_study_guide(notebook_id, guide.get('summary', ''), guide.get('faq', ''), guide.get('glossary', ''), quiz=result, flashcards=guide.get('flashcards', ''), mindmap=guide.get('mindmap', ''))
    return {"status": "success", "quiz": result}

class CustomFlashcardRequest(BaseModel):
    amount: int = 5
    difficulty: str = "Trung bình (Mặc định)"
    topic: str = ""
    language: str = "Tiếng Việt"

@app.post("/api/notebooks/{notebook_id}/flashcards/custom")
def generate_custom_flashcards(notebook_id: str, req: CustomFlashcardRequest):
    nb = session_manager.get_notebook(notebook_id)
    if not nb: raise HTTPException(status_code=404)
    engine = get_search_engine()
    context_str, _ = engine.retrieve("tổng hợp toàn bộ ý chính " + req.topic, notebook_id=notebook_id, top_k=30)
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    result = guide_gen.generate_custom_flashcards(notebook_id, context_str, req.topic, req.difficulty, req.amount, req.language, nb.get('is_private', True), nb.get('gemini_api_key'))
    # Update DB
    guide = session_manager.get_study_guide(notebook_id) or {}
    session_manager.save_study_guide(notebook_id, guide.get('summary', ''), guide.get('faq', ''), guide.get('glossary', ''), quiz=guide.get('quiz', ''), flashcards=result, mindmap=guide.get('mindmap', ''))
    return {"status": "success", "flashcards": result}

class CustomMindmapRequest(BaseModel):
    topic: str = ""

@app.post("/api/notebooks/{notebook_id}/mindmap/custom")
def generate_custom_mindmap(notebook_id: str, req: CustomMindmapRequest):
    nb = session_manager.get_notebook(notebook_id)
    if not nb: raise HTTPException(status_code=404)
    engine = get_search_engine()
    context_str, _ = engine.retrieve("tổng hợp toàn bộ ý chính " + req.topic, notebook_id=notebook_id, top_k=30)
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    result = guide_gen.generate_custom_mindmap(notebook_id, context_str, req.topic, nb.get('is_private', True), nb.get('gemini_api_key'))
    guide = session_manager.get_study_guide(notebook_id) or {}
    session_manager.save_study_guide(notebook_id, guide.get('summary', ''), guide.get('faq', ''), guide.get('glossary', ''), quiz=guide.get('quiz', ''), flashcards=guide.get('flashcards', ''), mindmap=result)
    return {"status": "success", "mindmap": result}

class CustomPodcastRequest(BaseModel):
    topic: str = ""
    language: str = "Tiếng Việt"

@app.post("/api/notebooks/{notebook_id}/podcast/custom")
def generate_custom_podcast_api(notebook_id: str, req: CustomPodcastRequest):
    nb = session_manager.get_notebook(notebook_id)
    if not nb: raise HTTPException(status_code=404)
    engine = get_search_engine()
    context_str, _ = engine.retrieve("tổng hợp toàn bộ ý chính " + req.topic, notebook_id=notebook_id, top_k=30)
    llm = get_llm_engine()
    pod_gen = PodcastGenerator(llm, session_manager)
    audio_url = pod_gen.generate_custom_podcast(notebook_id, context_str, req.topic, req.language, nb.get('is_private', True), nb.get('gemini_api_key'))
    return {"status": "success", "audio_url": audio_url}

# --- SYSTEM MODEL CONFIGURATION ENDPOINTS ---
class SetupModelRequest(BaseModel):
    type: str  # "vision" hoặc "audio"
    model_name: str # Tên model

@app.get("/api/system/models-status")
def get_models_status():
    from src.utils.config import settings
    return {
        "vision_configured": bool(settings.vision_model) or settings.vision_mode == "ocr",
        "vision_mode": settings.vision_mode,
        "vision_model": settings.vision_model,
        "audio_configured": bool(settings.audio_model),
        "audio_model": settings.audio_model
    }

@app.post("/api/system/setup-model")
def setup_system_model(req: SetupModelRequest):
    import os
    import re
    from src.utils.config import settings
    
    env_path = os.path.join(os.getcwd(), ".env")
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()

    try:
        if req.type == "vision":
            vision_mode = "ocr" if "ocr" in req.model_name.lower() else "local_model"
            vision_model_name = "" if vision_mode == "ocr" else req.model_name
            
            # Download model
            if vision_mode == "local_model" and vision_model_name:
                from huggingface_hub import snapshot_download
                if "moondream2" in vision_model_name.lower():
                    snapshot_download(vision_model_name, revision="2024-08-26")
                else:
                    snapshot_download(vision_model_name)
                    
            # Update .env
            if "RAG_VISION_MODE" in env_content:
                env_content = re.sub(r'RAG_VISION_MODE=.*', f'RAG_VISION_MODE={vision_mode}', env_content)
                env_content = re.sub(r'RAG_VISION_MODEL=.*', f'RAG_VISION_MODEL={vision_model_name}', env_content)
            else:
                env_content += f"\n# Vision Configuration\nRAG_VISION_MODE={vision_mode}\nRAG_VISION_MODEL={vision_model_name}\n"
            
            # Update settings at runtime
            settings.vision_mode = vision_mode
            settings.vision_model = vision_model_name
            
        elif req.type == "audio":
            # Download model
            import whisper
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cache_dir = os.path.join(os.getcwd(), "cache", "whisper")
                os.makedirs(cache_dir, exist_ok=True)
                whisper.load_model(req.model_name, download_root=cache_dir, device="cpu")
                
            # Update .env
            if "RAG_AUDIO_MODEL" in env_content:
                env_content = re.sub(r'RAG_AUDIO_MODEL=.*', f'RAG_AUDIO_MODEL={req.model_name}', env_content)
            else:
                env_content += f"\n# Audio Configuration\nRAG_AUDIO_MODEL={req.model_name}\n"
                
            # Update settings at runtime
            settings.audio_model = req.model_name
            
        else:
            raise HTTPException(status_code=400, detail="Invalid model type")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
            
        return {"status": "success", "message": f"Cấu hình {req.type} model thành công."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- END SYSTEM MODEL CONFIGURATION ENDPOINTS ---

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
