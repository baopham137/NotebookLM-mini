import { useState } from 'react';
import { X, Layers } from 'lucide-react';

export default function FlashcardConfigModal({ onClose, onSubmit }) {
  const [amount, setAmount] = useState(5);
  const [difficulty, setDifficulty] = useState('Trung bình (Mặc định)');
  const [topic, setTopic] = useState('');

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-[#1e1e1e] border border-white/10 p-6 rounded-2xl max-w-2xl w-full mx-4 relative shadow-2xl">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors">
          <X size={20} />
        </button>
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
          <Layers className="text-neon-purple" size={24} /> Tuỳ chỉnh Thẻ thông tin
        </h2>

        <div className="grid grid-cols-2 gap-8 mb-6">
          <div>
            <label className="block text-sm text-gray-300 mb-3">Số lượng thẻ</label>
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => setAmount(3)} className={`px-4 py-2 rounded-full text-sm transition-colors ${amount === 3 ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50' : 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'}`}>Ít hơn</button>
              <button onClick={() => setAmount(5)} className={`px-4 py-2 rounded-full text-sm transition-colors ${amount === 5 ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50' : 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'}`}>✓ Tiêu chuẩn (Mặc định)</button>
              <button onClick={() => setAmount(10)} className={`px-4 py-2 rounded-full text-sm transition-colors ${amount === 10 ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50' : 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'}`}>Tuỳ chọn khác</button>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-3">Độ khó</label>
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => setDifficulty('Dễ')} className={`px-4 py-2 rounded-full text-sm transition-colors ${difficulty === 'Dễ' ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50' : 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'}`}>Dễ</button>
              <button onClick={() => setDifficulty('Trung bình (Mặc định)')} className={`px-4 py-2 rounded-full text-sm transition-colors ${difficulty === 'Trung bình (Mặc định)' ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50' : 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'}`}>✓ Trung bình (Mặc định)</button>
              <button onClick={() => setDifficulty('Khó')} className={`px-4 py-2 rounded-full text-sm transition-colors ${difficulty === 'Khó' ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50' : 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'}`}>Khó</button>
            </div>
          </div>
        </div>

        <div className="mb-6">
          <label className="block text-sm text-gray-300 mb-3">Chủ đề nên là gì?</label>
          <textarea 
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Những điều nên thử:&#10;• Các thẻ thông tin phải được giới hạn trong một nguồn cụ thể&#10;• Các thẻ thông tin phải tập trung vào một chủ đề cụ thể&#10;• Mặt trước thẻ phải ngắn gọn"
            className="w-full bg-transparent border border-neon-purple/30 rounded-xl p-4 text-sm text-gray-200 focus:outline-none focus:border-neon-purple min-h-[120px] resize-none"
          />
        </div>

        <div className="flex justify-end mt-4">
          <button 
            onClick={() => onSubmit({ amount, difficulty, topic, language: 'Tiếng Việt' })}
            className="bg-neon-purple hover:bg-purple-600 text-white font-bold py-2 px-8 rounded-full transition-colors"
          >
            Tạo
          </button>
        </div>
      </div>
    </div>
  );
}
