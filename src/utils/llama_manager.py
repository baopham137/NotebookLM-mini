import os
import sys
import platform
import urllib.request
import zipfile
import tempfile
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LLAMA_CPP_VERSION = "b4661"
LLAMA_CPP_BASE_URL = f"https://github.com/ggerganov/llama.cpp/releases/download/{LLAMA_CPP_VERSION}"

class LlamaManager:
    def __init__(self, bin_dir="bin", models_dir="models"):
        self.bin_dir = os.path.abspath(bin_dir)
        self.models_dir = os.path.abspath(models_dir)
        os.makedirs(self.bin_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        self.is_windows = platform.system() == "Windows"
        self.is_mac = platform.system() == "Darwin"
        self.server_exe = os.path.join(self.bin_dir, "llama-server.exe" if self.is_windows else "llama-server")

    def download_progress(self, block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = downloaded * 100 / total_size
            sys.stdout.write(f"\rTiến độ tải: {percent:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)")
            sys.stdout.flush()

    def get_download_url(self, has_cuda=False, has_vulkan=False):
        if self.is_mac:
            if platform.machine() == "arm64":
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-macos-arm64.zip"
            else:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-macos-x64.zip"
        elif self.is_windows:
            if has_cuda:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-win-cuda-cu12.4-x64.zip"
            elif has_vulkan:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-win-vulkan-x64.zip"
            else:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-win-avx2-x64.zip"
        else:
            return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-ubuntu-x64.zip"

    def setup_llama_server(self, has_cuda=False, has_vulkan=False):
        if os.path.exists(self.server_exe):
            logger.info("[llama.cpp] Server executable đã có sẵn.")
            return self.server_exe

        url = self.get_download_url(has_cuda, has_vulkan)
        logger.info(f"[llama.cpp] Đang tải llama-server từ {url}...")
        
        zip_path = os.path.join(tempfile.gettempdir(), "llama_cpp.zip")
        try:
            urllib.request.urlretrieve(url, zip_path, reporthook=self.download_progress)
            print("\n[llama.cpp] Đang giải nén...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    extracted_path = zip_ref.extract(file_info, self.bin_dir)
                    if not self.is_windows and file_info.filename.endswith('llama-server'):
                        os.chmod(extracted_path, 0o755)
            
            logger.info("[llama.cpp] Cài đặt thành công!")
        except Exception as e:
            logger.error(f"[llama.cpp] Lỗi khi tải: {e}")
            raise e
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except:
                    pass
                
        return self.server_exe

    def download_model(self, model_repo: str, model_filename: str):
        target_path = os.path.join(self.models_dir, model_filename)
        if os.path.exists(target_path):
            logger.info(f"[Model] Mô hình {model_filename} đã có sẵn.")
            return target_path
            
        url = f"https://huggingface.co/{model_repo}/resolve/main/{model_filename}"
        logger.info(f"[Model] Đang tải mô hình từ {url}...")
        
        try:
            urllib.request.urlretrieve(url, target_path, reporthook=self.download_progress)
            print("\n")
            logger.info(f"[Model] Tải thành công: {target_path}")
        except Exception as e:
            logger.error(f"[Model] Lỗi khi tải mô hình: {e}")
            if os.path.exists(target_path):
                os.remove(target_path)
            raise e
                
        return target_path

    def check_build_tools(self) -> bool:
        """Kiểm tra xem C++ Build Tools có được cài đặt không."""
        if not self.is_windows:
            return True # Linux/Mac thường có sẵn GCC/Clang
        try:
            vswhere_path = os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Microsoft Visual Studio", "Installer", "vswhere.exe")
            if os.path.exists(vswhere_path):
                result = subprocess.run([vswhere_path, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], capture_output=True, text=True)
                if result.stdout.strip():
                    return True
        except Exception:
            pass
        return False

    def setup_layer_1(self) -> bool:
        """Lớp 1: Thử cài đặt llama-cpp-python từ mã nguồn nếu có Build Tools."""
        try:
            import llama_cpp
            logger.info("[Lớp 1] Thư viện llama-cpp-python đã có sẵn.")
            return True
        except Exception as e:
            logger.warning(f"[Lớp 1] Lỗi import llama_cpp (có thể do thiếu DLL): {e}")
            pass

        if self.check_build_tools():
            logger.info("[Lớp 1] Phát hiện C++ Build Tools! Đang tự biên dịch llama-cpp-python từ mã nguồn để đạt hiệu năng tối đa...")
            try:
                subprocess.run(["uv", "pip", "install", "llama-cpp-python", "--no-binary", "llama-cpp-python", "--force-reinstall"], check=True)
                return True
            except Exception as e:
                logger.error(f"[Lớp 1] Biên dịch thất bại: {e}. Sẽ sử dụng Lớp 2 (llama-server)...")
        return False

    def test_llama_cpp(self, model_path: str) -> bool:
        """Kiểm thử khởi tạo mô hình bằng llama-cpp-python."""
        logger.info("[Kiểm thử Lớp 1] Đang test khởi tạo mô hình bằng llama_cpp...")
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=model_path, n_gpu_layers=0, n_ctx=128, verbose=False)
            logger.info("[Kiểm thử Lớp 1] THÀNH CÔNG! Lớp 1 chạy hoàn hảo.")
            return True
        except OSError as e:
            if "0xc000001d" in str(e) or "illegal instruction" in str(e).lower():
                logger.error(f"[Kiểm thử Lớp 1] THẤT BẠI! Xung đột tập lệnh CPU (Lỗi 0xc000001d): {e}")
            else:
                logger.error(f"[Kiểm thử Lớp 1] THẤT BẠI! Lỗi hệ thống: {e}")
            return False
        except Exception as e:
            logger.error(f"[Kiểm thử Lớp 1] THẤT BẠI! Lỗi không xác định: {e}")
            return False

    def setup_ollama(self) -> bool:
        """Lớp 3: Tải và cài đặt Ollama."""
        logger.info("[Lớp 3] Đang kiểm tra Ollama...")
        # Check if ollama is already installed
        try:
            result = subprocess.run(['ollama', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=self.is_windows)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass
            
        logger.info("[Lớp 3] Ollama chưa được cài đặt. Đang tiến hành cài đặt tự động...")
        try:
            if self.is_windows:
                setup_url = "https://ollama.com/download/OllamaSetup.exe"
                setup_path = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
                logger.info(f"[Lớp 3] Đang tải Ollama từ {setup_url}...")
                urllib.request.urlretrieve(setup_url, setup_path, reporthook=self.download_progress)
                print("\n[Lớp 3] Đang cài đặt Ollama (Silent Mode)...")
                subprocess.run([setup_path, '/SILENT'], check=True, timeout=300)
                try:
                    os.remove(setup_path)
                except:
                    pass
                import time
                time.sleep(5)
            else:
                subprocess.run(['bash', '-c', 'curl -fsSL https://ollama.com/install.sh | sh'], check=True, timeout=300)
            
            # Verify installation
            try:
                subprocess.run(['ollama', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=self.is_windows)
                logger.info("[Lớp 3] ✅ Cài đặt Ollama thành công!")
                return True
            except FileNotFoundError:
                logger.warning("[Lớp 3] ⚠️ Cài đặt Ollama xong nhưng không tìm thấy lệnh 'ollama'. Có thể cần khởi động lại Terminal.")
                return False
        except Exception as e:
            logger.error(f"[Lớp 3] ❌ Lỗi khi cài đặt Ollama: {e}")
            return False

