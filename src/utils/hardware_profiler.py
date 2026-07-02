import platform
import psutil
import subprocess
import sys
import os
import shutil

# Ép HuggingFace tải Cache vào ổ D thay vì ổ C và cấm kết nối Internet
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "cache", "huggingface")
# os.environ["HF_HUB_OFFLINE"] = "1" # Bỏ comment nếu muốn ép offline

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from src.utils.llama_manager import LlamaManager

class ModelZooManager:
    def __init__(self):
        self.os_name = platform.system()
        self.total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        
        # Cảm biến đo dung lượng ổ cứng hiện tại
        total, used, free = shutil.disk_usage(os.getcwd())
        self.free_disk_gb = free / (1024 ** 3)
        
        self.vram_gb = 0
        self.has_cuda = False
        self.gpu_name = "Unknown"
        self.recommended_tier = 2  # Mặc định: Thử Lớp 2 (Native)
        self._detect_gpu()

    def _detect_gpu(self):
        """Nhận diện phần cứng GPU: Tên card, VRAM, và phân Lớp (Tier) tự động."""
        if self.os_name in ['Windows', 'Linux']:
            # --- Bước 1: Thử nhận diện NVIDIA qua nvidia-smi ---
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if lines:
                        parts = lines[0].split(',')
                        self.gpu_name = parts[0].strip()
                        self.vram_gb = sum(int(line.split(',')[1].strip()) for line in lines) / 1024
                        self.has_cuda = True
                        self.recommended_tier = 2  # NVIDIA -> Thử Lớp 2 (llama-server CUDA)
                        return
            except Exception:
                pass
            
            # --- Bước 2: Không phải NVIDIA -> Đọc tên Card qua WMIC (Windows) ---
            try:
                if self.os_name == 'Windows':
                    # Đọc tên Card đồ họa
                    name_result = subprocess.run(
                        ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    if name_result.returncode == 0:
                        name_lines = [line.strip() for line in name_result.stdout.split('\n') 
                                      if line.strip() and line.strip().lower() != 'name']
                        if name_lines:
                            self.gpu_name = name_lines[0]
                    
                    # Đọc VRAM
                    ram_result = subprocess.run(
                        ['wmic', 'path', 'win32_VideoController', 'get', 'AdapterRAM'], 
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    if ram_result.returncode == 0:
                        ram_lines = [line.strip() for line in ram_result.stdout.split('\n') 
                                     if line.strip() and line.strip().isdigit()]
                        if ram_lines:
                            self.vram_gb = sum(int(x) for x in ram_lines) / (1024 ** 3)
                    
                    # Phân Lớp dựa trên tên Card
                    gpu_lower = self.gpu_name.lower()
                    if any(keyword in gpu_lower for keyword in ['intel', 'iris', 'uhd']):
                        self.recommended_tier = 3  # Intel iGPU -> Đi thẳng Lớp 3 (Ollama Vulkan)
                    elif any(keyword in gpu_lower for keyword in ['amd', 'radeon']):
                        self.recommended_tier = 3  # AMD -> Đi thẳng Lớp 3 (Ollama ROCm/Vulkan)
                    else:
                        self.recommended_tier = 3  # Card không xác định -> An toàn nhất là Lớp 3
                        
            except Exception:
                self.recommended_tier = 3  # Lỗi quét -> An toàn nhất là Lớp 3
                
        elif self.os_name == 'Darwin':
            # --- Mac: Apple Silicon (M1/M2/M3) hoặc Intel Mac ---
            self.vram_gb = self.total_ram_gb * 0.75  # Mac chia sẻ RAM cho GPU
            try:
                result = subprocess.run(
                    ['sysctl', '-n', 'machdep.cpu.brand_string'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if result.returncode == 0:
                    cpu_brand = result.stdout.strip()
                    if 'Apple' in cpu_brand:
                        self.gpu_name = f"Apple Silicon ({platform.machine()})"
                        self.recommended_tier = 2  # Apple Metal -> Lớp 2 chạy cực mượt
                    else:
                        self.gpu_name = f"Intel Mac ({cpu_brand})"
                        self.recommended_tier = 3  # Intel Mac cũ -> Lớp 3 an toàn hơn
            except Exception:
                self.gpu_name = "Mac (Unknown)"
                self.recommended_tier = 2  # Mặc định Mac thử Lớp 2

    def _auto_select_llm(self):
        """Tự động chọn LLM Model dựa trên VRAM/RAM. Không cần hỏi người dùng."""
        models_map = {
            "14b": {"repo": "Qwen/Qwen2.5-14B-Instruct-GGUF", "file": "qwen2.5-14b-instruct-q4_k_m.gguf", "tag": "qwen2.5:14b", "label": "Qwen 2.5 (14B)", "disk_gb": 9.0},
            "7b":  {"repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",  "file": "qwen2.5-7b-instruct-q4_k_m.gguf",  "tag": "qwen2.5:7b", "label": "Qwen 2.5 (7B)",  "disk_gb": 4.5},
            "3b":  {"repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",  "file": "qwen2.5-3b-instruct-q4_k_m.gguf",  "tag": "qwen2.5:3b", "label": "Qwen 2.5 (3B)",  "disk_gb": 2.0},
            "0.5b":{"repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF","file": "qwen2.5-0.5b-instruct-q4_k_m.gguf","tag": "qwen2.5:0.5b", "label": "Qwen 2.5 (0.5B)","disk_gb": 0.5},
        }
        
        # Quyết định dựa trên VRAM khả dụng (trừ ~1GB cho hệ thống)
        effective_vram = self.vram_gb - 1.0
        
        if effective_vram >= 12 and self.free_disk_gb >= 10:
            choice = "14b"
        elif effective_vram >= 6 and self.free_disk_gb >= 5:
            choice = "7b"
        elif effective_vram >= 2 and self.free_disk_gb >= 3:
            choice = "3b"
        else:
            choice = "0.5b"
        
        selected = models_map[choice]
        print(f"  🧠 LLM: {selected['label']} (Tốn ~{selected['disk_gb']}GB ổ cứng)")
        return selected

    def _auto_select_embedding(self):
        """Tự động chọn Embedding Model dựa trên RAM."""
        if self.total_ram_gb > 8:
            model = "GreenNode/GreenNode-Embedding-Large-VN-Mixed-V1"
            print("  📚 Embedding: GreenNode Large (Siêu chính xác)")
        else:
            model = "keepitreal/vietnamese-sbert"
            print("  📚 Embedding: Vietnamese-sBERT (Nhẹ, nhanh)")
        return model

    def _auto_select_reranker(self):
        """Tự động chọn Reranker Model dựa trên RAM."""
        if self.total_ram_gb > 8:
            model = "BAAI/bge-reranker-v2-m3"
            print("  🔍 Reranker: BGE-Reranker-v2-m3 (Chuẩn xác)")
        else:
            model = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
            print("  🔍 Reranker: mMiniLMv2 (Nhẹ, nhanh)")
        return model

    def _auto_select_whisper(self):
        """Tự động chọn Whisper Model Size dựa trên RAM."""
        if self.total_ram_gb >= 16:
            size = "medium"
            print("  🎙️ Whisper: Medium (Chính xác cao)")
        elif self.total_ram_gb >= 8:
            size = "small"
            print("  🎙️ Whisper: Small (Cân bằng)")
        else:
            size = "base"
            print("  🎙️ Whisper: Base (Siêu nhẹ)")
        return size

    def _auto_select_vision(self):
        """Tự động chọn Vision Model dựa trên VRAM và RAM."""
        # Ước lượng VRAM trống
        effective_vram = self.vram_gb - 1.0
        
        if effective_vram >= 8.0 and self.total_ram_gb >= 16:
            model = "llama3.2-vision"
            print("  👁️ Vision: Llama 3.2 Vision 11B (Siêu nét, cực nặng)")
        elif effective_vram >= 4.0 and self.total_ram_gb >= 8:
            model = "llava"
            print("  👁️ Vision: LLaVA 7B (Chi tiết tốt)")
        else:
            model = "moondream"
            print("  👁️ Vision: Moondream 1.6B (Siêu tốc, siêu nhẹ)")
        return model

    def auto_setup(self):
        """Khởi tạo lần đầu hoàn toàn tự động. Không yêu cầu input từ người dùng."""
        print("\n" + "="*50)
        print("🤖 NOTEBOOKLM MINI - KHỞI TẠO TỰ ĐỘNG 🤖")
        print("="*50)
        print(f"📌 [Phân tích hệ thống]")
        print(f" - Hệ điều hành: {self.os_name}")
        print(f" - RAM vật lý: {self.total_ram_gb:.1f} GB")
        print(f" - Card đồ hoạ: {self.gpu_name}")
        print(f" - VRAM: {self.vram_gb:.1f} GB")
        print(f" - Ổ đĩa trống: {self.free_disk_gb:.1f} GB")
        
        # Hiển thị Lớp được chọn
        tier_labels = {
            2: "Lớp 2 (Native - CUDA/Metal)",
            3: "Lớp 3 (Ollama - Vulkan/ROCm/Auto)"
        }
        print(f" - 🎯 Lớp khuyến nghị: {tier_labels.get(self.recommended_tier, 'Lớp 3')}")
        print("="*50)
        
        # === TỰ ĐỘNG CHỌN TẤT CẢ MODEL ===
        print("\n⚙️ [Tự động lựa chọn bộ Model tối ưu cho cấu hình của bạn]")
        
        selected_model = self._auto_select_llm()
        embedding_model = self._auto_select_embedding()
        reranker_model = self._auto_select_reranker()
        whisper_size = self._auto_select_whisper()
        vision_model = self._auto_select_vision()

        # Ghi cấu hình vào .env
        self._write_env_config(embedding_model, reranker_model, whisper_size, vision_model)

        print("\n⏳ Đang tiến hành thiết lập hệ thống tự động...")
        
        # 1. Sinh file requirements.txt
        self._generate_requirements()
            
        # 2. Cơ chế Fallback 3 Lớp: Cài đặt AI Engine
        llama = LlamaManager()
        engine_installed = None
        server_exe = None
        model_path = None
        
        if self.recommended_tier == 2:
            print("\n⏳ [Điều phối viên] Thử nghiệm Lớp 1 (Tự động biên dịch từ mã nguồn)...")
            if llama.setup_layer_1():
                model_path = llama.download_model(selected_model["repo"], selected_model["file"])
                if llama.test_llama_cpp(model_path):
                    engine_installed = "llama-cpp-python"
                    print("\n✅ Lớp 1 cài đặt thành công!")
                else:
                    print("\n⚠️ Lớp 1 thất bại (Xung đột AVX). Chuyển sang Lớp 2...")
            
            if engine_installed is None:
                print("\n⏳ [Điều phối viên] Đang cài đặt Lớp 2 (llama-server Native)...")
                server_exe = llama.setup_llama_server(has_cuda=False, has_vulkan=self.has_cuda)
                model_path = llama.download_model(selected_model["repo"], selected_model["file"])
                engine_installed = "llama-server"
                print("\n✅ Lớp 2 cài đặt thành công!")
        else:
            print("\n⏳ [Điều phối viên] Hệ thống yêu cầu sử dụng Lớp 3 (Ollama)...")
            if llama.setup_ollama():
                engine_installed = "ollama"
                model_path = selected_model["tag"]
                print("\n✅ Lớp 3 (Ollama) đã được cài đặt và kích hoạt!")
            else:
                print("\n❌ Cài đặt Ollama thất bại!")
        
        print("\n✅ Đã tạo cấu hình và thiết lập AI engine hoàn tất!")
        
        return {
            "engine_installed": engine_installed,
            "server_exe": server_exe,
            "model_path": model_path,
            "has_cuda": self.has_cuda,
            "has_mac_gpu": self.os_name == 'Darwin',
            "recommended_tier": self.recommended_tier,
            "gpu_name": self.gpu_name,
            "selected_llm": selected_model,
            "whisper_size": whisper_size,
        }

    def _write_env_config(self, embedding_model, reranker_model, whisper_size, vision_model):
        """Ghi cấu hình model đã chọn vào file .env."""
        import re
        env_path = os.path.join(os.getcwd(), ".env")
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_content = f.read()
        
        # Cập nhật hoặc thêm các biến cấu hình
        config_updates = {
            "RAG_EMBEDDING_MODEL": embedding_model,
            "RAG_RERANKER_MODEL": reranker_model,
            "RAG_VISION_MODE": "ollama",
            "RAG_VISION_MODEL": vision_model,
            "RAG_AUDIO_MODEL": whisper_size,
        }
        
        for key, value in config_updates.items():
            if key in env_content:
                env_content = re.sub(rf'{key}=.*', f'{key}={value}', env_content)
            else:
                env_content += f"\n{key}={value}\n"
        
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)

    def _generate_requirements(self):
        """Sinh file requirements.txt với PyTorch phù hợp phần cứng."""
        req_base_path = os.path.join(os.getcwd(), "requirements-base.txt")
        req_out_path = os.path.join(os.getcwd(), "requirements.txt")
        
        with open(req_base_path, "r", encoding="utf-8") as f:
            req_content = f.read()
        
        # Chốt cứng llvmlite để tránh lỗi trên Python 3.13.1
        if "llvmlite" not in req_content:
            req_content += "\n# Fix: Chốt phiên bản llvmlite cho Python 3.13+\nllvmlite>=0.43.0\n"
            
        pytorch_mode = "gpu" if self.has_cuda else "cpu"
        
        if pytorch_mode == "cpu":
            if self.os_name == "Darwin":
                print("📦 PyTorch: Apple Metal (Native)")
                req_content += "\n# --- PyTorch Apple Metal ---\n"
                req_content += "torch>=2.0.0\n"
            else:
                print("📦 PyTorch: CPU-Only (Diet Plan)")
                req_content += "\n# --- PyTorch CPU-Only (Diet Plan) ---\n"
                req_content += "--extra-index-url https://download.pytorch.org/whl/cpu\n"
                req_content += "torch==2.6.0+cpu\n"
                req_content += "torchvision==0.21.0+cpu\n"
                req_content += "torchaudio==2.6.0+cpu\n"
        else:
            print("📦 PyTorch: Full Speed (NVIDIA GPU)")
            req_content += "\n# --- PyTorch Full Speed ---\n"
            req_content += "torch>=2.0.0\n"
            
        with open(req_out_path, "w", encoding="utf-8") as f:
            f.write(req_content)

if __name__ == "__main__":
    manager = ModelZooManager()
    manager.auto_setup()
