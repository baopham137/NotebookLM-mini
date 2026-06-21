# 📓 NotebookLM-Mini (Local AI Edition)

NotebookLM-Mini là một trợ lý học tập cá nhân dựa trên kiến trúc **Retrieval-Augmented Generation (RAG)**. Dự án được thiết kế lại hoàn toàn với kiến trúc **Frontend (React)** + **Backend (FastAPI)** + **Docker Compose**, giúp triển khai trơn tru trên mọi hệ điều hành. Hệ thống chú trọng vào chạy cục bộ (Local AI) để bảo mật tuyệt đối dữ liệu.

Dự án cho phép bạn tải lên tài liệu cá nhân (PDF, DOCX, TXT...), tự động phân tích và tương tác qua:
- 💬 **Hỏi đáp siêu tốc** với RAG (Qdrant Vector Database + BM25).
- 📝 **Tóm tắt thông minh** tự động ngay khi tải tài liệu.
- 🎯 **Tạo bài trắc nghiệm (Quiz)** & **Flashcards** để ôn tập kiến thức.
- 🎙️ **Podcast** sinh từ tài liệu (Text-to-Audio).

---

## 🌟 Tính Năng Triển Khai Nổi Bật

1. **🚀 1-Click Run (Khởi động 1 chạm):** Tích hợp Script `start.bat` / `start.sh` tự động cài Python, quét phần cứng, sinh cấu hình và bật Docker Compose dưới nền. Người dùng không cần gõ lệnh.
2. **🧠 Tự động nhận diện phần cứng (Setup Wizard):** `setup_wizard.py` quét RAM/VRAM để quyết định bạn nên chạy Model nặng (Ollama/Qwen 7B) hay Model siêu nhẹ, hoặc chuyển sang dùng Gemini API nếu máy quá yếu.
3. **🐳 Docker Hóa Hoàn Toàn:** Hệ thống được chia thành 3 container chuẩn mực: `llm_mini_frontend`, `llm_mini_backend`, và `llm_mini_redis` (dùng để quản lý Background Tasks).
4. **🛡️ Giải Cứu Ổ C (Rescue Drive):** Cung cấp công cụ `rescue_drive_c.py` chuyên dụng để dời ổ ảo Docker (vhdx) và bộ đệm HuggingFace sang ổ D, bảo vệ ổ C của người dùng phổ thông.

---

## 📖 HƯỚNG DẪN SỬ DỤNG (Dành cho Người dùng cuối)

### 1. Yêu Cầu Cài Đặt Ban Đầu
- Tải và cài đặt **Docker Desktop** (Bắt buộc). Đảm bảo Docker đang chạy (Biểu tượng cá voi màu xanh).
- Mạng internet cho **lần chạy đầu tiên** để tải hình ảnh Docker và mô hình AI (khoảng 3GB - 10GB tùy cấu hình).

### 2. Khởi Động Dự Án (Chỉ 1 Click)

**Đối với người dùng Windows:**
1. Mở thư mục dự án.
2. Nhấp đúp chuột vào file `start.bat`.
3. Cửa sổ dòng lệnh sẽ hiện lên, nó sẽ tự cài đặt và chạy `setup_wizard` (Hỏi bạn cấu hình 1 lần duy nhất).
4. Sau đó, nó tự động gọi Docker và mở trình duyệt web tại `http://localhost:5173`.

**Từ lần thứ 2 trở đi:**
- Bạn có thể nhấp đúp lại `start.bat`. Hệ thống sẽ nhận diện là đã cài đặt và chỉ việc đánh thức Docker lên.
- **Hoặc** bạn có thể mở giao diện Docker Desktop, tìm nhóm container tên là `llm_mini` và bấm nút **Play (▷)**.
- Mở trình duyệt web của bạn và gõ: `http://localhost:5173`.

### 3. Tắt Hệ Thống (Dừng dự án)
- Mở giao diện Docker Desktop.
- Bấm nút **Stop (⏹)** ở nhóm `llm_mini`. Hệ thống sẽ đi ngủ, nhả lại RAM và CPU cho máy tính của bạn. Dữ liệu tài liệu của bạn vẫn được lưu giữ an toàn trên ổ cứng.

---

## 🛠️ HƯỚNG DẪN DÀNH CHO LẬP TRÌNH VIÊN (Developer)

Nếu bạn muốn test code hoặc chạy lẻ tẻ để xem log, thay vì dùng `start.bat`, hãy làm theo các bước sau:

### 1. Build và Chạy toàn bộ hệ thống bằng Docker
```bash
docker-compose up -d --build
```
*Lệnh này sẽ khởi chạy Backend (Cổng 8000), Frontend (Cổng 5173) và Redis.*
*Để xem log của Backend (rất hữu ích khi xem Ingestion hay RAG chạy ngầm):*
```bash
docker logs -f llm_mini_backend
```

### 2. Chạy Kiểm Thử Tự Động (E2E Test)
Dự án được trang bị kịch bản End-to-End Test (E2E) tự động giả lập người dùng: tạo Notebook, tải tài liệu ảo, chờ nạp dữ liệu nền và hỏi LLM một câu hỏi để kiểm tra độ chính xác của RAG.

**Cách chạy E2E Test:**
```bash
python tests/test_e2e.py
```
*(Yêu cầu: Docker Desktop phải đang bật).*

---

## 🏥 XỬ LÝ SỰ CỐ (Troubleshooting)

- **Ổ C bị báo đỏ sau khi cài dự án?** 
  Mở thư mục dự án và nhấp đúp vào `rescue_drive_c.py` (hoặc chạy `python rescue_drive_c.py`). Script này sẽ giúp dời cục dữ liệu Docker khổng lồ từ ổ C sang ổ D an toàn.
  
- **Vào Web `localhost:5173` bị trắng trang?**
  Đảm bảo Docker Desktop của bạn đang bật và các container đang báo xanh. Nếu backend vẫn đang kéo Model, hãy đợi 2-3 phút rồi F5 (tải lại trang).

---
*Dự án NotebookLM Mini - Đóng gói mượt mà như ứng dụng thương mại.*
