import React from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen w-screen flex flex-col bg-[#F9F9FB] text-gray-900 font-sans selection:bg-blue-200">
      
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-2">
          <BookOpen className="text-gray-700" size={24} />
          <span className="font-semibold text-xl tracking-tight text-gray-800">NotebookLM Mini</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center text-center px-4 animate-fade-in">
        <h1 className="text-6xl md:text-8xl font-medium tracking-tight mb-6">
          Tìm hiểu <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-500 to-green-400">mọi thứ</span>
        </h1>
        
        <p className="text-lg md:text-xl text-gray-600 max-w-3xl mb-12 leading-relaxed">
          Cộng sự nghiên cứu và tư duy, dựa trên thông tin mà bạn tin cậy, được xây dựng bằng
          các mô hình ngôn ngữ mới nhất (Local & Gemini).
        </p>
        
        <button 
          onClick={() => navigate('/dashboard')}
          className="bg-black hover:bg-gray-800 text-white px-8 py-4 rounded-full text-lg font-medium transition-transform transform hover:scale-105 active:scale-95 shadow-xl"
        >
          Bắt đầu sử dụng NotebookLM
        </button>
      </main>

      {/* Footer Title */}
      <div className="pb-12 text-center">
        <h2 className="text-3xl font-normal text-gray-800">
          Cộng sự nghiên cứu bằng AI của bạn
        </h2>
      </div>

    </div>
  );
}

export default Landing;
