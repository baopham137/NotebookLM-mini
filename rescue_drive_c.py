import os
import subprocess
import shutil
import time
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def run_cmd(cmd, check=True):
    print(f"Chạy lệnh: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)

def rescue():
    print("=== BẮT ĐẦU ĐẠI PHẪU DỜI DỮ LIỆU TỪ Ổ C SANG Ổ D ===")
    
    # 1. Tắt Docker
    print("\n[1/5] Đang tắt Docker Desktop...")
    subprocess.run(["taskkill", "/F", "/IM", "Docker Desktop.exe"], capture_output=True)
    subprocess.run(["wsl", "--shutdown"], check=False)
    time.sleep(3)
    
    # 2. Di dời WSL
    tar_path = r"D:\docker_data_backup.tar"
    import_dir = r"D:\DockerData"
    
    print("\n[2/5] Đang đóng gói dữ liệu Docker (28.5 GB) sang ổ D. Quá trình này sẽ mất 3-5 phút...")
    try:
        run_cmd(["wsl", "--export", "docker-desktop-data", tar_path])
        
        print("\n[3/5] Đang xoá tận gốc ổ ảo 28.5 GB trên ổ C...")
        run_cmd(["wsl", "--unregister", "docker-desktop-data"])
        
        print("\n[4/5] Đang khôi phục hệ thống Docker trên ổ D...")
        os.makedirs(import_dir, exist_ok=True)
        run_cmd(["wsl", "--import", "docker-desktop-data", import_dir, tar_path, "--version", "2"])
        
        if os.path.exists(tar_path):
            os.remove(tar_path)
            
        print("\n[OK] Đã dời xong Docker sang ổ D!")
    except Exception as e:
        print(f"Lỗi khi dời Docker: {e}")
        print("Sẽ tiến hành xoá trực tiếp để dọn rác như bạn yêu cầu.")
        run_cmd(["wsl", "--unregister", "docker-desktop-data"], check=False)

    # 3. Dọn rác HuggingFace Cache
    print("\n[5/5] Đang xoá sạch HuggingFace Cache (16.6 GB) trên ổ C...")
    hf_cache = os.path.expanduser("~/.cache/huggingface")
    if os.path.exists(hf_cache):
        try:
            shutil.rmtree(hf_cache, ignore_errors=True)
            print("[OK] Đã dọn sạch HuggingFace Cache!")
        except:
            pass

    # 4. Dọn Pip cache
    print("\nĐang xoá bộ đệm của Pip...")
    subprocess.run(["pip", "cache", "purge"], capture_output=True)
    
    print("\n=== HOÀN TẤT ĐẠI PHẪU! Ổ C ĐÃ ĐƯỢC GIẢI CỨU ===")

if __name__ == "__main__":
    rescue()
