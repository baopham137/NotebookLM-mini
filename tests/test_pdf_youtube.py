import requests
import json
import time
from reportlab.pdfgen import canvas
import os

def create_pdf(filepath):
    c = canvas.Canvas(filepath)
    c.drawString(100, 750, "Báo cáo Mật: Dự án Omega")
    c.drawString(100, 730, "Mục đích của dự án Omega là nghiên cứu và chế tạo ra cà phê AI.")
    c.drawString(100, 710, "Cà phê AI giúp lập trình viên viết code nhanh gấp 10 lần.")
    c.save()
    print(f"Created PDF: {filepath}")

def test_pdf_youtube():
    print("\n=== BẮT ĐẦU TEST PDF VÀ YOUTUBE URL ===")
    notebook_id = "test_media_notebook"
    
    # 1. Create notebook
    requests.delete(f"http://localhost:8000/api/notebooks/{notebook_id}")
    res = requests.post("http://localhost:8000/api/notebooks", json={
        "id": notebook_id,
        "title": "Media Test Notebook",
        "is_private": True
    })
    print("1. Tạo Notebook:", res.json())
    
    # 2. Upload PDF
    pdf_path = "test_omega.pdf"
    create_pdf(pdf_path)
    with open(pdf_path, 'rb') as f:
        res = requests.post(
            "http://localhost:8000/api/ingest/upload",
            data={"notebook_id": notebook_id},
            files={"file": (pdf_path, f, "application/pdf")}
        )
    print("2. Upload PDF:", res.json())
    
    # 3. Ingest YouTube URL (Một video ngắn bất kỳ, ví dụ video giới thiệu iPhone 15 hoặc gì đó)
    # Lấy video ngắn: "Me at the zoo" (video đầu tiên của YouTube) - dài 18 giây
    youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    res = requests.post(
        "http://localhost:8000/api/ingest/url",
        data={"notebook_id": notebook_id, "url": youtube_url}
    )
    print("3. Ingest YouTube:", res.json())
    
    # 4. Chờ xử lý xong
    print("4. Đang chờ hệ thống xử lý ngầm (Chunking, Embedding, Reranking Index)...")
    while True:
        res = requests.get(f"http://localhost:8000/api/notebooks/{notebook_id}/documents")
        docs = res.json()
        all_ready = True
        for doc in docs:
            print(f"   - {doc['filename']}: {doc['status']}")
            if doc['status'] != 'ready':
                all_ready = False
        
        if len(docs) == 2 and all_ready:
            print("=> Tất cả tài liệu đã sẵn sàng!")
            break
        time.sleep(3)
        
    # 5. Hỏi đáp về PDF
    print("\n--- Hỏi về PDF ---")
    payload = {
        "query": "Dự án Omega là gì?",
        "notebook_id": notebook_id
    }
    with requests.post("http://localhost:8000/api/chat", json=payload, stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data = json.loads(decoded[6:])
                    if data['type'] == 'status':
                        print(f"Status: {data['message']}")
                    elif data['type'] == 'chunk':
                        print(data['text'], end="", flush=True)
    print("\n")

    # 6. Hỏi đáp về YouTube
    print("\n--- Hỏi về YouTube Video ---")
    payload = {
        "query": "Video trên YouTube nói về cái gì?",
        "notebook_id": notebook_id
    }
    with requests.post("http://localhost:8000/api/chat", json=payload, stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data = json.loads(decoded[6:])
                    if data['type'] == 'status':
                        print(f"Status: {data['message']}")
                    elif data['type'] == 'chunk':
                        print(data['text'], end="", flush=True)
    print("\n")

if __name__ == "__main__":
    test_pdf_youtube()
