import platform
import psutil
import subprocess
import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

MODEL_ZOO = {
    # Tier 1: VRAM > 16GB
    1: {
        "tier_name": "Tier 1 (High-End)",
        "model_tag": "qwen2.5:14b",
        "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
    },
    # Tier 2: VRAM 8GB - 16GB
    2: {
        "tier_name": "Tier 2 (Mid-Range)",
        "model_tag": "qwen2.5:7b",
        "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
    },
    # Tier 3: VRAM 4GB - 8GB
    3: {
        "tier_name": "Tier 3 (Entry-Level)",
        "model_tag": "qwen2.5:3b",
        "repo_id": "bartowski/Llama-3.2-1B-Instruct-GGUF",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf"
    },
    # Tier 4: VRAM < 4GB
    4: {
        "tier_name": "Tier 4 (CPU/Low VRAM)",
        "model_tag": "qwen2.5:0.5b",
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    }
}

class ModelZooManager:
    def __init__(self):
        self.os_name = platform.system()
        self.total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        self.vram_gb = 0
        self.has_cuda = False
        self.has_mps = False
        self.gpu_names = []
        self._detect_gpu()

    def _detect_gpu(self):
        self.gpu_names = []
        
        # 1. Phát hiện GPU trên Windows bằng wmic (để lấy danh sách đầy đủ bao gồm Intel, AMD, NVIDIA)
        if platform.system() == "Windows":
            try:
                import subprocess
                # Lấy tên GPU
                result_name = subprocess.run(["wmic", "path", "win32_VideoController", "get", "Name"], capture_output=True, text=True)
                if result_name.returncode == 0:
                    self.gpu_names = [line.strip() for line in result_name.stdout.split('\n')[1:] if line.strip()]
                
                # Lấy AdapterRAM
                result_ram = subprocess.run(["wmic", "path", "win32_VideoController", "get", "AdapterRAM"], capture_output=True, text=True)
                if result_ram.returncode == 0:
                    lines = [line.strip() for line in result_ram.stdout.split('\n') if line.strip() and line.strip().isdigit()]
                    if lines:
                        max_ram_bytes = max(int(ram) for ram in lines)
                        self.vram_gb = max_ram_bytes / (1024**3)
            except Exception:
                pass

        # 2. Thử dùng nvidia-smi để lấy VRAM chính xác hơn của NVIDIA (nếu có)
        try:
            import subprocess
            result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True)
            if result.returncode == 0:
                parts = result.stdout.strip().split('\n')[0].split(',')
                gpu_name = parts[0].strip()
                vram_mb = int(parts[1].strip())
                self.vram_gb = vram_mb / 1024
                self.has_cuda = True
                if gpu_name not in self.gpu_names:
                    self.gpu_names.append(gpu_name)
        except Exception:
            pass

        # 3. Phát hiện Apple Silicon trên macOS
        if platform.system() == "Darwin":
            try:
                import platform as pf
                if "arm" in pf.machine().lower() or "arm" in pf.processor().lower():
                    self.has_mps = True
                    self.gpu_names.append("Apple Silicon GPU (Metal)")
            except Exception:
                pass

        # 4. Kiểm tra xem có phải card NVIDIA không để gán has_cuda
        if any("nvidia" in name.lower() for name in self.gpu_names):
            self.has_cuda = True

    def get_tier(self):
        if self.vram_gb > 16:
            return 1
        elif self.vram_gb > 8:
            return 2
        elif self.vram_gb >= 4:
            return 3
        else:
            return 4

    def get_recommended_config(self):
        tier = self.get_tier()
        config = MODEL_ZOO[tier].copy()
        return config

    def check_build_tools(self) -> bool:
        """Kiểm tra xem C++ Build Tools có được cài đặt không."""
        if platform.system() != "Windows":
            return True # Linux/Mac thường có sẵn GCC/Clang
        try:
            # Tìm vswhere.exe
            vswhere_path = os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Microsoft Visual Studio", "Installer", "vswhere.exe")
            if os.path.exists(vswhere_path):
                result = subprocess.run([vswhere_path, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], capture_output=True, text=True)
                if result.stdout.strip():
                    return True
        except Exception:
            pass
        return False

    def setup_layer_1_and_2(self) -> bool:
        """Thử cài đặt thư viện llama-cpp-python. Trả về True nếu thành công."""
        try:
            import huggingface_hub
        except ImportError:
            print("[Auto-Setup] Đang cài đặt thư viện huggingface_hub...")
            subprocess.run(["uv", "pip", "install", "huggingface-hub"], check=True)
            
        has_tools = self.check_build_tools()
        
        try:
            import llama_cpp
            return True
        except ImportError:
            if has_tools:
                print("[Lớp 1] Phát hiện C++ Build Tools! Đang tự biên dịch llama-cpp-python từ mã nguồn để đạt hiệu năng tối đa...")
                try:
                    subprocess.run(["uv", "pip", "install", "llama-cpp-python", "--no-binary", "llama-cpp-python"], check=True)
                    return True
                except Exception as e:
                    print(f"[Lớp 1] Biên dịch thất bại: {e}. Đang chuyển sang Lớp 2...")
            
            print("[Lớp 2] Đang cài đặt llama-cpp-python (Pre-compiled wheels)...")
            try:
                subprocess.run(["uv", "pip", "install", "llama-cpp-python", "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"], check=True)
                return True
            except Exception as e:
                print(f"[Lớp 2] Cài đặt Pre-compiled thất bại: {e}")
                return False

    def test_llama_cpp(self, model_path: str) -> bool:
        """Kiểm thử khởi tạo mô hình. Trả về True nếu khởi chạy thành công (không bị lỗi AVX2)."""
        print("[Kiểm thử Lớp 2] Đang test khởi tạo mô hình bằng llama_cpp...")
        try:
            import ctypes
            # Thử gọi Llama
            from llama_cpp import Llama
            llm = Llama(model_path=model_path, n_gpu_layers=0, n_ctx=128, verbose=False)
            print("[Kiểm thử Lớp 2] THÀNH CÔNG! Lớp 1/2 chạy hoàn hảo.")
            return True
        except OSError as e:
            if "0xc000001d" in str(e) or "illegal instruction" in str(e).lower():
                print(f"[Kiểm thử Lớp 2] THẤT BẠI! Xung đột tập lệnh CPU (Lỗi 0xc000001d - thường do Wheel chứa AVX-512 mà CPU không hỗ trợ): {e}")
            else:
                print(f"[Kiểm thử Lớp 2] THẤT BẠI! Lỗi hệ thống: {e}")
            return False
        except Exception as e:
            print(f"[Kiểm thử Lớp 2] THẤT BẠI! Lỗi không xác định: {e}")
            return False

    def check_and_install_model(self, repo_id: str, filename: str) -> str:
        """Tải model từ HF về thư mục /models và trả về đường dẫn."""
        from huggingface_hub import hf_hub_download
        models_dir = os.path.join(os.getcwd(), "models")
        os.makedirs(models_dir, exist_ok=True)
        print(f"\n[Model Manager] Đang tải mô hình GGUF: \033[92m{filename}\033[0m")
        try:
            model_path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=models_dir, local_dir_use_symlinks=False)
            return model_path
        except Exception as e:
            print(f"[Lỗi] Quá trình tải {filename} thất bại: {str(e)}")
            return ""

    def setup_ollama_portable(self, model_tag: str):
        """LỚP 3: Tự động tải Ollama Portable, bật server ngầm, và pull model."""
        print("\n[LỚP 3 - Cứu cánh] Kích hoạt chế độ tải Ollama Portable dành cho CPU cũ...")
        bin_dir = os.path.join(os.getcwd(), "bin")
        os.makedirs(bin_dir, exist_ok=True)
        ollama_exe = os.path.join(bin_dir, "ollama.exe")
        
        # 1. Tải Ollama Portable nếu chưa có
        if not os.path.exists(ollama_exe):
            print("[Lớp 3] Đang tải Ollama Portable (Khoảng 150MB). Vui lòng đợi...")
            import urllib.request
            import zipfile
            import tempfile
            import sys
            
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = downloaded * 100 / total_size
                    sys.stdout.write(f"\r[Lớp 3] Tiến độ tải: {percent:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)")
                    sys.stdout.flush()
                    
            url = "https://ollama.com/download/ollama-windows-amd64.zip"
            zip_path = os.path.join(tempfile.gettempdir(), "ollama_portable.zip")
            urllib.request.urlretrieve(url, zip_path, reporthook=download_progress)
            print("\n[Lớp 3] Đang giải nén Ollama...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(bin_dir)
            os.remove(zip_path)
            
        # 2. Khởi động Ollama Serve ngầm nếu chưa chạy
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:11434", timeout=1)
        except:
            print("[Lớp 3] Đang khởi động AI Engine (Ollama)...")
            creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            env = os.environ.copy()
            subprocess.Popen([ollama_exe, "serve"], creationflags=creationflags, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            for _ in range(30):
                try:
                    urllib.request.urlopen("http://localhost:11434", timeout=1)
                    break
                except:
                    time.sleep(0.5)
        
        # 3. Kích hoạt Pull Model
        print(f"\n[Lớp 3] Hệ thống đang tải bộ não AI tương thích cho Ollama: \033[92m{model_tag}\033[0m")
        try:
            subprocess.run([ollama_exe, "pull", model_tag], check=True)
            print(f"[Lớp 3] Sẵn sàng phục vụ!")
        except Exception as e:
            print(f"[Lớp 3] Lỗi tải {model_tag}: {str(e)}")

    def auto_setup(self):
        config = self.get_recommended_config()
        print(f"--- Auto Hardware Profiler & Model Zoo (3-Layer Auto-Adaptation) ---")
        gpu_str = ", ".join(self.gpu_names) if self.gpu_names else "None"
        print(f"OS: {self.os_name} | RAM: {self.total_ram_gb:.1f} GB | GPUs: {gpu_str} (VRAM: {self.vram_gb:.1f} GB)")
        print(f"Assigned Tier: {config['tier_name']}")
        print(f"--------------------------------------------------------------------")
        
        # Thử Lớp 1 và Lớp 2
        # Nếu phát hiện GPU là AMD hoặc Intel (không phải Nvidia/Apple Silicon) trên Windows,
        # ta nên chuyển thẳng sang Lớp 3 (Ollama) vì Ollama hỗ trợ tăng tốc GPU AMD/Intel rất tốt (ROCm/Vulkan),
        # tránh phải cài đặt llama-cpp-python CPU chậm và dễ lỗi tập lệnh.
        has_amd_intel = any(any(brand in name.lower() for brand in ["amd", "radeon", "intel", "iris", "arc", "xe"]) for name in self.gpu_names)
        if has_amd_intel and not self.has_cuda and platform.system() == "Windows":
            print("\n[Điều phối viên] Phát hiện GPU AMD/Intel. Đang tự động chuyển hướng sang Lớp 3 (Ollama) để tối ưu hóa tăng tốc phần cứng...")
            layer_1_2_success = False
        else:
            layer_1_2_success = self.setup_layer_1_and_2()
        
        if layer_1_2_success:
            model_path = self.check_and_install_model(config['repo_id'], config['filename'])
            config['model_path'] = model_path
            
            # Kiểm thử xem CPU có chạy được Llama (Pre-compiled) không
            if model_path and self.test_llama_cpp(model_path):
                config['engine'] = 'llama-cpp-python'
                return config
            else:
                print("\n[Điều phối viên] Phát hiện phần cứng không tương thích với Lớp 1/2. Đang tự động chuyển hướng...")
        else:
            if not (has_amd_intel and not self.has_cuda and platform.system() == "Windows"):
                print("\n[Điều phối viên] Không thể cài đặt Lớp 1/2. Đang tự động chuyển hướng...")
 
        # Chuyển sang Lớp 3
        self.setup_ollama_portable(config['model_tag'])
        config['engine'] = 'ollama'
        return config

if __name__ == "__main__":
    manager = ModelZooManager()
    manager.auto_setup()
