#!/bin/bash

# ==============================================================================
# NotebookLM-Mini 1-Click Run Script for macOS
# ==============================================================================

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Khởi động NotebookLM-Mini cho macOS..."

# Di chuyển đến thư mục chứa script
cd "$(dirname "$0")"

# Hàm kiểm tra command có tồn tại
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Kiểm tra Python
if ! command_exists python3; then
    echo "❌ Lỗi: Không tìm thấy Python3. Vui lòng cài đặt Python (https://www.python.org/downloads/mac-osx/)"
    exit 1
fi

# 1.5 Cài đặt các công cụ hệ thống cần thiết qua Homebrew
if command_exists brew; then
    if ! command_exists ffmpeg; then
        echo "📦 Đang cài đặt ffmpeg (để xử lý âm thanh)..."
        brew install ffmpeg
    fi
    if ! command_exists tesseract; then
        echo "📦 Đang cài đặt Tesseract OCR (để nhận diện chữ trong ảnh)..."
        brew install tesseract tesseract-lang
    fi
else
    echo "⚠️ Cảnh báo: Homebrew chưa được cài đặt, bỏ qua tự động cài ffmpeg và tesseract."
fi

# 2. Kiểm tra và cài đặt uv (Trình quản lý package siêu tốc)
if ! command_exists uv; then
    echo "📦 Đang cài đặt uv (Công cụ quản lý môi trường siêu tốc)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Khởi tạo môi trường ảo (nếu chưa có)
if [ ! -d ".venv" ]; then
    echo "🛠 Đang tạo môi trường ảo..."
    uv venv
fi

# 4. Kích hoạt môi trường ảo
source .venv/bin/activate

# 5. Cài đặt các thư viện lõi
echo "📥 Đang đồng bộ hóa thư viện..."
uv pip install -r requirements.txt

# 6. Cài đặt llama-cpp-python với cờ Metal cho Mac M-series (tối ưu tốc độ)
echo "⚡ Đang kiểm tra/cài đặt Engine AI tối ưu cho máy Mac..."
# Kiểm tra nếu chưa cài llama-cpp-python
if ! python -c "import llama_cpp" 2>/dev/null; then
    echo "🚀 Cài đặt Llama.cpp với cấu hình Apple Metal GPU..."
    CMAKE_ARGS="-DGGML_METAL=on" uv pip install llama-cpp-python --no-cache-dir
fi

# 6.5 Quét phần cứng và tự động cài đặt Model Zoo
echo "🔍 Đang quét cấu hình máy tính của bạn để đề xuất Model AI tối ưu..."
python src/utils/hardware_profiler.py

# 6.8 Xây dựng giao diện Frontend
if command_exists npm; then
    echo "📦 Đang kiểm tra và xây dựng giao diện người dùng (Frontend)..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "📥 Đang cài đặt thư viện Node.js..."
        npm install
    fi
    if [ ! -d "dist" ]; then
        echo "🏗 Đang biên dịch giao diện Web..."
        npm run build
    fi
    cd ..
else
    echo "⚠️ Lỗi: Không tìm thấy lệnh 'npm'. Giao diện Web sẽ không hiển thị. Vui lòng cài đặt Node.js."
fi

# 7. Khởi động hệ thống
echo "✨ Bắt đầu chạy hệ thống..."
echo "-> Mở trình duyệt Web tại: http://localhost:8000"

# Đợi 2 giây cho Server Uvicorn khởi động, sau đó mở web
(sleep 3 && open http://localhost:8000) &

# Chạy Backend (chiếm màn hình chính)
uvicorn src.api.api:app --host 127.0.0.1 --port 8000
