import os
import time
import requests
import json
import wave
import sys
from PIL import Image, ImageDraw

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def generate_test_data():
    os.makedirs("test_data", exist_ok=True)
    
    # 1. Markdown
    with open("test_data/test_doc_1.md", "w", encoding="utf-8") as f:
        f.write("# Máy tính lượng tử\n\nMáy tính lượng tử sử dụng Qubit thay vì Bit. Chồng chập lượng tử cho phép qubit ở nhiều trạng thái cùng lúc.\n")
        
    # 2. CSV
    with open("test_data/test_doc_2.csv", "w", encoding="utf-8") as f:
        f.write("Năm,Phát minh,Người phát minh\n1712,Động cơ hơi nước,Thomas Newcomen\n1765,Động cơ hơi nước cải tiến,James Watt\n")
        
    # 3. Image (PNG)
    img = Image.new('RGB', (400, 200), color = (73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((10,10), "Doanh thu Q3 2023 tang 45%", fill=(255,255,0))
    img.save("test_data/test_doc_3.png")
    
    # 4. Audio (WAV) - Create a 1 second silent WAV file
    with wave.open("test_data/test_doc_4.wav", "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b'\x00' * 44100 * 2)

    # 5. PDF (Mock structure)
    with open("test_data/test_doc_5.pdf", "wb") as f:
        f.write(b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%EOF\n")

    print("Generated 5 test files.")

def main():
    print("Waiting for server to start...")
    while True:
        try:
            res = requests.get(f"{BASE_URL}/api/health")
            if res.status_code == 200:
                print("Server is UP!")
                break
        except Exception:
            time.sleep(2)

    notebook_id = "test_nb_" + str(int(time.time()))
    
    # 1. Create Notebook
    print(f"\n--- Creating Notebook: {notebook_id} ---")
    requests.post(f"{BASE_URL}/api/notebooks", json={"id": notebook_id, "title": "E2E Test", "is_private": True})
    
    # 2. Upload Files
    print("--- Uploading Files ---")
    files_to_upload = ["test_doc_1.md", "test_doc_2.csv", "test_doc_3.png", "test_doc_4.wav", "test_doc_5.pdf"]
    for file_name in files_to_upload:
        with open(f"test_data/{file_name}", "rb") as f:
            res = requests.post(f"{BASE_URL}/api/ingest/upload", data={"notebook_id": notebook_id}, files={"file": f})
            print(f"Uploaded {file_name}: {res.status_code}")
            
    # 3. Ingest URL
    print("--- Ingesting URL ---")
    res = requests.post(f"{BASE_URL}/api/ingest/url", data={"notebook_id": notebook_id, "url": "https://vi.wikipedia.org/wiki/Tr%C3%AD_tu%E1%BB%87_nh%C3%A2n_t%E1%BA%A1o"})
    print(f"Ingested URL: {res.status_code}")
    
    # 4. Wait for processing
    print("--- Waiting for background processing (25s) ---")
    time.sleep(25)
    docs = requests.get(f"{BASE_URL}/api/notebooks/{notebook_id}/documents").json()
    print("Documents in DB:", [d["filename"] + " - " + d.get("status", "unknown") for d in docs])
    
    # 5. Queries
    print("\n--- Running Queries ---")
    long_prompt = "Đây là một đoạn text rất dài tôi copy paste vào. Năm 1712 Thomas Newcomen phát minh ra động cơ hơi nước, sau đó James Watt cải tiến nó năm 1765. Trong khi đó máy tính lượng tử dùng qubit. Đọc đoạn văn lủng củng tôi vừa dán trên và đối chiếu nó với các số liệu có trong hệ thống, chỉ ra sự tương quan."
    
    queries = [
        "xín cháo bạng",
        "hãy tómtắt hộ tui số liệu trong bảng csv",
        "Phát minh động cơ hơi nước năm bao nhiêu, có liên quan gì đến lượng tử không?",
        long_prompt
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        with requests.post(f"{BASE_URL}/api/chat", json={"notebook_id": notebook_id, "query": q}, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data = json.loads(decoded[6:])
                        if data['type'] == 'chunk':
                            print(data['text'], end='', flush=True)
                        elif data['type'] == 'status' and data['message']:
                            print(f"\n[Status: {data['message']}]")
        print("\n" + "-"*50)
        
    # 6. Fetch Study Guide
    print("\n--- Fetching Study Guide (Includes Flashcards, Quiz, Mindmap, Podcast) ---")
    while True:
        guide_res = requests.get(f"{BASE_URL}/api/notebooks/{notebook_id}/study-guide")
        if guide_res.status_code == 200:
            guide = guide_res.json()
            if guide and "summary" in guide:
                print("Study Guide Generated! It contains summary, flashcards, quizzes, etc.")
                break
        print("Waiting for Study Guide...")
        time.sleep(5)

    # 7. Delete resources
    print("\n--- Deleting Resources ---")
    docs = requests.get(f"{BASE_URL}/api/notebooks/{notebook_id}/documents").json()
    for d in docs:
        filename = d["filename"]
        res = requests.delete(f"{BASE_URL}/api/notebooks/{notebook_id}/documents", params={"filename": filename})
        print(f"Deleted {filename}: {res.status_code}")
        
    res = requests.delete(f"{BASE_URL}/api/notebooks/{notebook_id}")
    print(f"Deleted Notebook {notebook_id}: {res.status_code}")
    print("E2E Test Completed!")

if __name__ == "__main__":
    generate_test_data()
    main()
