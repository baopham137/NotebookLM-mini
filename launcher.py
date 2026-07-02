import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
import tarfile
import tempfile
import webbrowser
import time
import shutil

# Phải import các util từ code hiện tại, PyInstaller sẽ tự bundle các file này
from src.utils.hardware_profiler import ModelZooManager

def download_uv(bin_dir):
    is_win = platform.system() == "Windows"
    uv_exe = os.path.join(bin_dir, "uv.exe" if is_win else "uv")
    if os.path.exists(uv_exe):
        return uv_exe
        
    print("[Launcher] Đang tải uv (Python Package Manager)...")
    
    if is_win:
        url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    elif platform.system() == "Darwin":
        if platform.machine() == "arm64":
            url = "https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz"
        else:
            url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz"
    else:
        url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
        
    temp_path = os.path.join(tempfile.gettempdir(), "uv_download")
    urllib.request.urlretrieve(url, temp_path)
    
    if url.endswith(".zip"):
        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('uv.exe'):
                    file_info.filename = 'uv.exe'
                    zip_ref.extract(file_info, bin_dir)
    else:
        with tarfile.open(temp_path, 'r:gz') as tar_ref:
            for member in tar_ref.getmembers():
                if member.name.endswith('uv'):
                    member.name = 'uv'
                    tar_ref.extract(member, bin_dir)
                    os.chmod(os.path.join(bin_dir, 'uv'), 0o755)
    os.remove(temp_path)
    return uv_exe



