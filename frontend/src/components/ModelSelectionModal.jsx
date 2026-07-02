import { useState, useEffect } from 'react';
import { X, Cpu, HardDrive, AlertTriangle, CheckCircle2, DownloadCloud, Server, Loader2 } from 'lucide-react';

export default function ModelSelectionModal({ isOpen, onClose, onSuccess, type, fileToUpload }) {
  const [resources, setResources] = useState(null);
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetch('/api/system-resources')
        .then(res => res.json())
        .then(data => {
          setResources(data);
          // Auto select recommended based on resources
          if (type === 'vision') {
            if (data.gpu_memory_total_gb > 4) setSelectedModel('Qwen/Qwen2-VL-2B-Instruct');
            else if (data.ram_total_gb > 8) setSelectedModel('vikhyatk/moondream2');
            else setSelectedModel('ocr');
          } else {
            if (data.ram_total_gb > 8) setSelectedModel('small');
            else setSelectedModel('base');
          }
        })
        .catch(err => console.error("Could not fetch resources", err));
    }
  }, [isOpen, type]);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!selectedModel) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/system/setup-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, model_name: selectedModel })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Lỗi cài đặt mô hình');
      }
      onSuccess(fileToUpload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getMemoryWarning = (model) => {
    if (!resources) return null;
    if (type === 'vision') {
      if (model === 'Qwen/Qwen2-VL-2B-Instruct' && resources.gpu_memory_total_gb < 4) {
        return <div className="text-red-500 text-xs mt-1 flex items-center"><AlertTriangle className="w-3 h-3 mr-1"/> Cảnh báo: VRAM yếu, máy có thể bị treo.</div>;
      }
      if (model === 'vikhyatk/moondream2' && resources.ram_total_gb < 8) {
        return <div className="text-orange-500 text-xs mt-1 flex items-center"><AlertTriangle className="w-3 h-3 mr-1"/> Khuyên dùng RAM &gt; 8GB.</div>;
      }
    } else {
      if (model === 'medium' && resources.ram_total_gb < 8) {
        return <div className="text-orange-500 text-xs mt-1 flex items-center"><AlertTriangle className="w-3 h-3 mr-1"/> Khuyên dùng RAM &gt; 8GB.</div>;
      }
    }
    return <div className="text-green-500 text-xs mt-1 flex items-center"><CheckCircle2 className="w-3 h-3 mr-1"/> Cấu hình phù hợp.</div>;
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-xl shadow-xl w-full max-w-2xl border border-slate-700 overflow-hidden flex flex-col">
        <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/50">
          <h2 className="text-xl font-bold text-white flex items-center">
            {type === 'vision' ? '👁️ Lựa Chọn Mô Hình Xử Lý Ảnh' : '🎧 Lựa Chọn Mô Hình Bóc Băng Âm Thanh'}
          </h2>
          <button onClick={onClose} disabled={loading} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto">
          {!loading ? (
            <>
              <p className="text-slate-300 mb-4 text-sm leading-relaxed">
                Hệ thống phát hiện bạn đang tải lên tài liệu {type === 'vision' ? 'Hình ảnh' : 'Âm thanh'} lần đầu tiên.
                Vui lòng chọn mô hình AI (Model) để cài đặt. Quá trình này <strong>chỉ diễn ra 1 lần duy nhất</strong>.
              </p>

              {resources && (
                <div className="flex flex-wrap gap-4 mb-6 p-3 bg-slate-800 rounded-lg border border-slate-700 text-sm">
                  <div className="flex items-center text-slate-300">
                    <Cpu className="w-4 h-4 mr-2 text-blue-400" />
                    <span>RAM: <strong>{resources.ram_total_gb?.toFixed(1)} GB</strong></span>
                  </div>
                  <div className="flex items-center text-slate-300">
                    <Server className="w-4 h-4 mr-2 text-purple-400" />
                    <span>VRAM: <strong>{resources.gpu_memory_total_gb?.toFixed(1)} GB</strong></span>
                  </div>
                  <div className="flex items-center text-slate-300">
                    <HardDrive className="w-4 h-4 mr-2 text-green-400" />
                    <span>Disk: <strong>{resources.disk_free_gb?.toFixed(1)} GB</strong></span>
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {type === 'vision' ? (
                  <>
                    <label className={`flex flex-col p-4 rounded-lg border cursor-pointer transition-all ${selectedModel === 'ocr' ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'}`}>
                      <div className="flex items-center">
                        <input type="radio" name="model" value="ocr" checked={selectedModel === 'ocr'} onChange={(e) => setSelectedModel(e.target.value)} className="mr-3 w-4 h-4 text-blue-500" />
                        <span className="font-semibold text-white">Chỉ dùng OCR (Siêu nhẹ)</span>
                      </div>
                      <div className="ml-7 mt-1 text-xs text-slate-400">Trích xuất văn bản cơ bản, không có khả năng mô tả hình ảnh. Tốn 0 GB ổ cứng.</div>
                      <div className="ml-7">{getMemoryWarning('ocr')}</div>
                    </label>

                    <label className={`flex flex-col p-4 rounded-lg border cursor-pointer transition-all ${selectedModel === 'vikhyatk/moondream2' ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'}`}>
                      <div className="flex items-center">
                        <input type="radio" name="model" value="vikhyatk/moondream2" checked={selectedModel === 'vikhyatk/moondream2'} onChange={(e) => setSelectedModel(e.target.value)} className="mr-3 w-4 h-4 text-blue-500" />
                        <span className="font-semibold text-white">Moondream2 (Nhẹ ~1.5GB)</span>
                        <span className="ml-auto text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">Khuyên dùng</span>
                      </div>
                      <div className="ml-7 mt-1 text-xs text-slate-400">Mô hình thị giác cực kỳ nhỏ gọn nhưng thông minh. Lý tưởng cho máy không có Card rời.</div>
                      <div className="ml-7">{getMemoryWarning('vikhyatk/moondream2')}</div>
                    </label>

                    <label className={`flex flex-col p-4 rounded-lg border cursor-pointer transition-all ${selectedModel === 'Qwen/Qwen2-VL-2B-Instruct' ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'}`}>
                      <div className="flex items-center">
                        <input type="radio" name="model" value="Qwen/Qwen2-VL-2B-Instruct" checked={selectedModel === 'Qwen/Qwen2-VL-2B-Instruct'} onChange={(e) => setSelectedModel(e.target.value)} className="mr-3 w-4 h-4 text-blue-500" />
                        <span className="font-semibold text-white">Qwen2-VL-2B (Nặng ~3.5GB)</span>
                      </div>
                      <div className="ml-7 mt-1 text-xs text-slate-400">Mô hình cực kỳ mạnh mẽ, nhận diện chữ tiếng Việt tốt. Phải có Card rời.</div>
                      <div className="ml-7">{getMemoryWarning('Qwen/Qwen2-VL-2B-Instruct')}</div>
                    </label>
                  </>
                ) : (
                  <>
                    <label className={`flex flex-col p-4 rounded-lg border cursor-pointer transition-all ${selectedModel === 'base' ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'}`}>
                      <div className="flex items-center">
                        <input type="radio" name="model" value="base" checked={selectedModel === 'base'} onChange={(e) => setSelectedModel(e.target.value)} className="mr-3 w-4 h-4 text-blue-500" />
                        <span className="font-semibold text-white">Whisper Base (~140MB)</span>
                      </div>
                      <div className="ml-7 mt-1 text-xs text-slate-400">Chạy mượt trên mọi máy, tốc độ nhanh. Tiếng Việt có thể thỉnh thoảng sai dấu.</div>
                      <div className="ml-7">{getMemoryWarning('base')}</div>
                    </label>

                    <label className={`flex flex-col p-4 rounded-lg border cursor-pointer transition-all ${selectedModel === 'small' ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'}`}>
                      <div className="flex items-center">
                        <input type="radio" name="model" value="small" checked={selectedModel === 'small'} onChange={(e) => setSelectedModel(e.target.value)} className="mr-3 w-4 h-4 text-blue-500" />
                        <span className="font-semibold text-white">Whisper Small (~460MB)</span>
                        <span className="ml-auto text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">Khuyên dùng</span>
                      </div>
                      <div className="ml-7 mt-1 text-xs text-slate-400">Cân bằng tốt giữa tốc độ và độ chính xác cho tiếng Việt.</div>
                      <div className="ml-7">{getMemoryWarning('small')}</div>
                    </label>
                    
                    <label className={`flex flex-col p-4 rounded-lg border cursor-pointer transition-all ${selectedModel === 'medium' ? 'border-blue-500 bg-blue-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'}`}>
                      <div className="flex items-center">
                        <input type="radio" name="model" value="medium" checked={selectedModel === 'medium'} onChange={(e) => setSelectedModel(e.target.value)} className="mr-3 w-4 h-4 text-blue-500" />
                        <span className="font-semibold text-white">Whisper Medium (~1.5GB)</span>
                      </div>
                      <div className="ml-7 mt-1 text-xs text-slate-400">Độ chính xác rất cao, phù hợp cho bài giảng dài. Tốc độ hơi chậm.</div>
                      <div className="ml-7">{getMemoryWarning('medium')}</div>
                    </label>
                  </>
                )}
              </div>
              {error && (
                <div className="mt-4 p-3 bg-red-500/20 border border-red-500 rounded text-red-200 text-sm">
                  {error}
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Loader2 className="w-16 h-16 text-blue-500 animate-spin mb-4" />
              <h3 className="text-xl font-bold text-white mb-2">Đang tải và cài đặt mô hình...</h3>
              <p className="text-slate-400 max-w-sm">
                Quá trình này có thể mất vài phút tùy thuộc vào tốc độ mạng của bạn. Vui lòng không đóng cửa sổ này.
              </p>
              <div className="mt-6 flex items-center p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400 text-sm">
                <DownloadCloud className="w-5 h-5 mr-2" />
                <span>Model sẽ được lưu vào thư mục cache để sử dụng offline cho các lần sau.</span>
              </div>
            </div>
          )}
        </div>

        {!loading && (
          <div className="p-4 border-t border-slate-700 flex justify-end gap-3 bg-slate-800/50">
            <button onClick={onClose} className="px-5 py-2 rounded-lg font-medium text-slate-300 hover:bg-slate-700 transition-colors">
              Hủy bỏ
            </button>
            <button 
              onClick={handleSubmit}
              disabled={!selectedModel}
              className="px-5 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              Cài đặt & Tiếp tục <CheckCircle2 className="w-4 h-4 ml-2" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
