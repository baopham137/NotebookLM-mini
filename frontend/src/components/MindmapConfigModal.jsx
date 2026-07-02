import { useState } from 'react';
import { X, Network } from 'lucide-react';

export default function MindmapConfigModal({ onClose, onSubmit }) {
  const [topic, setTopic] = useState('');

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-[#1e1e1e] border border-white/10 p-6 rounded-2xl max-w-2xl w-full mx-4 relative shadow-2xl">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors">
          <X size={20} />
        </button>
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
          <Network className="text-pink-400" size={24} /> Tuỳ chỉnh Bản đồ tư duy
        </h2>

        <div className="mb-6">
          <label className="block text-sm text-gray-300 mb-3">Chủ đề nên là gì?</label>
          <textarea 
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Những điều nên thử:&#10;• Bản đồ tư duy phải tập trung hoàn toàn vào các khái niệm chính&#10;• Tạo một bản đồ tư duy để giúp tôi nghiên cứu nguyên nhân dẫn đến Chiến tranh"
            className="w-full bg-transparent border border-pink-500/30 rounded-xl p-4 text-sm text-gray-200 focus:outline-none focus:border-pink-500 min-h-[120px] resize-none"
          />
        </div>

        <div className="flex justify-end mt-4">
          <button 
            onClick={() => onSubmit({ topic })}
            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-8 rounded-full transition-colors"
          >
            Tạo
          </button>
        </div>
      </div>
    </div>
  );
}
