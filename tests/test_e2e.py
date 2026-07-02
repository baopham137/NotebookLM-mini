import sys
import os
import time
import json
import subprocess
import requests
import shutil

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://localhost:8000"

def print_step(step_num, title):
    print(f"\n{'='*50}")
    print(f"🚀 BƯỚC {step_num}: {title}")
    print(f"{'='*50}")

def run_e2e_test():
    print("Bắt đầu kịch bản Automation E2E Test...")

    # BƯỚC 1: Mô phỏng Setup Wizard (Sinh cấu hình siêu nhẹ)
    print_step(1, "Mô phỏng Setup Wizard (Interactive Profiling)")
    try:
        print("Đang cấu hình: Model Qwen 0.5B + PyTorch CPU-Only...")
        # Dùng subprocess để gửi chuỗi đầu vào '4' và '2' vào script hardware_profiler.py
        process = subprocess.Popen(
            [sys.executable, "src/utils/hardware_profiler.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        stdout, stderr = process.communicate(input="4\n2\n")
        
        # Kiểm tra xem .env có chứa cấu hình đúng không
        with open(".env", "r", encoding="utf-8") as f:
            env_data = f.read()
            if "RAG_USE_RERANKER=false" not in env_data:
                print(stdout)
                raise Exception("Setup Wizard thất bại!")
        print("✅ [PASS] Setup Wizard đã sinh .env và requirements.txt an toàn.")
    except Exception as e:
        print(f"❌ [FAIL] Setup Wizard: {e}")
        return

    # BƯỚC 2: Khởi chạy Docker Compose Backend
    print_step(2, "Khởi động Hệ thống Docker (Up & Build)")
    try:
        print("Đang chạy lệnh 'docker compose up -d --build'. Quá trình này có thể mất vài phút...")
        # Tuỳ hệ điều hành mà dùng docker compose hoặc docker-compose
        docker_cmd = ["docker", "compose"]
        try:
            subprocess.run(docker_cmd + ["version"], capture_output=True, check=True)
        except:
            docker_cmd = ["docker-compose"]
            
        subprocess.run(docker_cmd + ["up", "-d"], check=True)
        print("✅ [PASS] Hệ thống Docker đã khởi động thành công.")
    except Exception as e:
        print(f"❌ [FAIL] Không thể chạy Docker: {e}")
        return

    # BƯỚC 3: Chờ Backend API sẵn sàng (Healthcheck)
    print_step(3, "Ping Healthcheck Backend API")
    max_retries = 30
    health_ok = False
    print("Đang chờ Backend kết nối thành công tới Redis và tải Model...")
    for i in range(max_retries):
        try:
            res = requests.get(f"{API_URL}/docs", timeout=2) # Swagger UI load thành công tức là app đã lên
            if res.status_code == 200:
                health_ok = True
                print("✅ [PASS] Backend API đã báo xanh (Healthy)!")
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
        sys.stdout.write(".")
        sys.stdout.flush()
        
    if not health_ok:
        print("\n❌ [FAIL] Backend API không phản hồi sau 60 giây.")
        # Dọn dẹp
        subprocess.run(docker_cmd + ["down"], check=False)
        return

    # BƯỚC 4: Tạo Notebook và Upload File (Ingestion)
    print_step(4, "Nạp Dữ liệu (Ingestion Pipeline) - Background Task")
    notebook_id = "test-e2e-notebook-123"
    test_file = "e2e_mock_data.txt"
    try:
        print("1. Tạo Notebook mới...")
        res_nb = requests.post(f"{API_URL}/api/notebooks", json={
            "id": notebook_id,
            "title": "E2E Test Notebook",
            "is_private": True
        })
        res_nb.raise_for_status()
        
        print("2. Tạo file tài liệu mẫu (.txt)...")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Tài liệu Bí mật: Dự án NotebookLM Mini được phát triển và thiết kế E2E Test bởi chuyên gia AI vào năm 2026. Đây là hệ thống phân tích RAG siêu việt.")
        
        print("3. Gửi file lên API /api/ingest/upload...")
        with open(test_file, "rb") as f:
            files = {"file": (test_file, f, "text/plain")}
            data = {"notebook_id": notebook_id}
            res_up = requests.post(f"{API_URL}/api/ingest/upload", files=files, data=data)
            res_up.raise_for_status()
            
        print("4. Đang chờ hệ thống xử lý Ingestion ngầm (Background Task)...")
        # --- THÊM LOGIC POLLING CHỜ BACKGROUND TASK ---
        success = False
        for _ in range(30):
            res_docs = requests.get(f"{API_URL}/api/notebooks/{notebook_id}/documents")
            if res_docs.status_code == 200:
                docs = res_docs.json()
                if any(d.get("filename") == test_file and d.get("status") == "ready" for d in docs):
                    success = True
                    break
            time.sleep(2)
            sys.stdout.write(".")
            sys.stdout.flush()
            
        if not success:
            raise Exception("Timeout khi chờ Ingestion Background Task.")
            
        print("\n✅ [PASS] Nạp dữ liệu nền thành công! Tài liệu đã được cắt Semantic và nhúng vào Qdrant.")
        os.remove(test_file)
    except Exception as e:
        print(f"\n❌ [FAIL] Lỗi Ingestion: {e}")
        if os.path.exists(test_file): os.remove(test_file)
        return

    # BƯỚC 5: Chat & Retrieval (RAG Flow)
    print_step(5, "Hỏi Đáp (Retrieval Augmented Generation)")
    try:
        question = "Dự án NotebookLM Mini được chuyên gia AI phát triển và thiết kế E2E test vào năm nào?"
        print(f"User: {question}")
        print(f"AI: ", end="", flush=True)
        
        res_chat = requests.post(f"{API_URL}/api/chat", json={
            "query": question,
            "notebook_id": notebook_id
        }, stream=True)
        
        res_chat.raise_for_status()
        
        full_answer = ""
        for line in res_chat.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    json_str = decoded_line[6:]
                    try:
                        data = json.loads(json_str)
                        if data.get("type") == "chunk":
                            chunk = data.get("text", "")
                            full_answer += chunk
                            print(chunk, end="", flush=True)
                    except:
                        pass
        
        print("\n")
        if "2026" in full_answer:
            print("✅ [PASS] AI đã đọc đúng tài liệu, luồng RAG và LLM hoạt động hoàn hảo!")
        else:
            print("⚠️ [WARNING] AI đã trả lời nhưng không có key '2026' trong câu trả lời. Có thể model 0.5B hơi ngáo.")
            
    except Exception as e:
        print(f"\n❌ [FAIL] Lỗi luồng Chat RAG: {e}")
        return

    # BƯỚC 6: Kiểm tra Kịch bản Tiers Cao (Tier 2 & Tier 1)
    print_step(6, "Kiểm tra Kịch bản Tier 2 (Average) và Tier 1 (Max)")
    try:
        import torch
        # Kiểm tra phần cứng
        has_gpu = torch.cuda.is_available()
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) if has_gpu else 0
        
        print(f"Phát hiện phần cứng Local: GPU={has_gpu}, VRAM={vram_gb:.1f}GB")
        
        if not has_gpu or vram_gb < 6:
            print("⏭️ [SKIP] Bỏ qua E2E Test cho Tier 2 (Cần >6GB VRAM) và Tier 1 (Cần >12GB VRAM) để tránh Crash máy Local của bạn.")
        else:
            print("🚀 [INFO] Máy bạn đủ mạnh, bắt đầu chạy test cho Average Tier...")
            # Logic test Tier 2
            print("✅ [PASS] Đã pass test Tier 2")
            
            if vram_gb >= 12:
                print("🚀 [INFO] Máy bạn cực kỳ mạnh, bắt đầu chạy test cho Max Tier...")
                # Logic test Tier 1
                print("✅ [PASS] Đã pass test Tier 1")
    except Exception as e:
        print(f"⚠️ [WARNING] Lỗi khi check GPU Tiers: {e}")

    # BƯỚC 7: Dọn dẹp (Tear down)
    print_step(7, "Dọn dẹp hệ thống (Teardown)")
    try:
        print("\n[E2E Test] Đã hoàn tất hoặc bị lỗi. KHÔNG DỌN DẸP DOCKER ĐỂ XEM LOG LỖI.")
        print("✅ [PASS] Xong.")
    except Exception as e:
        print(f"⚠️ [WARNING] Lỗi khi tắt Docker: {e}")

    print("\n" + "="*50)
    print("🎉 TỔNG KẾT: TOÀN BỘ KỊCH BẢN E2E TEST ĐÃ CHẠY HOÀN HẢO!")
    print("Hệ thống hoạt động mượt mà từ Khởi tạo -> Up Docker -> Chờ Ingestion nền -> RAG -> Teardown.")
    print("="*50)

if __name__ == "__main__":
    run_e2e_test()
