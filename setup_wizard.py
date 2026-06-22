import os
import subprocess
import platform
import webbrowser
import time
import sys

def inject_docker_path():
    if platform.system() == "Windows":
        import winreg
        try:
            # 1. Quét biến PATH System mới nhất từ Registry
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"System\CurrentControlSet\Control\Session Manager\Environment") as key:
                sys_path = winreg.QueryValueEx(key, "Path")[0]
                for p in sys_path.split(os.pathsep):
                    if p and p not in os.environ["PATH"]:
                        os.environ["PATH"] += os.pathsep + p
        except Exception:
            pass
            
        try:
            # 2. Quét biến PATH User mới nhất từ Registry
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                usr_path = winreg.QueryValueEx(key, "Path")[0]
                for p in usr_path.split(os.pathsep):
                    if p and p not in os.environ["PATH"]:
                        os.environ["PATH"] += os.pathsep + p
        except Exception:
            pass

        # 3. Fallback cuối cùng: Cấu hình mặc định
        docker_bin = r"C:\Program Files\Docker\Docker\resources\bin"
        if os.path.exists(docker_bin) and docker_bin not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + docker_bin

def check_command(cmd_list):
    inject_docker_path()
    try:
        subprocess.run(cmd_list, capture_output=True, check=True)
        return True
    except Exception as e:
        return False

def get_docker_compose_cmd():
    if check_command(["docker", "compose", "version"]):
        return ["docker", "compose"]
    elif check_command(["docker-compose", "--version"]):
        return ["docker-compose"]
    return None

def is_docker_running():
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def auto_start_docker_desktop():
    os_name = platform.system()
    print("[THÔNG BÁO] Docker đang tắt. Đang tự động đánh thức Docker Desktop...")
    try:
        if os_name == "Windows":
            docker_path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
            if os.path.exists(docker_path):
                os.startfile(docker_path)
            else:
                return False
        elif os_name == "Darwin":
            os.system("open -a Docker")
        else:
            return False
            
        # Chờ Docker khởi động
        for i in range(30):
            time.sleep(2)
            if is_docker_running():
                print("[OK] Docker đã thức dậy thành công!")
                return True
            sys.stdout.write(".")
            sys.stdout.flush()
        print("\n[LỖI] Đợi Docker khởi động quá lâu (Timeout).")
        return False
    except Exception as e:
        print(f"\n[LỖI] Không thể tự bật Docker: {e}")
        return False

def install_docker():
    os_name = platform.system()
    print("\n--- [BƯỚC 1] KIỂM TRA DOCKER ---")
    
    compose_cmd = get_docker_compose_cmd()
    
    # Kịch bản 1: Đã có lệnh Docker, kiểm tra xem đã chạy chưa
    if check_command(["docker", "--version"]):
        if not is_docker_running():
            if not auto_start_docker_desktop():
                print("[CẢNH BÁO] Không thể tự bật Docker. Vui lòng mở phần mềm Docker Desktop bằng tay!")
                sys.exit(1)
                
        if compose_cmd is not None:
            print("[OK] Docker Engine đang chạy hoàn hảo.")
            return compose_cmd
    
    # Kịch bản 2: Không tìm thấy lệnh Docker (Chưa cài hoặc lỗi PATH)
    print("[CẢNH BÁO] Máy bạn chưa cài đặt Docker hoặc bị lỗi môi trường!")
    print("Đang thử tự động cài đặt Docker Desktop...")
    try:
        if os_name == "Windows":
            print("[LỖI] Lệnh cài tự động (winget) không khả dụng trên máy bạn.")
            print("Vui lòng tải và cài đặt Docker bằng tay tại: https://www.docker.com/products/docker-desktop/")
            sys.exit(1)
        elif os_name == "Darwin":
            subprocess.run(["brew", "install", "--cask", "docker"], check=True)
            print("\n[QUAN TRỌNG] Đã cài xong Docker!")
            print("Vui lòng mở ứng dụng Docker Desktop trong Launchpad để nó chạy nền, sau đó chạy lại script start.sh.")
            sys.exit(0)
        elif os_name == "Linux":
            os.system("curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh")
            print("[OK] Đã cài xong Docker Engine trên Linux.")
            return ["docker", "compose"]
    except Exception as e:
        print(f"[LỖI] Lỗi hệ thống: {e}")
        sys.exit(1)

def run_hardware_profiler():
    print("\n--- [BƯỚC 2] NHẬN DIỆN PHẦN CỨNG & AUTO-PULL MODEL AI ---")
    # Đảm bảo có thư viện uv để tải llama-cpp siêu tốc
    subprocess.run([sys.executable, "-m", "pip", "install", "uv", "--quiet"], check=False)
    
    sys.path.append(os.path.join(os.path.dirname(__file__), "src", "utils"))
    try:
        from hardware_profiler import ModelZooManager
        manager = ModelZooManager()
        # auto_setup sẽ tự tải Ollama Portable (nếu cần) và kéo Model GGUF / Ollama Model tùy cấu hình
        manager.auto_setup() 
    except Exception as e:
        print(f"[LỖI] Trình nhận diện phần cứng thất bại: {e}")

def start_docker_compose(compose_cmd):
    print("\n--- [BƯỚC 3] KHỞI ĐỘNG HỆ THỐNG ---")
    print("Đang nổ máy Backend, Frontend và Database (Redis)...")
    try:
        if platform.system() == "Darwin":
            cmd = compose_cmd + ["-f", "docker-compose.mac.yml", "up", "-d"]
            subprocess.run(cmd, check=True)
            print("[OK] Redis và Frontend đã chạy ngầm trong Docker!")
            
            print("\n[Mac] Đang tạo môi trường ảo và cài đặt thư viện cho Backend (Native)...")
            subprocess.run([sys.executable, "-m", "uv", "venv", ".venv"], check=False)
            subprocess.run([sys.executable, "-m", "uv", "pip", "install", "-r", "requirements.txt"], check=True)
            
            print("[Mac] Đang khởi động Backend trực tiếp trên hệ điều hành (hỗ trợ GPU Metal)...")
            uvicorn_exe = os.path.join(os.getcwd(), ".venv", "bin", "uvicorn")
            subprocess.Popen([uvicorn_exe, "src.api.api:app", "--host", "0.0.0.0", "--port", "8000"])
            print("[OK] Hệ thống đã chạy thành công!")
        else:
            cmd = compose_cmd + ["up", "-d"]
            subprocess.run(cmd, check=True)
            print("[OK] Hệ thống đã chạy ngầm thành công!")
    except Exception as e:
        print(f"[LỖI] Docker compose thất bại: {e}")
        sys.exit(1)

def open_browser():
    print("\n--- HOÀN TẤT ---")
    print("Mở giao diện ứng dụng sau 3 giây...")
    time.sleep(3)
    webbrowser.open("http://localhost:5173")

if __name__ == "__main__":
    print("========================================")
    print("   KHỞI CHẠY SETUP WIZARD THÔNG MINH    ")
    print("========================================")
    
    compose_cmd = install_docker()
    run_hardware_profiler()
    start_docker_compose(compose_cmd)
    open_browser()
    
    print("\n[CHÚC MỪNG] Toàn bộ hệ thống đã sẵn sàng!")
    print("Mẹo: Để xem log chạy ngầm, hãy gõ: docker-compose logs -f")
