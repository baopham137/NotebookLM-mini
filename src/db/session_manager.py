import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

class SessionManager:
    """Quản lý CSDL SQLite cho Notebooks, tin nhắn và Study Guides."""
    
    def __init__(self, db_path: str = "storage/notebooks.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
        
    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Bảng Notebooks (Chứa cơ chế bảo mật is_private)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notebooks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    is_private BOOLEAN NOT NULL DEFAULT 1,
                    gemini_api_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Bảng Documents (Tài liệu tải lên)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notebook_id TEXT,
                    filename TEXT NOT NULL,
                    status TEXT DEFAULT 'ready',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (notebook_id) REFERENCES notebooks (id)
                )
            ''')
            
            # Bảng Messages (Tin nhắn Chat)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notebook_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations TEXT, -- JSON string
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (notebook_id) REFERENCES notebooks (id)
                )
            ''')
            
            # Bảng Study Guides
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS study_guides (
                    notebook_id TEXT PRIMARY KEY,
                    summary TEXT,
                    faq TEXT,
                    glossary TEXT,
                    quiz TEXT,
                    flashcards TEXT,
                    mindmap TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (notebook_id) REFERENCES notebooks (id)
                )
            ''')
            
            # Thêm cột mindmap nếu chưa có (migration)
            try:
                cursor.execute("ALTER TABLE study_guides ADD COLUMN mindmap TEXT")
            except sqlite3.OperationalError:
                pass # Cột đã tồn tại
            
            # Kiểm tra và thêm cột quiz, flashcards nếu bảng đã tồn tại nhưng chưa có cột (schema migration)
            try:
                cursor.execute("ALTER TABLE study_guides ADD COLUMN quiz TEXT")
                cursor.execute("ALTER TABLE study_guides ADD COLUMN flashcards TEXT")
            except sqlite3.OperationalError:
                pass # Cột đã tồn tại
                
            # Migration cho bảng documents (thêm status)
            try:
                cursor.execute("ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'ready'")
            except sqlite3.OperationalError:
                pass
                
            # Migration cho bảng notebooks
            try:
                cursor.execute("ALTER TABLE notebooks ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE notebooks ADD COLUMN gemini_api_key TEXT")
            except sqlite3.OperationalError:
                pass
                

    # --- API Quản lý Notebooks ---
    def create_notebook(self, notebook_id: str, title: str = "Notebook mới", is_private: bool = True, gemini_api_key: Optional[str] = None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notebooks (id, title, is_private, gemini_api_key) VALUES (?, ?, ?, ?)",
                (notebook_id, title, is_private, gemini_api_key)
            )
            conn.commit()

    def list_notebooks(self) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, title, is_private, gemini_api_key, created_at FROM notebooks ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [{"id": r[0], "title": r[1], "is_private": bool(r[2]), "gemini_api_key": r[3], "created_at": r[4]} for r in rows]

    def update_notebook_privacy(self, notebook_id: str, is_private: bool):
        with self._get_conn() as conn:
            conn.execute("UPDATE notebooks SET is_private = ? WHERE id = ?", (is_private, notebook_id))
            conn.commit()

    def delete_notebook(self, notebook_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM study_guides WHERE notebook_id = ?", (notebook_id,))
            conn.execute("DELETE FROM messages WHERE notebook_id = ?", (notebook_id,))
            conn.execute("DELETE FROM documents WHERE notebook_id = ?", (notebook_id,))
            conn.execute("DELETE FROM notebooks WHERE id = ?", (notebook_id,))
            conn.commit()

    def get_notebook_privacy(self, notebook_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT is_private FROM notebooks WHERE id = ?", (notebook_id,))
            row = cursor.fetchone()
            return bool(row[0]) if row else True # Mặc định là Private nếu không tìm thấy

    def get_notebook(self, notebook_id: str) -> Dict:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, title, is_private, gemini_api_key, created_at FROM notebooks WHERE id = ?", (notebook_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "title": row[1], "is_private": bool(row[2]), "gemini_api_key": row[3], "created_at": row[4]}
            return None

    def add_document(self, notebook_id: str, filename: str, status: str = "processing"):
        with self._get_conn() as conn:
            conn.execute("INSERT INTO documents (notebook_id, filename, status) VALUES (?, ?, ?)", (notebook_id, filename, status))
            conn.commit()
            
    def update_document_status(self, notebook_id: str, filename: str, status: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE documents SET status = ? WHERE notebook_id = ? AND filename = ?", (status, notebook_id, filename))
            conn.commit()

    def delete_document(self, notebook_id: str, filename: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM documents WHERE notebook_id = ? AND filename = ?", (notebook_id, filename))
            conn.commit()

    def get_documents(self, notebook_id: str) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, filename, status, created_at FROM documents WHERE notebook_id = ? ORDER BY created_at ASC", (notebook_id,))
            rows = cursor.fetchall()
            return [{"id": r[0], "filename": r[1], "status": r[2], "created_at": r[3]} for r in rows]

    # --- API Quản lý Tin nhắn ---
    def save_message(self, notebook_id: str, role: str, content: str, citations: Optional[List[Dict]] = None):
        citations_str = json.dumps(citations, ensure_ascii=False) if citations else None
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (notebook_id, role, content, citations) VALUES (?, ?, ?, ?)",
                (notebook_id, role, content, citations_str)
            )
            conn.commit()

    def get_chat_history(self, notebook_id: str) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT role, content, citations FROM messages WHERE notebook_id = ? ORDER BY created_at ASC",
                (notebook_id,)
            )
            rows = cursor.fetchall()
            history = []
            for r in rows:
                cites = json.loads(r[2]) if r[2] else []
                history.append({
                    "role": r[0],
                    "content": r[1],
                    "citations": cites
                })
            return history

    # --- API Study Guide ---
    def save_study_guide(self, notebook_id: str, summary: str, faq: str, glossary: str, quiz: str = None, flashcards: str = None, mindmap: str = None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO study_guides (notebook_id, summary, faq, glossary, quiz, flashcards, mindmap) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (notebook_id, summary, faq, glossary, quiz, flashcards, mindmap)
            )
            conn.commit()

    def get_study_guide(self, notebook_id: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT summary, faq, glossary, quiz, flashcards, mindmap FROM study_guides WHERE notebook_id = ?", (notebook_id,))
            row = cursor.fetchone()
            if row:
                import json
                
                quiz_data = None
                flashcards_data = None
                if row[3]:
                    try: quiz_data = json.loads(row[3])
                    except: pass
                if row[4]:
                    try: flashcards_data = json.loads(row[4])
                    except: pass
                    
                return {
                    "summary": row[0], 
                    "faq": row[1], 
                    "glossary": row[2],
                    "quiz": quiz_data,
                    "flashcards": flashcards_data,
                    "mindmap": row[5]
                }
            return None

    def delete_study_guide(self, notebook_id: str):
        """Xóa Cẩm nang học tập của một Notebook."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM study_guides WHERE notebook_id = ?", (notebook_id,))
            conn.commit()

    def delete_messages(self, notebook_id: str):
        """Xóa toàn bộ lịch sử chat của một Notebook."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE notebook_id = ?", (notebook_id,))
            conn.commit()
