import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Plus, Search, Check, Grid, List, Settings, LayoutGrid, Trash2 } from 'lucide-react';
import axios from 'axios';

function Dashboard() {
  const navigate = useNavigate();
  const [notebooks, setNotebooks] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [backendType, setBackendType] = useState('local'); // 'local' or 'gemini'
  const [apiKey, setApiKey] = useState('');

  useEffect(() => {
    fetchNotebooks();
  }, []);

  const fetchNotebooks = async () => {
    try {
      const res = await axios.get('/api/notebooks');
      setNotebooks(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const deleteNotebook = async (e, notebookId) => {
    e.stopPropagation();
    if (!window.confirm("Bạn có chắc chắn muốn xóa sổ tay này và toàn bộ dữ liệu bên trong không?")) return;
    try {
      await axios.delete(`/api/notebooks/${notebookId}`);
      setNotebooks(prev => prev.filter(nb => nb.id !== notebookId));
    } catch (err) {
      console.error(err);
      alert("Lỗi khi xóa sổ tay");
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    if (backendType === 'gemini' && !apiKey.trim()) {
      alert('Vui lòng nhập Gemini API Key!');
      return;
    }
    
    const id = Date.now().toString();
    try {
      await axios.post('/api/notebooks', {
        id,
        title: newTitle,
        is_private: backendType === 'local',
        gemini_api_key: backendType === 'gemini' ? apiKey : null
      });
      setShowModal(false);
      setNewTitle('');
      setApiKey('');
      navigate(`/notebook/${id}`);
    } catch (err) {
      console.error(err);
      if (err.response) {
        alert('Lỗi tạo sổ ghi chú: ' + (err.response.data.detail || err.response.data.message || err.message));
      } else {
        alert('Không thể kết nối đến AI. Hệ thống có thể đang khởi động, vui lòng thử lại sau vài giây!');
      }
    }
  };

  return (
    <div className="flex flex-col font-sans selection:bg-blue-500/30 w-full">
      {/* Header */}
      <header className="flex justify-between items-center p-4 border-b border-white/5">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
          <BookOpen className="text-white" size={24} />
          <span className="font-semibold text-lg tracking-tight">NotebookLM Mini</span>
        </div>
        <div className="flex items-center gap-4 text-sm font-medium">
          <button className="flex items-center gap-2 hover:bg-white/10 px-3 py-1.5 rounded-lg transition-colors">
            <Settings size={18} /> Cài đặt
          </button>
        </div>
      </header>

      {/* Main Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-8">
        
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex gap-6 text-sm font-medium text-gray-400">
            <button className="text-white border-b-2 border-white pb-1">Tất cả</button>
            <button className="hover:text-white transition-colors">Sổ ghi chú của tôi</button>
            <button className="hover:text-white transition-colors">Sổ ghi chú nổi bật</button>
          </div>
          
          <div className="flex items-center gap-3">
            <button className="w-10 h-10 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 transition">
              <Search size={18} />
            </button>
            <div className="flex bg-white/5 rounded-full p-1">
              <button className="p-2 bg-white/10 rounded-full text-white"><Check size={16} /></button>
              <button className="p-2 text-gray-400 hover:text-white"><Grid size={16} /></button>
            </div>
            <button 
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 bg-white text-black px-4 py-2 rounded-full font-medium hover:bg-gray-200 transition-colors shadow-lg"
            >
              <Plus size={18} /> Tạo mới
            </button>
          </div>
        </div>

        {/* Notebooks Grid */}
        <h2 className="text-xl font-medium mb-6">Sổ ghi chú của bạn</h2>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Create New Card */}
          <div 
            onClick={() => setShowModal(true)}
            className="aspect-[4/3] rounded-2xl bg-white/5 hover:bg-white/10 border border-transparent hover:border-white/20 transition-all cursor-pointer flex flex-col items-center justify-center group"
          >
            <div className="w-12 h-12 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Plus size={24} />
            </div>
            <span className="font-medium text-lg text-white">Tạo sổ ghi chú mới</span>
          </div>

          {/* Existing Notebooks */}
          {notebooks.map(nb => (
            <div 
              key={nb.id}
              onClick={() => navigate(`/notebook/${nb.id}`)}
              className="aspect-[4/3] rounded-2xl bg-white/5 border border-white/10 p-6 flex flex-col justify-end cursor-pointer hover:bg-white/10 transition-all hover:-translate-y-1 hover:shadow-xl relative overflow-hidden group"
            >
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent z-0"></div>
              
              <button 
                onClick={(e) => deleteNotebook(e, nb.id)}
                className="absolute top-4 right-4 z-20 p-2 bg-black/40 hover:bg-red-500/80 text-white rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 backdrop-blur-md"
                title="Xóa sổ ghi chú"
              >
                <Trash2 size={16} />
              </button>

              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold ${nb.is_private ? 'bg-green-500' : 'bg-blue-500'}`}>
                    {nb.is_private ? 'L' : 'G'}
                  </div>
                  <span className="text-xs font-medium text-gray-300">
                    {nb.is_private ? 'Local Model' : 'Gemini API'}
                  </span>
                </div>
                <h3 className="font-semibold text-xl text-white mb-1 line-clamp-2">{nb.title}</h3>
                <p className="text-xs text-gray-400">{new Date(nb.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          ))}
        </div>

      </main>

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#1C1F26] border border-white/10 rounded-2xl p-8 max-w-md w-full shadow-2xl">
            <h3 className="text-2xl font-semibold mb-6">Tạo sổ ghi chú</h3>
            
            <label className="block text-sm font-medium text-gray-400 mb-2">Tên sổ ghi chú</label>
            <input 
              type="text" 
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white mb-6 focus:outline-none focus:border-blue-500"
              placeholder="VD: Nghiên cứu sinh học..."
              autoFocus
            />

            <label className="block text-sm font-medium text-gray-400 mb-2">Chọn Bộ não AI (LLM)</label>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div 
                onClick={() => setBackendType('local')}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${backendType === 'local' ? 'border-green-500 bg-green-500/10' : 'border-white/10 bg-white/5 hover:border-white/30'}`}
              >
                <h4 className="font-semibold text-green-400 mb-1">AI Nội bộ (Auto-Tier)</h4>
                <p className="text-xs text-gray-400">Tự động tải & chạy AI phù hợp cấu hình máy. Offline 100%.</p>
              </div>
              <div 
                onClick={() => setBackendType('gemini')}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${backendType === 'gemini' ? 'border-blue-500 bg-blue-500/10' : 'border-white/10 bg-white/5 hover:border-white/30'}`}
              >
                <h4 className="font-semibold text-blue-400 mb-1">Gemini API</h4>
                <p className="text-xs text-gray-400">Siêu nhanh, thông minh. Chỉ dùng cho data công khai.</p>
              </div>
            </div>

            {backendType === 'gemini' && (
              <div className="mb-8 animate-fade-in">
                <label className="block text-sm font-medium text-gray-400 mb-2">Google Gemini API Key</label>
                <input 
                  type="password" 
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500"
                  placeholder="AIzaSy..."
                />
              </div>
            )}

            <div className="flex justify-end gap-3 mt-4">
              <button 
                onClick={() => setShowModal(false)}
                className="px-5 py-2.5 rounded-full text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                Hủy
              </button>
              <button 
                onClick={handleCreate}
                disabled={!newTitle.trim() || (backendType === 'gemini' && !apiKey.trim())}
                className="px-5 py-2.5 rounded-full text-sm font-medium bg-white text-black hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg"
              >
                Tạo sổ ghi chú
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default Dashboard;
