import { useState } from 'react';
import { X, AudioLines } from 'lucide-react';

export default function PodcastConfigModal({ onClose, onSubmit }) {
  const [topic, setTopic] = useState('');
  const [language, setLanguage] = useState('Tiếng Việt');

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-[#1e1e1e] border border-white/10 p-6 rounded-2xl max-w-2xl w-full mx-4 relative shadow-2xl">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors">
          <X size={20} />
        </button>
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
          <AudioLines className="text-gray-300" size={24} /> Tuỳ chỉnh Tổng quan bằng âm thanh
        </h2>

        <div className="mb-6">
          <label className="block text-sm text-gray-300 mb-3">Chọn ngôn ngữ</label>
          <select 
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-transparent border border-gray-600 rounded-xl p-3 text-sm text-gray-200 focus:outline-none focus:border-gray-400 w-1/3"
          >
            <option value="Tiếng Việt">Tiếng Việt</option>
            <option value="Tiếng Anh">Tiếng Anh</option>
          </select>
        </div>

        <div className="mb-6">
          <label className="block text-sm text-gray-300 mb-3">Máy chủ AI nên tập trung vào điều gì trong tập này?</label>
          <textarea 
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Ví dụ: Tập trung giải thích cách RAG giúp khắc phục hiện tượng mất dữ liệu giữa ngữ cảnh."
            className="w-full bg-transparent border border-gray-600 rounded-xl p-4 text-sm text-gray-200 focus:outline-none focus:border-gray-400 min-h-[120px] resize-none"
          />
        </div>

        <div className="flex justify-end mt-4">
          <button 
            onClick={() => onSubmit({ topic, language })}
            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-8 rounded-full transition-colors"
          >
            Tạo
          </button>
        </div>
      </div>
    </div>
  );
}
