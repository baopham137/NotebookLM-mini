import os
from typing import Optional, List, Dict
import warnings

from ..document_tree import DocumentNode, HeadingNode, ParagraphNode

class AudioParser:
    """Parser xử lý file âm thanh (MP3, WAV) sử dụng mô hình Whisper (Local)."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def _load_model(self):
        if self.model is None:
            try:
                # [Dự phòng] Thử nạp FFmpeg nếu bước Launcher bị bỏ qua
                import subprocess
                import platform
                try:
                    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    print("[AudioParser] Chưa tìm thấy FFmpeg, đang thử tải và cấu hình dự phòng...")
                    import imageio_ffmpeg
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    if ffmpeg_exe and os.path.exists(ffmpeg_exe):
                        os.environ["PATH"] = os.path.dirname(ffmpeg_exe) + os.pathsep + os.environ.get("PATH", "")
                        print("[AudioParser] Đã nạp xong FFmpeg dự phòng!")
            except Exception as e:
                print(f"[AudioParser] Cảnh báo cấu hình FFmpeg dự phòng: {e}")

            try:
                from src.utils.vram_orchestrator import get_orchestrator
                self.model = get_orchestrator().get_whisper(self.model_size)
                if self.model is None:
                    raise RuntimeError("Không thể tải model Whisper thông qua VRAM Orchestrator.")
            except ImportError:
                raise ImportError("Thư viện openai-whisper chưa được cài đặt. Chạy lệnh: pip install openai-whisper")
            except Exception as e:
                raise RuntimeError(f"Lỗi khởi tạo Whisper model: {e}\n(Bạn đã cài đặt ffmpeg trên máy chưa?)")

    def unload(self):
        """Xả mô hình Whisper khỏi bộ nhớ thông qua Orchestrator."""
        from src.utils.vram_orchestrator import get_orchestrator
        get_orchestrator().release_whisper()
        self.model = None

    def _group_segments_into_paragraphs(self, segments: List[Dict], max_duration: float = 30.0) -> List[Dict]:
        """Gộp các đoạn âm thanh ngắn thành các đoạn văn dài hơn."""
        paragraphs = []
        current_text = []
        current_start = 0.0
        current_duration = 0.0

        if not segments:
            return paragraphs

        current_start = segments[0]['start']

        for item in segments:
            text = item['text'].strip()
            current_text.append(text)
            current_duration = item['end'] - current_start

            if current_duration >= max_duration:
                paragraphs.append({
                    'text': " ".join(current_text).replace('\n', ' '),
                    'start': current_start,
                    'end': item['end']
                })
                current_text = []
                # Đặt lại current_start ở segment tiếp theo (được xử lý vòng lặp tới, hoặc lấy end của hiện tại)
                current_start = item['end']
                current_duration = 0.0

        if current_text:
            paragraphs.append({
                'text': " ".join(current_text).replace('\n', ' '),
                'start': current_start,
                'end': segments[-1]['end'] if segments else current_start
            })

        return paragraphs

    def parse(self, audio_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Không tìm thấy file audio: {audio_path}")

        # Tải mô hình nếu chưa tải
        self._load_model()

        print(f"[AudioParser] Đang bóc băng âm thanh (Transcribing): {os.path.basename(audio_path)}")
        try:
            # Transcribe
            result = self.model.transcribe(audio_path, fp16=False) # Tắt fp16 để an toàn trên CPU
            segments = result.get('segments', [])
        except Exception as e:
            raise RuntimeError(f"Lỗi khi transcribe audio (kiểm tra xem ffmpeg đã được cài chưa): {e}")

        # Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(audio_path)
        meta["parser"] = "AudioParser"
        meta["language"] = result.get("language", "unknown")

        # Khởi tạo Document Tree
        doc_node = DocumentNode(metadata=meta)
        doc_node.add_child(HeadingNode(level=1, content=f"Audio Transcript: {os.path.basename(audio_path)}"))

        # Gộp thành các Paragraphs
        paragraphs = self._group_segments_into_paragraphs(segments, max_duration=45.0)

        for p in paragraphs:
            p_meta = {
                "timestamp_start": round(p['start'], 2),
                "timestamp_end": round(p['end'], 2),
                "timestamp_display": f"[{int(p['start']//60):02d}:{int(p['start']%60):02d} - {int(p['end']//60):02d}:{int(p['end']%60):02d}]"
            }
            content = f"{p_meta['timestamp_display']} {p['text']}"
            doc_node.add_child(ParagraphNode(content=content, metadata=p_meta))

        return doc_node