def ollama_pull_model(model_name):
    """Tải (pull) model trên Ollama nếu chưa có."""
    try:
        print(f"[Launcher] Đang kiểm tra model Ollama: {model_name}...")
        # Kiểm tra model đã có chưa
        result = subprocess.run(
            ['ollama', 'list'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if model_name in result.stdout:
            print(f"[Launcher] ✅ Model {model_name} đã có sẵn.")
            return True
        
        # Tải model
        print(f"[Launcher] ⬇️ Đang tải model {model_name} trên Ollama...")
        subprocess.run(['ollama', 'pull', model_name], check=True)
        print(f"[Launcher] ✅ Tải model {model_name} hoàn tất!")
        return True
    except Exception as e:
        print(f"[Launcher] ❌ Lỗi khi tải model {model_name}: {e}")
        return False


def try_llama_server(llama_exe, model_path, config):
    """Thử khởi chạy llama-server (Lớp 2). Trả về process nếu thành công, None nếu thất bại."""
    print("\n[Launcher] 🚀 Đang thử khởi chạy Lớp 2 (Native llama-server)...")
    
    llama_cmd = [llama_exe, "-m", model_path, "--host", "127.0.0.1", "--port", "8080", "-c", "4096"]
    if config["has_cuda"] or config["has_mac_gpu"]:
        llama_cmd.extend(["-ngl", "99"])
    else:
        llama_cmd.extend(["-ngl", "0"])
    
    try:
        llama_process = subprocess.Popen(
            llama_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # Chờ 3 giây để xem process có bị văng (crash) không
        time.sleep(3)
        
        if llama_process.poll() is not None:
            # Process đã thoát -> Crash rồi!
            stderr_output = llama_process.stderr.read().decode('utf-8', errors='ignore')
            print(f"[Launcher] ⚠️ Lớp 2 thất bại! Lỗi: {stderr_output[:200]}")
            return None
        
        print("[Launcher] ✅ Lớp 2 (llama-server) khởi chạy thành công!")
        return llama_process
        
    except Exception as e:
        print(f"[Launcher] ⚠️ Lớp 2 thất bại! Lỗi: {e}")
        return None


def start_ollama_llm(config):
    """Khởi chạy LLM qua Ollama (Lớp 3). Trả về tên model Ollama đang chạy."""
    print("\n[Launcher] 🔄 Chuyển sang Lớp 3 (Ollama)...")
    
    # Xác định model Ollama phù hợp dựa trên cấu hình đã chọn
    selected_llm = config.get("selected_llm", {})
    llm_file = selected_llm.get("file", "")
    
    if "14b" in llm_file:
        ollama_model = "qwen2.5:14b"
    elif "7b" in llm_file:
        ollama_model = "qwen2.5:7b"
    elif "3b" in llm_file:
        ollama_model = "qwen2.5:3b"
    else:
        ollama_model = "qwen2.5:0.5b"
    
    # Tải model LLM
    ollama_pull_model(ollama_model)
    
    # Đã loại bỏ việc tải sẵn moondream. Moondream sẽ tự động được tải lần đầu khi user ném ảnh vào.
    
    # Khởi chạy Ollama serve ngầm (nếu chưa chạy)
    try:
        subprocess.Popen(
            ['ollama', 'serve'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)
    except Exception:
        pass  # Ollama có thể đã chạy sẵn dưới dạng service
    
    print(f"[Launcher] ✅ Lớp 3 (Ollama) đã sẵn sàng với model: {ollama_model}")
    return ollama_model


def main():
    print("========================================")
    print("   KHỞI CHẠY NOTEBOOKLM MINI STANDALONE ")
    print("========================================")
    
    bin_dir = os.path.abspath("bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    # 1. Cấu hình phần cứng và tải LLM (Zero-Click: Tự động hoàn toàn)
    manager = ModelZooManager()
    config = manager.auto_setup()
    
    # 2. Chuẩn bị môi trường Python bằng uv
    uv_exe = download_uv(bin_dir)
    
    print("\n[Launcher] Đang thiết lập môi trường Python ảo...")
    subprocess.run([uv_exe, "python", "install", "3.12"], check=True)
    if not os.path.exists(".venv"):
        subprocess.run([uv_exe, "venv", "--python", "3.12"], check=True)
    
    print("\n[Launcher] Đang cài đặt các thư viện cần thiết...")
    subprocess.run([uv_exe, "pip", "install", "-r", "requirements.txt"], check=True)
    
    # --- Cấu hình FFmpeg ---
    print("\n[Launcher] Đang cấu hình FFmpeg...")
    is_win = platform.system() == "Windows"
    python_exe = os.path.join(".venv", "Scripts", "python.exe") if is_win else os.path.join(".venv", "bin", "python")
    try:
        ffmpeg_cmd = [python_exe, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True, timeout=15)
        ffmpeg_exe = result.stdout.strip()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            bin_dir = os.path.abspath("bin")
            target_ffmpeg = os.path.join(bin_dir, "ffmpeg.exe" if is_win else "ffmpeg")
            if not os.path.exists(target_ffmpeg):
                shutil.copy2(ffmpeg_exe, target_ffmpeg)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            print(f"[Launcher] Đã cập nhật PATH với FFmpeg: {bin_dir}")
    except subprocess.TimeoutExpired:
        print("[Launcher] Cảnh báo: Cấu hình FFmpeg quá lâu (Timeout). Sẽ bỏ qua bước này.")
    except Exception as e:
        print(f"[Launcher] Cảnh báo: Không thể nạp FFmpeg tự động ({e})")
        
    # --- Preload Core AI Models ---
    print("\n[Launcher] Đang tải trước các mô hình cốt lõi (Embedding, Reranker)...")
    try:
        subprocess.run([python_exe, "-m", "src.utils.preload"], check=True)
    except Exception as e:
        print(f"[Launcher] Lỗi khi tải mô hình cốt lõi: {e}")
    
    # ============================================================
    # 3. CƠ CHẾ 3 LỚP: Khởi chạy AI Engine
    # ============================================================
    engine_installed = config.get("engine_installed")
    llama_process = None
    ollama_model = None
    using_ollama = False
    
    if engine_installed == "llama-cpp-python":
        print("\n[Launcher] 🚀 Lớp 1 (llama-cpp-python) đã được chọn. Khởi chạy qua thư viện Python...")
        llama_cmd = [python_exe, "-m", "llama_cpp.server", "--model", config["model_path"], "--host", "127.0.0.1", "--port", "8080", "--n_ctx", "4096"]
        if config.get("has_cuda") or config.get("has_mac_gpu"):
            llama_cmd.extend(["--n_gpu_layers", "99"])
        else:
            llama_cmd.extend(["--n_gpu_layers", "0"])
            
        try:
            llama_process = subprocess.Popen(llama_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(3)
            if llama_process.poll() is not None:
                stderr_output = llama_process.stderr.read().decode('utf-8', errors='ignore')
                print(f"[Launcher] ⚠️ Lớp 1 thất bại lúc khởi chạy ngầm! Lỗi: {stderr_output[:200]}")
                print("[Launcher] Tự động chuyển sang Lớp 3 (Ollama)...")
                ollama_model = start_ollama_llm(config)
                using_ollama = True
            else:
                print("[Launcher] ✅ Lớp 1 (llama-cpp-python) khởi chạy thành công!")
        except Exception as e:
            print(f"[Launcher] ⚠️ Lớp 1 thất bại: {e}. Tự động chuyển sang Lớp 3 (Ollama)...")
            ollama_model = start_ollama_llm(config)
            using_ollama = True

    elif engine_installed == "llama-server":
        # --- Thử Lớp 2 (Native llama-server) ---
        llama_process = try_llama_server(
            config["server_exe"], config["model_path"], config
        )
        
        if llama_process is None:
            # Lớp 2 thất bại -> Fallback sang Lớp 3 (Ollama)
            print("[Launcher] 🔄 Lớp 2 thất bại. Tự động chuyển sang Lớp 3 (Ollama)...")
            ollama_model = start_ollama_llm(config)
            using_ollama = True
    elif engine_installed == "ollama":
        # --- Lớp 3 (Ollama) ngay từ đầu cho Intel/AMD ---
        print(f"\n[Launcher] 🎯 Đi thẳng Lớp 3 (Ollama)")
        ollama_model = start_ollama_llm(config)
        using_ollama = True
    else:
        print("\n[Launcher] ❌ Cảnh báo: Không có Engine nào được khởi chạy!")
    
    # 4. Chạy Backend
    print("\n[Launcher] Đang khởi động Backend Server...")
    uvicorn_exe = os.path.join(".venv", "Scripts", "uvicorn.exe") if is_win else os.path.join(".venv", "bin", "uvicorn")
    
    # Cập nhật biến môi trường để Backend biết đang dùng Lớp nào
    if using_ollama:
        os.environ["RAG_LLAMA_SERVER_URL"] = "http://127.0.0.1:11434"  # Ollama port
        os.environ["RAG_LLM_PROVIDER"] = "ollama"
        if ollama_model:
            os.environ["RAG_OLLAMA_MODEL"] = ollama_model
    
    backend_cmd = [uvicorn_exe, "src.api.api:app", "--host", "127.0.0.1", "--port", "8000"]
    backend_process = subprocess.Popen(backend_cmd)
    
    # 5. Mở trình duyệt
    print("\n[Launcher] Đang chờ Backend Server sẵn sàng...")
    import urllib.error
    max_retries = 60
    for _ in range(max_retries):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000", timeout=1)
            break
        except urllib.error.URLError:
            time.sleep(1)
            
    print("\n[Launcher] Hoàn tất! Đang mở giao diện trên trình duyệt...")
    webbrowser.open("http://127.0.0.1:8000")
    
    # Hiển thị thông tin chế độ đang chạy
    if using_ollama:
        print(f"\n[INFO] 🎯 Đang chạy ở Lớp 3 (Ollama) với model: {ollama_model}")
    else:
        print(f"\n[INFO] 🚀 Đang chạy ở Lớp 2 (Native llama-server)")
    
    print("[INFO] Nhấn Ctrl+C để tắt toàn bộ hệ thống.")
    try:
        backend_process.wait()
    except KeyboardInterrupt:
        print("\n[INFO] Đang tắt hệ thống...")
        if llama_process:
            llama_process.terminate()
        backend_process.terminate()

if __name__ == "__main__":
    main()
