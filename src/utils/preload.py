import os
import sys
from huggingface_hub import snapshot_download

# Bổ sung path để import được cấu hình
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.config import settings

def preload_core_models():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print("\n" + "="*50)
    print(" BẮT ĐẦU TẢI TRƯỚC CÁC MÔ HÌNH LÕI (CACHE PRELOADING) ")
    print("="*50)
    print("Quá trình này chỉ diễn ra 1 lần duy nhất để phục vụ dùng Offline sau này.")
    print("Lưu ý: Hệ thống chỉ tải file vào ổ đĩa, KHÔNG nạp lên RAM.\n")
    
    # 1. Embedding Model
    print(f"[1/2] Đang tải Embedding Model: {settings.embedding_model} ...")
    try:
        snapshot_download(settings.embedding_model)
        print(" -> [Thành công] Embedding Model đã sẵn sàng.")
    except Exception as e:
        print(f" -> [Lỗi] Không thể tải Embedding Model: {e}")

    # 2. Reranker Model
    print(f"[2/2] Đang tải Reranker Model: {settings.reranker_model} ...")
    try:
        snapshot_download(settings.reranker_model)
        print(" -> [Thành công] Reranker Model đã sẵn sàng.")
    except Exception as e:
        print(f" -> [Lỗi] Không thể tải Reranker Model: {e}")
        
    print("\n" + "="*50)
    print(" HOÀN TẤT TẢI MÔ HÌNH LÕI! ")
    print("="*50 + "\n")

if __name__ == "__main__":
    preload_core_models()
