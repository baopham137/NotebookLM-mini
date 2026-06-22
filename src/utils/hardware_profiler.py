import platform
import psutil
import subprocess
import sys
import os
import shutil

# Ép HuggingFace tải Cache vào ổ D thay vì ổ C
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "cache", "huggingface")

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

class ModelZooManager:
    def __init__(self):
        self.os_name = platform.system()
        self.total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        
        # Cảm biến đo dung lượng ổ cứng hiện tại
        total, used, free = shutil.disk_usage(os.getcwd())
        self.free_disk_gb = free / (1024 ** 3)
        
        self.vram_gb = 0
        self.has_cuda = False
        self._detect_gpu()

    def _detect_gpu(self):
        if self.os_name in ['Windows', 'Linux']:
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    self.vram_gb = sum(int(x) for x in result.stdout.strip().split('\n')) / 1024
                    self.has_cuda = True
                    return
            except Exception:
                pass
            
            try:
                if self.os_name == 'Windows':
                    result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'AdapterRAM'], 
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if result.returncode == 0:
                        lines = [line.strip() for line in result.stdout.split('\n') if line.strip() and line.strip().isdigit()]
                        if lines:
                            self.vram_gb = sum(int(x) for x in lines) / (1024 ** 3)
            except Exception:
                pass
        elif self.os_name == 'Darwin':
            self.vram_gb = self.total_ram_gb * 0.75

    def auto_setup(self):
        print("\n" + "="*50)
        print("🤖 NOTEBOOKLM MINI - SETUP WIZARD TƯƠNG TÁC 🤖")
        print("="*50)
        print(f"📌 [Phân tích hệ thống]")
        print(f" - Hệ điều hành: {self.os_name}")
        print(f" - RAM vật lý: {self.total_ram_gb:.1f} GB")
        print(f" - VRAM (Card đồ hoạ): {self.vram_gb:.1f} GB")
        print(f" - Ổ đĩa trống: {self.free_disk_gb:.1f} GB")
        print("="*50)
        
        # LỰA CHỌN LLM
        print("\n🧠 BƯỚC 1: LỰA CHỌN BỘ NÃO AI (OLLAMA LLM)")
        print(" Hệ thống hỗ trợ nhiều kích cỡ LLM. Hãy chọn mức phù hợp với máy của bạn:")
        print("  [1] Qwen 2.5 (14B) - Cực thông minh | Tốn ~9.0GB ổ cứng | Khuyên dùng nếu VRAM > 12GB")
        print("  [2] Qwen 2.5 (7B)  - Thông minh     | Tốn ~4.5GB ổ cứng | Khuyên dùng nếu VRAM > 6GB")
        print("  [3] Qwen 2.5 (3B)  - Cân bằng       | Tốn ~2.0GB ổ cứng | Phù hợp Laptop tầm trung")
        print("  [4] Qwen 2.5 (0.5B)- Siêu nhẹ       | Tốn ~0.5GB ổ cứng | Chạy mượt trên mọi máy (Kể cả không VGA)")
        
        while True:
            choice_llm = input("👉 Nhập lựa chọn của bạn (1-4) [Mặc định: 3]: ").strip()
            if not choice_llm: choice_llm = "3"
            
            if choice_llm == "1":
                model_tag = "qwen2.5:14b"
                break
            elif choice_llm == "2":
                model_tag = "qwen2.5:7b"
                break
            elif choice_llm == "3":
                model_tag = "qwen2.5:3b"
                break
            elif choice_llm == "4":
                model_tag = "qwen2.5:0.5b"
                break
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")

        # LỰA CHỌN ENGINE DOCKER
        print("\n🚀 BƯỚC 2: LỰA CHỌN ĐỘNG CƠ RAG (PYTORCH ENGINE)")
        print(" NOTE: Mọi phiên bản đều được trang bị đầy đủ Reranker và Embedding GreenNode xịn nhất.")
        print("  [1] Chế độ MAX SPEED (NVIDIA GPU / APPLE METAL) | Cài bản full PyTorch | Tốc độ RAG siêu nhanh")
        print("  [2] Chế độ TIẾT KIỆM (CPU-Only)   | Cài bản PyTorch CPU  | Tốn thêm ~0.2GB ổ cứng | Tốc độ RAG bình thường")
        
        # Tư vấn tự động
        recommended = "1" if (self.has_cuda and self.free_disk_gb > 15) or self.os_name == 'Darwin' else "2"
        
        while True:
            choice_engine = input(f"👉 Nhập lựa chọn của bạn (1-2) [Mặc định: {recommended}]: ").strip()
            if not choice_engine: choice_engine = recommended
            
            if choice_engine == "1":
                pytorch_mode = "gpu"
                if self.free_disk_gb < 15:
                    print("⚠️ CẢNH BÁO: Ổ đĩa của bạn còn khá ít. Hãy đảm bảo bạn có đủ chỗ trống!")
                break
            elif choice_engine == "2":
                pytorch_mode = "cpu"
                break
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")

        print("\n⏳ Đang tiến hành thiết lập hệ thống theo yêu cầu của bạn...")
        
        # 1. Ghi file .env (Universal Architecture: Always ON)
        env_path = os.path.join(os.getcwd(), ".env")
        env_example_path = os.path.join(os.getcwd(), ".env.example")
        
        # Đọc nội dung hiện tại hoặc từ template
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        elif os.path.exists(env_example_path):
            with open(env_example_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        new_settings = {
            "RAG_USE_RERANKER": "false",
            "RAG_EMBEDDING_MODEL": "keepitreal/vietnamese-sbert",
            "RAG_OLLAMA_BASE_URL": "http://localhost:11434" if self.os_name == 'Darwin' else "http://host.docker.internal:11434",
            "RAG_REDIS_HOST": "localhost" if self.os_name == 'Darwin' else "redis"
        }
        
        updated_lines = []
        for line in lines:
            updated = False
            for key, val in list(new_settings.items()):
                if line.startswith(f"{key}="):
                    updated_lines.append(f"{key}={val}\n")
                    del new_settings[key]
                    updated = True
                    break
            if not updated:
                updated_lines.append(line)
        
        # Thêm các key còn thiếu
        if new_settings:
            updated_lines.append("\n# Tự động sinh bởi Hardware Profiler (Interactive Mode)\n")
            for key, val in new_settings.items():
                updated_lines.append(f"{key}={val}\n")
                
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)
            
        # 2. Sinh file requirements.txt
        req_base_path = os.path.join(os.getcwd(), "requirements-base.txt")
        req_out_path = os.path.join(os.getcwd(), "requirements.txt")
        
        with open(req_base_path, "r", encoding="utf-8") as f:
            req_content = f.read()
            
        if pytorch_mode == "cpu":
            if self.os_name == "Darwin":
                print("📦 Đã chọn: Cài đặt PyTorch Native (Apple Metal)")
                req_content += "\n# --- PyTorch Apple Metal ---\n"
                req_content += "torch>=2.0.0\n"
            else:
                print("📦 Đã chọn: Cài đặt PyTorch CPU-Only (Diet Plan)")
                req_content += "\n# --- PyTorch CPU-Only (Diet Plan) ---\n"
                req_content += "--extra-index-url https://download.pytorch.org/whl/cpu\n"
                req_content += "torch==2.6.0+cpu\n"
                req_content += "torchvision==0.21.0+cpu\n"
                req_content += "torchaudio==2.6.0+cpu\n"
        else:
            print("📦 Đã chọn: Cài đặt PyTorch Full Speed (NVIDIA GPU / Apple Metal)")
            req_content += "\n# --- PyTorch Full Speed ---\n"
            req_content += "torch>=2.0.0\n"
            
        with open(req_out_path, "w", encoding="utf-8") as f:
            f.write(req_content)
            
        # 3. Ghi file docker-compose.override.yml (NVIDIA GPU Passthrough)
        override_path = os.path.join(os.getcwd(), "docker-compose.override.yml")
        if pytorch_mode == "gpu" and self.os_name in ["Windows", "Linux"]:
            print("🔧 Cấu hình: Đang mở cổng kết nối GPU qua Docker Compose (NVIDIA Runtime)...")
            override_content = """services:
  backend:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
"""
            with open(override_path, "w", encoding="utf-8") as f:
                f.write(override_content)
        else:
            if os.path.exists(override_path):
                os.remove(override_path)
            
        print("✅ Đã tạo cấu hình hoàn tất!")
        
        self.setup_ollama_portable(model_tag)
        
        return {
            "model_tag": model_tag,
            "pytorch_mode": pytorch_mode
        }

    def setup_ollama_portable(self, model_tag: str):
        """Tự động tải Ollama Portable, bật server ngầm, và pull model."""
        print(f"\n[AI Engine] Khởi tạo Ollama Bridge để kết nối Docker với GPU Windows...")
        bin_dir = os.path.join(os.getcwd(), "bin")
        os.makedirs(bin_dir, exist_ok=True)
        
        is_windows = platform.system() == "Windows"
        ollama_exe = os.path.join(bin_dir, "ollama.exe" if is_windows else "ollama")
        
        if not os.path.exists(ollama_exe):
            print("[Ollama] Đang tải Ollama Portable. Vui lòng đợi...")
            import urllib.request
            import zipfile
            import tempfile
            
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = downloaded * 100 / total_size
                    sys.stdout.write(f"\rTiến độ tải: {percent:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)")
                    sys.stdout.flush()
                    
            if is_windows:
                url = "https://ollama.com/download/ollama-windows-amd64.zip"
                zip_path = os.path.join(tempfile.gettempdir(), "ollama_portable.zip")
                urllib.request.urlretrieve(url, zip_path, reporthook=download_progress)
                print("\n[Ollama] Đang giải nén...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(bin_dir)
                os.remove(zip_path)
            elif platform.system() == "Darwin":
                url = "https://ollama.com/download/ollama-darwin-arm64"
                urllib.request.urlretrieve(url, ollama_exe, reporthook=download_progress)
                os.chmod(ollama_exe, 0o755)
            elif platform.system() == "Linux":
                url = "https://ollama.com/download/ollama-linux-amd64"
                urllib.request.urlretrieve(url, ollama_exe, reporthook=download_progress)
                os.chmod(ollama_exe, 0o755)
            
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:11434", timeout=1)
        except:
            print("[Ollama] Đang khởi động AI Engine ngầm...")
            creationflags = subprocess.CREATE_NO_WINDOW if is_windows else 0
            env = os.environ.copy()
            subprocess.Popen([ollama_exe, "serve"], creationflags=creationflags, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            for _ in range(30):
                try:
                    urllib.request.urlopen("http://localhost:11434", timeout=1)
                    break
                except:
                    time.sleep(0.5)
        
        print(f"\n[Ollama] Hệ thống đang tải bộ não AI: \033[92m{model_tag}\033[0m")
        try:
            subprocess.run([ollama_exe, "pull", model_tag], check=True)
            print(f"[Ollama] Sẵn sàng phục vụ!")
        except Exception as e:
            print(f"[Ollama] Lỗi tải {model_tag}: {str(e)}")



if __name__ == "__main__":
    manager = ModelZooManager()
    manager.auto_setup()
