# 📓 NotebookLM-Mini (Native Local Edition)

NotebookLM-Mini là một trợ lý học tập cá nhân dựa trên kiến trúc **Retrieval-Augmented Generation (RAG)**. Ở phiên bản mới nhất, hệ thống đã loại bỏ hoàn toàn sự cồng kềnh của Docker, thay vào đó sử dụng kiến trúc **Native Local (llama.cpp + FastAPI + React)**. Nhờ vậy, dự án có thể chạy trực tiếp trên hệ điều hành của bạn với dung lượng RAM/VRAM được tối ưu hóa đến mức tối đa.

Dự án cho phép bạn tải lên tài liệu cá nhân (PDF, DOCX, TXT, Hình ảnh, Âm thanh...), tự động phân tích và tương tác qua:
- 💬 **Hỏi đáp siêu tốc** với RAG (Qdrant Vector Database + BM25).
- 📝 **Tóm tắt thông minh** tự động ngay khi tải tài liệu.
- 🎯 **Tạo bài trắc nghiệm (Quiz)** & **Flashcards** để ôn tập kiến thức.
- 🎙️ **Podcast** sinh từ tài liệu (Text-to-Audio).

---

## 🌟 Tính Năng Nổi Bật Của Kiến Trúc Mới

1. **🚀 1-Click Run (Khởi động 1 chạm):** Chỉ cần chạy file `run.bat` (Windows) hoặc `run_mac.command` (Mac). Hệ thống sẽ tự động tạo môi trường ảo (Virtual Environment), tải AI và chạy phần mềm mà không cần bạn phải cấu hình biến môi trường phức tạp.
2. **🧠 Nhận diện phần cứng thông minh:** Cửa sổ Terminal sẽ cho phép bạn chọn mức độ nặng/nhẹ của mô hình LLM (Qwen 2.5), mô hình Embedding và Reranker để phù hợp nhất với cấu hình máy của bạn (Từ Laptop văn phòng 4GB RAM đến PC Gaming đỉnh cao).
3. **🛡️ Bảo vệ VRAM tuyệt đối:** Hệ thống RAG được thiết kế để tự động lùi về chạy trên CPU nếu VRAM của bạn thấp (<= 6GB), nhường toàn bộ sức mạnh Card đồ họa cho LLM để tốc độ gõ chữ đạt mức cao nhất.
4. **👁️ Tải AI Thị Giác & Âm Thanh On-Demand:** Các mô hình phân tích Ảnh (OCR/Moondream) và Âm thanh (Whisper) sẽ không bị tải dư thừa từ đầu. Khi bạn Upload ảnh hoặc âm thanh, Web UI mới hiện ra bảng chọn và tư vấn mô hình phù hợp dựa trên phần cứng.

---

## 📖 HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG

### 1. Yêu Cầu Cài Đặt Ban Đầu
- Máy tính đã cài sẵn **Python 3.10+**.
- Kết nối Internet (chỉ cần trong lần chạy đầu tiên để tải mã nguồn và mô hình AI).

### 2. Khởi Động Dự Án (Lần đầu tiên)
**Đối với người dùng Windows:**
1. Nhấp đúp chuột vào file `run.bat`.
2. Terminal sẽ hiện ra. Bạn sẽ được hỏi 3 câu hỏi để cá nhân hóa phần mềm:
   - Chọn kích cỡ **Bộ não LLM (Qwen 2.5)**.
   - Chọn **Mô hình Embedding (GreenNode hoặc sBERT)**.
   - Chọn **Mô hình Reranker (BGE-M3 hoặc mMiniLM)**.
3. Chờ phần mềm tự động tải các mô hình này về máy. (Quá trình này tùy thuộc vào tốc độ mạng của bạn, dao động từ 5 phút - 20 phút).
4. Sau khi tải xong, trình duyệt web sẽ tự động mở lên tại địa chỉ: `http://localhost:5173`.

**Đối với người dùng Mac:**
- Mở Terminal, trỏ vào thư mục dự án và chạy: `./run_mac.command`.

### 3. Từ lần chạy thứ 2 trở đi
- Bạn chỉ việc nhấp đúp lại vào file `run.bat`.
- Hệ thống sẽ nhận diện là máy đã cài đặt xong, nó sẽ trực tiếp khởi động máy chủ (Backend + LLM) chưa tới 10 giây và mở trình duyệt web cho bạn.

---

## 🛠️ HƯỚNG DẪN DÀNH CHO LẬP TRÌNH VIÊN (Developer)

Nếu bạn muốn chỉnh sửa code của hệ thống, kiến trúc đã được tách bạch rõ ràng:

- **Frontend:** Code React (Vite) nằm trong thư mục `frontend/`. 
  - Chạy môi trường phát triển: `cd frontend && npm run dev`.
  - Đóng gói: `npm run build`. 
  Lưu ý: Bạn không cần phải bật dev server của frontend nếu chỉ muốn xài, vì backend tự động phục vụ file tĩnh của Frontend tại cổng 8000.

- **Backend:** Code FastAPI nằm trong thư mục `src/`.
  - Bạn có thể xem Log của Backend ngay tại cửa sổ Terminal khi `run.bat` đang chạy để theo dõi quá trình phân tích RAG và Ingestion.
  - Cấu hình thiết lập được lưu trữ trong file `.env` ẩn tại thư mục gốc. Bạn có thể mở file này để thay đổi `RAG_EMBEDDING_MODEL` hoặc `RAG_RERANKER_MODEL` sang bất kỳ mô hình HuggingFace nào bạn thích.

---
*Dự án NotebookLM Mini - Đóng gói mượt mà, siêu việt trên máy tính cá nhân.*
