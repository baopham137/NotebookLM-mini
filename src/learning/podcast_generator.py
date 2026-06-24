import os
import re
import uuid
import logging
import asyncio
from ..llm.llm_client import LLMEngine
from ..db.session_manager import SessionManager

logger = logging.getLogger(__name__)

class PodcastGenerator:
    def __init__(self, llm_engine: LLMEngine, session_manager: SessionManager):
        self.llm = llm_engine
        self.db = session_manager
        self.output_dir = "storage/podcasts"
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_podcast(self, notebook_id: str, is_private: bool, style: str = "normal", gemini_api_key: str = None) -> str:
        """Sinh Podcast MP3 dựa trên Study Guide."""
        guide = self.db.get_study_guide(notebook_id)
        if not guide:
            raise ValueError("Chưa có Study Guide cho Notebook này.")
            
        summary = guide.get('summary', '')
        faq = guide.get('faq', '')
        
        # 1. Sinh kịch bản bằng LLM Local
        
        if style == "debate":
            style_prompt = "Hãy viết kịch bản dạng TRANH BIỆN GẮT GAO. Host A ủng hộ quan điểm trong tài liệu, Host B kịch liệt phản đối và bắt bẻ. Hai bên tranh luận nảy lửa."
            sys_prompt = "Bạn là biên kịch viết lời thoại Podcast Tranh Biện cực gắt."
        elif style == "sarcastic":
            style_prompt = "Hãy viết kịch bản dạng HÀI HƯỚC, CÀ KHỊA. Hai Host dùng nhiều từ lóng Gen Z, mỉa mai những điểm vô lý hoặc tóm tắt tài liệu theo cách buồn cười nhất có thể."
            sys_prompt = "Bạn là biên kịch viết lời thoại Podcast Hài hước Gen Z."
        else:
            style_prompt = "Hãy viết một kịch bản giao lưu Podcast ngắn gọn, dễ hiểu, thân thiện."
            sys_prompt = "Bạn là biên kịch viết lời thoại Podcast chuyên nghiệp."
            
        prompt = (
            f"Dưới đây là tài liệu tóm tắt:\n{summary}\n\nCác câu hỏi thường gặp:\n{faq}\n\n"
            f"{style_prompt}\n"
            f"Kịch bản dài khoảng 6-10 câu giữa 2 người (Host A - Nam, Host B - Nữ). "
            f"Định dạng NGHIÊM NGẶT như sau, không viết thêm bất cứ giải thích nào khác:\n"
            f"A: [Lời thoại của A]\n"
            f"B: [Lời thoại của B]\n"
        )
        
        logger.info(f"Đang sinh kịch bản Podcast (Style: {style})...")
        script_raw = "".join(self.llm.generate(prompt, system_prompt=sys_prompt, is_private=is_private, gemini_api_key=gemini_api_key))
        
        # 2. Parse kịch bản
        lines = script_raw.split('\n')
        dialogues = []
        for line in lines:
            if line.startswith('A:') or line.startswith('Host A:'):
                dialogues.append(('A', line.split(':', 1)[1].strip()))
            elif line.startswith('B:') or line.startswith('Host B:'):
                dialogues.append(('B', line.split(':', 1)[1].strip()))
                
        if not dialogues:
            logger.warning("Không nhận diện được kịch bản, dùng kịch bản dự phòng.")
            dialogues = [
                ('A', 'Xin chào, có vẻ hệ thống AI vừa gặp lỗi khi viết kịch bản.'),
                ('B', 'Vâng, chúng tôi sẽ sớm khắc phục.')
            ]
            
        # 3. Tổng hợp giọng nói (Băng Kép)
        output_file = os.path.join(self.output_dir, f"{notebook_id}.mp3")
        
        if is_private:
            self._generate_offline(dialogues, output_file)
        else:
            asyncio.run(self._generate_online(dialogues, output_file))
            
        return output_file

    def _generate_offline(self, dialogues, output_file):
        """Sử dụng pyttsx3 cho chế độ 100% Offline (Airgapped)"""
        logger.info("TTS Mode: OFFLINE (pyttsx3)")
        import pyttsx3
        from pydub import AudioSegment
        
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        # Thử tìm giọng Nam và Nữ
        voice_a = voices[0].id if len(voices) > 0 else None
        voice_b = voices[1].id if len(voices) > 1 else voice_a
        
        audio_segments = []
        temp_files = []
        
        for idx, (speaker, text) in enumerate(dialogues):
            temp_file = f"temp_{uuid.uuid4().hex}.wav"
            temp_files.append(temp_file)
            
            if speaker == 'A':
                if voice_a: engine.setProperty('voice', voice_a)
            else:
                if voice_b: engine.setProperty('voice', voice_b)
                
            engine.save_to_file(text, temp_file)
            engine.runAndWait()
            
            # Đọc bằng pydub
            audio_segments.append(AudioSegment.from_wav(temp_file))
            
        # Nối file
        final_audio = sum(audio_segments)
        final_audio.export(output_file, format="mp3")
        
        # Dọn dẹp
        for f in temp_files:
            if os.path.exists(f): os.remove(f)

    async def _generate_online(self, dialogues, output_file):
        """Sử dụng edge-tts cho chế độ Public (API Edge siêu mượt)"""
        logger.info("TTS Mode: ONLINE (edge-tts)")
        import edge_tts
        from pydub import AudioSegment
        
        voice_a = "vi-VN-NamMinhNeural" # Giọng Nam
        voice_b = "vi-VN-HoaiMyNeural" # Giọng Nữ
        
        audio_segments = []
        temp_files = []
        
        for idx, (speaker, text) in enumerate(dialogues):
            temp_file = f"temp_{uuid.uuid4().hex}.mp3"
            temp_files.append(temp_file)
            
            v = voice_a if speaker == 'A' else voice_b
            communicate = edge_tts.Communicate(text, v)
            await communicate.save(temp_file)
            
            audio_segments.append(AudioSegment.from_mp3(temp_file))
            
        # Nối file
        final_audio = sum(audio_segments)
        final_audio.export(output_file, format="mp3")
        
        # Dọn dẹp
        for f in temp_files:
            if os.path.exists(f): os.remove(f)

    def generate_custom_podcast(self, notebook_id: str, context: str, topic: str, language: str, is_private: bool, gemini_api_key: str = None) -> str:
        """Sinh Podcast MP3 dựa trên cấu hình tùy chỉnh."""
        prompt = (
            f"Dưới đây là tài liệu:\n{context[:10000]}\n\n"
            f"Hãy viết một kịch bản giao lưu Podcast ngắn gọn, thân thiện bằng ngôn ngữ '{language}'.\n"
            f"Chủ đề tập trung: {topic}\n"
            f"Kịch bản dài khoảng 6-10 câu giữa 2 người (Host A - Nam, Host B - Nữ). "
            f"Định dạng NGHIÊM NGẶT như sau, không viết thêm bất cứ giải thích nào khác:\n"
            f"A: [Lời thoại của A]\n"
            f"B: [Lời thoại của B]\n"
        )
        
        logger.info(f"Đang sinh kịch bản Podcast tùy chỉnh...")
        script_raw = "".join(self.llm.generate(prompt, system_prompt="Bạn là biên kịch viết lời thoại Podcast chuyên nghiệp.", is_private=is_private, gemini_api_key=gemini_api_key))
        
        # Parse kịch bản
        lines = script_raw.split('\n')
        dialogues = []
        for line in lines:
            if line.startswith('A:') or line.startswith('Host A:'):
                dialogues.append(('A', line.split(':', 1)[1].strip()))
            elif line.startswith('B:') or line.startswith('Host B:'):
                dialogues.append(('B', line.split(':', 1)[1].strip()))
                
        if not dialogues:
            raise ValueError("LLM không sinh ra kịch bản đúng định dạng.")
            
        output_filename = f"{notebook_id}_{uuid.uuid4().hex[:8]}.mp3"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Sinh audio thực tế (tương tự method trên)
        if is_private:
            self._generate_offline(dialogues, output_path)
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._generate_online(dialogues, output_path))
            finally:
                loop.close()
            
        return f"/api/podcasts/{output_filename}"
