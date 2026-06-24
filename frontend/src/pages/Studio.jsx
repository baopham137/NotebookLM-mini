import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Bot, User, FileText, ChevronRight, Paperclip, Loader, Headphones, RefreshCw, BookOpen, Brain, Layers, X, Check, XCircle, Trash2, Link as LinkIcon, Plus, ArrowLeft, ShieldAlert, Zap, Trophy, Star, Lock, AudioLines, MonitorPlay, Video, Network, BarChart, Table, Heart } from 'lucide-react';
import QuizConfigModal from '../components/QuizConfigModal';
import FlashcardConfigModal from '../components/FlashcardConfigModal';
import PodcastConfigModal from '../components/PodcastConfigModal';
import MindmapConfigModal from '../components/MindmapConfigModal';
import ModelSelectionModal from '../components/ModelSelectionModal';

function Studio() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeNotebook, setActiveNotebook] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [studyGuide, setStudyGuide] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [podcastGenerating, setPodcastGenerating] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  
  // Quiz & Flashcard state
  const [showQuiz, setShowQuiz] = useState(false);
  const [showFlashcards, setShowFlashcards] = useState(false);
  const [podcastUrl, setPodcastUrl] = useState(null);
  const [currentFlashcard, setCurrentFlashcard] = useState(0);
  const [flashcardFlipped, setFlashcardFlipped] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState(null);

  // Gamification state removed
  const [activeFeature, setActiveFeature] = useState(null);
  const [configModal, setConfigModal] = useState(null); // 'quiz', 'flashcard', 'podcast', 'mindmap'
  const [modelModalConfig, setModelModalConfig] = useState(null);

  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlInputValue, setUrlInputValue] = useState('');
  const [uploadingDocs, setUploadingDocs] = useState([]);

  const messagesEndRef = useRef(null);

  // Auto scroll
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleAddExp = async (amount) => {
    if (!activeNotebook) return;
    try {
      const res = await fetch(`/api/notebooks/${activeNotebook.id}/add-exp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount })
      });
      if (res.ok) {
        const data = await res.json();
        setGamification(prev => ({ ...prev, ...data }));
        setExpToast(`+${amount} EXP`);
        setTimeout(() => setExpToast(null), 3000);
        if (data.leveled_up) {
           alert(`Chúc mừng! Bạn đã đạt Level ${data.level} và nhận được 1 SP!`);
        }
      }
    } catch(e) {}
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch data khi mount
  useEffect(() => {
    if (!id) return;
    
    const fetchData = async () => {
      try {
        const nbRes = await fetch('/api/notebooks');
        const nbs = await nbRes.json();
        const nb = nbs.find(n => n.id === id);
        if (nb) {
          setActiveNotebook(nb);
          
          const msgRes = await fetch(`/api/notebooks/${nb.id}/messages`);
          const msgs = await msgRes.json();
          if (msgs && msgs.length > 0) {
            setMessages(msgs);
          } else {
            setMessages([{ role: 'assistant', content: `Xin chào! Bạn đang ở sổ tay "${nb.title}". Hãy tải tài liệu hoặc gửi link cho tôi nhé!`, citations: [] }]);
          }

          const guideRes = await fetch(`/api/notebooks/${nb.id}/study-guide`);
          if (guideRes.ok) {
            const guide = await guideRes.json();
            setStudyGuide(guide);
          }

          const docRes = await fetch(`/api/notebooks/${nb.id}/documents`);
          if (docRes.ok) {
            const docs = await docRes.json();
            setDocuments(docs);
          }
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchData();
  }, [id]);


  // Polling Study Guide if it is null AND there are documents
  useEffect(() => {
    let intervalId;
    if (activeNotebook && !studyGuide && documents.length > 0) {
      intervalId = setInterval(async () => {
        try {
          const guideRes = await fetch(`/api/notebooks/${activeNotebook.id}/study-guide`);
          if (guideRes.ok) {
            const guide = await guideRes.json();
            if (guide) {
              setStudyGuide(guide);
              clearInterval(intervalId);
            }
          }
        } catch (e) {
          console.error("Lỗi khi poll Study Guide:", e);
        }
      }, 3000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeNotebook, studyGuide, documents]);

  const generatePodcast = async () => {
    setPodcastGenerating(true);
    try {
      const formData = new FormData();
      formData.append('notebook_id', activeNotebook.id);
      formData.append('style', podcastStyle);

      await fetch('/api/podcast/generate', {
        method: 'POST',
        body: formData
      });
      setTimeout(() => {
        setAudioUrl(`/api/podcast/audio/${activeNotebook?.id || 'default'}?t=${Date.now()}`);
        setPodcastGenerating(false);
      }, 2000);
    } catch (e) {
      console.error(e);
      setPodcastGenerating(false);
    }
  };

  const deleteNotebook = async () => {
    if (!activeNotebook) return;
    if (!window.confirm("Bạn có chắc chắn muốn xóa sổ tay này và toàn bộ dữ liệu bên trong không?")) return;
    try {
      const res = await fetch(`/api/notebooks/${activeNotebook.id}`, { method: 'DELETE' });
      if (res.ok) {
        navigate(-1);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUrlSubmit = async () => {
    if (!urlInputValue.trim() || !activeNotebook) return;
    
    // Basic URL validation
    let urlToSubmit = urlInputValue.trim();
    if (!urlToSubmit.startsWith('http://') && !urlToSubmit.startsWith('https://')) {
      urlToSubmit = 'https://' + urlToSubmit;
    }

    setLoading(true);
    setShowUrlInput(false);
    setUploadingDocs(prev => [...prev, { filename: urlToSubmit }]);
    
    try {
      const formData = new FormData();
      formData.append('url', urlToSubmit);
      formData.append('notebook_id', activeNotebook.id);

      const res = await fetch('/api/ingest/url', {
        method: 'POST',
        body: formData
      });
      
      if (!res.ok) {
        throw new Error(`Mã lỗi từ máy chủ: ${res.status}`);
      }

      await res.json();
      setUrlInputValue('');
      
      // Cập nhật lại danh sách documents
      const docRes = await fetch(`/api/notebooks/${activeNotebook.id}/documents`);
      if (docRes.ok) {
        setDocuments(await docRes.json());
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Lỗi khi nạp link: ${e.message}`, citations: [] }]);
    } finally {
      setLoading(false);
      setUploadingDocs(prev => prev.filter(d => d.filename !== urlToSubmit));
    }
  };

  const handleFileUpload = async (e) => {
    if (!activeNotebook) return;
    const file = e.target.files[0];
    if (!file) return;

    const isImage = file.name.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i);
    const isAudio = file.name.match(/\.(mp3|wav|flac|ogg|m4a)$/i);

    if (isImage || isAudio) {
      try {
        const statusRes = await fetch('/api/system/models-status');
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (isImage && !statusData.vision_configured) {
            setModelModalConfig({ type: 'vision', fileToUpload: file });
            e.target.value = null;
            return;
          }
          if (isAudio && !statusData.audio_configured) {
            setModelModalConfig({ type: 'audio', fileToUpload: file });
            e.target.value = null;
            return;
          }
        }
      } catch (err) {
        console.error("Lỗi khi check model status", err);
      }
    }

    proceedWithUpload(file);
    e.target.value = null;
  };

  const proceedWithUpload = async (file) => {
    setUploading(true);
    setUploadingDocs(prev => [...prev, { filename: file.name }]);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('notebook_id', activeNotebook.id);

    try {
      const response = await fetch('/api/ingest/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();
      
      // Cập nhật lại danh sách documents
      const docRes = await fetch(`/api/notebooks/${activeNotebook.id}/documents`);
      if (docRes.ok) {
        setDocuments(await docRes.json());
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: `❌ Lỗi khi tải tệp: ${err.message}`, citations: [] }]);
    } finally {
      setUploading(false);
      setUploadingDocs(prev => prev.filter(d => d.filename !== file.name));
    }
  };

  const deleteDocument = async (filename) => {
    if (!activeNotebook) return;
    if (!window.confirm(`Bạn có chắc muốn xóa tài liệu "${filename}"?`)) return;
    
    try {
      const res = await fetch(`/api/notebooks/${activeNotebook.id}/documents?filename=${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.filename !== filename));
      }
    } catch (err) {
      console.error('Error deleting document:', err);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !activeNotebook) return;
    
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      setMessages(prev => [...prev, { role: 'assistant', content: '', citations: [] }]);
      
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, notebook_id: activeNotebook.id })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          handleAddExp(5);
          break;
        }
        
        buffer += decoder.decode(value, { stream: true });
        
        const events = buffer.split('\n\n');
        buffer = events.pop() || "";
        
        for (const event of events) {
          if (event.startsWith("data: ")) {
            const dataStr = event.substring(6);
            try {
              const data = JSON.parse(dataStr);
              
              setMessages(prev => {
                const newMessages = [...prev];
                const lastIndex = newMessages.length - 1;
                
                if (data.type === 'citations') {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    citations: data.citations
                  };
                } else if (data.type === 'chunk') {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    content: newMessages[lastIndex].content + data.text,
                    status: null
                  };
                } else if (data.type === 'status') {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    status: data.message
                  };
                }
                
                return newMessages;
              });
            } catch (e) {
              console.error("Lỗi parse JSON SSE", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        newMessages[lastIndex] = {
          ...newMessages[lastIndex],
          content: 'Xin lỗi, có lỗi xảy ra khi kết nối tới LLM Engine.'
        };
        return newMessages;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!activeNotebook) return;
    setEvaluating(true);
    setEvalResult(null);
    try {
      const formData = new FormData();
      formData.append('notebook_id', activeNotebook.id);
      const res = await fetch('/api/evaluate', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        setEvalResult(data.metrics);
      } else {
        alert("Lỗi đánh giá: " + data.message);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setEvaluating(false);
    }
  };

  const handleFeatureClick = (feature) => {
    if (documents.length === 0) {
      alert("Bạn chưa nạp tài liệu. Vui lòng tải lên tài liệu hoặc thêm link để sử dụng tính năng này!");
      return;
    }
    
    // Nếu click lại vào tab đang mở thì đóng nó lại
    if (activeFeature === feature) {
      setActiveFeature(null);
      return;
    }

    // Kiểm tra xem dữ liệu đã có chưa, nếu chưa có thì tự động tạo với cấu hình mặc định
    if (feature === 'quiz' && (!studyGuide?.quiz || studyGuide.quiz.length === 0)) {
      handleCustomGenerate('quiz', {
        topic: "Tổng hợp toàn bộ kiến thức",
        difficulty: "Vừa",
        language: "Tiếng Việt",
        quantity: 10
      });
      return;
    }

    if (feature === 'flashcard' && (!studyGuide?.flashcards || studyGuide.flashcards.length === 0)) {
      handleCustomGenerate('flashcards', {
        topic: "Tổng hợp toàn bộ kiến thức",
        language: "Tiếng Việt",
        quantity: 20
      });
      return;
    }

    if (feature === 'mindmap' && (!studyGuide?.mindmap)) {
      handleCustomGenerate('mindmap', {
        topic: "Tổng hợp toàn bộ kiến thức"
      });
      return;
    }

    if (feature === 'podcast' && (!audioUrl)) {
      handleCustomGenerate('podcast', {
        topic: "Tóm tắt nhanh kiến thức chính (khoảng 2 phút)",
        language: "Tiếng Việt"
      });
      return;
    }
    
    // Nếu đã có dữ liệu thì chỉ việc hiển thị
    setActiveFeature(feature);
  };


  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading && input.trim()) {
        handleSend();
      }
    }
  };

  const handleCustomGenerate = async (type, config) => {
    try {
      setConfigModal(null);
      alert(`Hệ thống đang xử lý tạo ${type === 'flashcards' ? 'thẻ ghi nhớ' : type} tùy chỉnh. Vui lòng đợi...`);
      const res = await fetch(`/api/notebooks/${activeNotebook.id}/${type}/custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        const data = await res.json();
        const guideRes = await fetch(`/api/notebooks/${activeNotebook.id}/study-guide`);
        if (guideRes.ok) setStudyGuide(await guideRes.json());
        
        if (type === 'podcast' && data.audio_url) {
          setAudioUrl(data.audio_url);
        }
        alert("Tạo thành công!");
        setActiveFeature(type === 'flashcards' ? 'flashcard' : type);
      } else {
        alert("Có lỗi xảy ra khi tạo.");
      }
    } catch (e) {
      console.error(e);
      alert("Lỗi kết nối.");
    }
  };

  if (!activeNotebook) return <div className="h-screen w-full flex items-center justify-center bg-[#131314] text-white"><Loader className="animate-spin" size={32} /></div>;

  return (
    <div className="h-screen w-full flex bg-[#131314] text-white overflow-hidden font-sans selection:bg-blue-500/30">
      {/* Cột 1: Left Sidebar (Sources) */}
      <div className="w-72 flex-shrink-0 h-full border-r border-white/5 bg-[#131314] flex flex-col p-4 z-10 relative">
        <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-8 w-fit transition-colors">
          <ArrowLeft size={18} /> Quay lại
        </button>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2 text-gray-200">
          <Layers size={18} className="text-blue-400" /> Nguồn dữ liệu
        </h2>
        
        <div className="flex-1 overflow-y-auto scrollbar-hide space-y-3">
          {documents.length === 0 && uploadingDocs.length === 0 ? (
            <div className="text-center text-gray-500 text-sm mt-10">Chưa có dữ liệu nào</div>
          ) : (
            <>
              {uploadingDocs.map((doc, index) => (
                <div key={`up-${index}`} className="p-3 bg-white/5 rounded-xl border border-white/10 flex items-center gap-3 opacity-70">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
                    <Loader size={20} className="animate-spin" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate text-gray-200" title={doc.filename}>{doc.filename}</p>
                    <p className="text-xs text-blue-400 truncate mt-1">Đang nạp...</p>
                  </div>
                </div>
              ))}
              {documents.map((doc, index) => (
                <div key={`doc-${index}`} className="p-3 bg-white/5 rounded-xl border border-white/10 flex items-center justify-between gap-3 group">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0 relative">
                      {doc.filename.includes('http') || doc.filename.includes('YouTube') ? <LinkIcon size={20} /> : <FileText size={20} />}
                      <div className="absolute -bottom-1 -right-1 bg-green-500 rounded-full text-[#131314] p-0.5">
                        <Check size={10} strokeWidth={4} />
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate text-gray-200" title={doc.filename}>{doc.filename}</p>
                      <p className="text-xs text-gray-500 truncate">{new Date(doc.created_at).toLocaleString('vi-VN')}</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => deleteDocument(doc.filename)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded text-gray-400 hover:text-red-400 hover:bg-white/10 transition-all shrink-0"
                    title="Xóa tài liệu"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </>
          )}
        </div>

        <div className="pt-4 mt-auto border-t border-white/5">
          <button 
            onClick={() => setShowUrlInput(!showUrlInput)}
            className="w-full bg-white/5 hover:bg-white/10 text-white py-3 rounded-xl flex justify-center items-center gap-2 font-medium transition-colors mb-2 border border-white/10"
          >
            <LinkIcon size={18} /> Thêm Link
          </button>
          <button 
            onClick={() => document.getElementById('file-upload').click()}
            className="w-full bg-white text-black hover:bg-gray-200 py-3 rounded-xl flex justify-center items-center gap-2 font-medium transition-colors shadow-lg"
          >
            <Plus size={18} /> Tải tệp lên
          </button>
        </div>
      </div>

      {/* Cột 2: Center (Chat) */}
      <div className="flex-1 flex flex-col h-full border-r border-white/5 p-4 max-w-4xl mx-auto relative z-10">
      <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileText className="text-electric-blue" size={24}/>
            Phòng Chat
          </h2>
          <span className="bg-white/10 text-xs px-2 py-1 rounded-full text-gray-300">
            {activeNotebook?.title || "Chưa chọn Sổ tay"}
          </span>
        </div>
        <div className="flex items-center gap-2">

          {evalResult && (
            <div className="flex gap-2 text-xs mr-2">
              <span className="bg-green-500/20 text-green-400 px-2 py-1 rounded border border-green-500/30">
                Chính xác: {evalResult.faithfulness.toFixed(2)}
              </span>
              <span className="bg-blue-500/20 text-blue-400 px-2 py-1 rounded border border-blue-500/30">
                Ngữ cảnh: {evalResult.context_precision.toFixed(2)}
              </span>
            </div>
          )}
          <button 
            onClick={handleEvaluate}
            disabled={evaluating}
            className="text-sm px-3 py-1.5 rounded-lg border border-yellow-500/50 bg-yellow-500/20 text-yellow-500 hover:bg-yellow-500/30 transition-colors disabled:opacity-50 flex items-center gap-1"
            title="Đánh giá chất lượng RAG bằng Ragas"
          >
            {evaluating ? <Loader size={14} className="animate-spin" /> : <Brain size={14} />}
            Đánh giá AI
          </button>
          <button 
            onClick={deleteNotebook}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-400 hover:bg-white/5 transition-colors"
            title="Xóa sổ tay"
          >
            <Trash2 size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-hide flex flex-col gap-6 pb-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-gradient-to-br from-neon-purple to-pink-500' : 'bg-gradient-to-br from-electric-blue to-cyan-400'}`}>
              {msg.role === 'assistant' ? <Bot size={20} className="text-white" /> : <User size={20} className="text-white" />}
            </div>
            <div className={`flex flex-col gap-2 max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`px-5 py-3.5 rounded-2xl text-[15px] leading-relaxed shadow-lg ${
                msg.role === 'user' 
                  ? 'bg-surface border border-white/10 text-white rounded-tr-sm' 
                  : 'glass-panel text-gray-100 rounded-tl-sm'
              }`}>
                {msg.content ? (
                  <div className="relative">
                    {msg.content.split('\n').map((line, i, arr) => (
                      <span key={i}>
                        {line}
                        {msg.role === 'assistant' && loading && idx === messages.length - 1 && i === arr.length - 1 && (
                          <span className="inline-block w-2 h-4 bg-electric-blue animate-pulse ml-1 align-middle rounded-sm shadow-[0_0_8px_rgba(37,99,235,0.8)]"></span>
                        )}
                        <br />
                      </span>
                    ))}
                  </div>
                ) : (
                  msg.role === 'assistant' && loading && idx === messages.length - 1 && (
                    <div className="flex flex-col gap-3">
                      <span className="flex gap-1 items-center h-5">
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></span>
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.4s'}}></span>
                      </span>
                      {msg.status && (
                        <div className="flex items-center gap-2 text-xs text-electric-blue font-medium animate-pulse">
                          <Loader size={12} className="animate-spin" />
                          {msg.status}
                        </div>
                      )}
                    </div>
                  )
                )}
              </div>
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {msg.citations.map((cit, cidx) => (
                    <div key={cidx} className="flex items-center gap-1.5 text-xs bg-electric-blue/10 border border-electric-blue/30 text-electric-blue px-2.5 py-1 rounded-full cursor-pointer hover:bg-electric-blue/20 transition-colors">
                      <span className="font-semibold">{cit.marker}</span>
                      <ChevronRight size={12} className="opacity-50" />
                      <span className="truncate max-w-[150px] opacity-80">{cit.filename}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="pt-4">
        <div className="glass-panel p-2 flex items-end gap-2 rounded-2xl relative group focus-within:shadow-[0_0_20px_rgba(37,99,235,0.2)] focus-within:border-electric-blue/40 transition-all duration-300">
          
          <div className="relative">
            {showUrlInput && (
              <div className="absolute bottom-full left-0 mb-2 bg-surface border border-white/10 p-2 rounded-lg shadow-xl flex gap-2 z-20 w-80">
                <input 
                  type="text" 
                  value={urlInputValue}
                  onChange={(e) => setUrlInputValue(e.target.value)}
                  placeholder="Dán link YouTube / Website..." 
                  className="flex-1 bg-black/30 text-sm px-3 py-2 rounded-md outline-none text-white border border-white/10 focus:border-electric-blue"
                  onKeyDown={(e) => e.key === 'Enter' && handleUrlSubmit()}
                />
                <button 
                  onClick={handleUrlSubmit}
                  className="bg-electric-blue px-3 rounded-md text-white hover:bg-blue-600 transition-colors"
                >
                  <Check size={16}/>
                </button>
              </div>
            )}
            <button 
              onClick={() => setShowUrlInput(!showUrlInput)}
              className="p-3 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-all"
              title="Nhập Link Website hoặc YouTube"
            >
              <LinkIcon size={20} />
            </button>
          </div>
          
          <button 
            onClick={() => document.getElementById('file-upload').click()}
            className="p-3 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-all"
            title="Tải lên PDF/Doc/Audio"
          >
            <Paperclip size={20} />
          </button>
          <input 
            type="file" 
            id="file-upload" 
            className="hidden" 
            onChange={handleFileUpload}
            accept=".pdf,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,.mp3,.wav,.m4a"
          />

          <textarea 
            className="flex-1 bg-transparent border-none px-2 py-3 text-[15px] text-white focus:outline-none focus:ring-0 resize-none min-h-[50px] max-h-[150px] scrollbar-hide"
            placeholder="Hỏi bất cứ điều gì về tài liệu..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
          />
          <button 
            className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
              input.trim() && !loading 
                ? 'bg-electric-blue text-white hover:bg-blue-500 shadow-[0_0_15px_rgba(37,99,235,0.4)]' 
                : 'bg-white/5 text-gray-500 cursor-not-allowed'
            }`}
            onClick={handleSend} 
            disabled={!input.trim() || loading}
          >
            <Send size={20} className={input.trim() && !loading ? 'translate-x-0.5 -translate-y-0.5' : ''} />
          </button>
        </div>
        <div className="text-center mt-3 text-xs text-gray-500">
          NotebookLM Mini có thể đưa ra thông tin không chính xác. Hãy luôn kiểm tra lại nguồn trích dẫn.
        </div>
      </div>
      </div>

      <div className="w-80 lg:w-96 flex-shrink-0 h-full p-4 overflow-y-auto scrollbar-hide bg-[#131314] flex flex-col gap-6 border-l border-white/5 relative">

        <div className={`glass-panel p-5 rounded-2xl border transition-all border-white/10`}>
          <div className="flex justify-between items-center mb-3">
            <h3 className={`text-lg font-bold flex items-center gap-2 transition-colors text-electric-blue`}>
              <BookOpen size={20} /> Cẩm Nang Học Tập
            </h3>
          </div>
          
          <div className="mt-4">
              <div className="flex flex-col gap-2 mb-4">
                <div className="flex border border-white/10 rounded-xl overflow-hidden bg-white/5 transition-all focus-within:ring-1 focus-within:ring-electric-blue">
                  <button 
                    onClick={() => handleFeatureClick('quiz')}
                    className={`flex-1 flex items-center gap-2 p-3 text-left hover:bg-white/10 transition-colors ${activeFeature === 'quiz' ? 'bg-electric-blue/20 text-electric-blue' : 'text-gray-300'}`}
                  >
                    <Brain size={18} className="flex-shrink-0" />
                    <span className="font-semibold text-sm">Bài kiểm tra</span>
                  </button>
                  <button onClick={() => setConfigModal('quiz')} className="px-3 hover:bg-white/10 border-l border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">
                    <ChevronRight size={18} />
                  </button>
                </div>

                <div className="flex border border-white/10 rounded-xl overflow-hidden bg-white/5 transition-all focus-within:ring-1 focus-within:ring-neon-purple">
                  <button 
                    onClick={() => handleFeatureClick('flashcard')}
                    className={`flex-1 flex items-center gap-2 p-3 text-left hover:bg-white/10 transition-colors ${activeFeature === 'flashcard' ? 'bg-neon-purple/20 text-neon-purple' : 'text-gray-300'}`}
                  >
                    <Layers size={18} className="flex-shrink-0" />
                    <span className="font-semibold text-sm">Thẻ ghi nhớ</span>
                  </button>
                  <button onClick={() => setConfigModal('flashcard')} className="px-3 hover:bg-white/10 border-l border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">
                    <ChevronRight size={18} />
                  </button>
                </div>

                <div className="flex border border-white/10 rounded-xl overflow-hidden bg-white/5 transition-all focus-within:ring-1 focus-within:ring-pink-500">
                  <button 
                    onClick={() => handleFeatureClick('mindmap')}
                    className={`flex-1 flex items-center gap-2 p-3 text-left hover:bg-white/10 transition-colors ${activeFeature === 'mindmap' ? 'bg-pink-500/20 text-pink-400' : 'text-gray-300'}`}
                  >
                    <Network size={18} className="flex-shrink-0" />
                    <span className="font-semibold text-sm">Bản đồ tư duy</span>
                  </button>
                  <button onClick={() => setConfigModal('mindmap')} className="px-3 hover:bg-white/10 border-l border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">
                    <ChevronRight size={18} />
                  </button>
                </div>

                <div className="flex border border-white/10 rounded-xl overflow-hidden bg-white/5 transition-all focus-within:ring-1 focus-within:ring-blue-500">
                  <button 
                    onClick={() => handleFeatureClick('podcast')}
                    className={`flex-1 flex items-center gap-2 p-3 text-left hover:bg-white/10 transition-colors ${activeFeature === 'podcast' ? 'bg-blue-500/20 text-blue-400' : 'text-gray-300'}`}
                  >
                    <AudioLines size={18} className="flex-shrink-0" />
                    <span className="font-semibold text-sm">Tổng quan bằng âm thanh</span>
                  </button>
                  <button onClick={() => setConfigModal('podcast')} className="px-3 hover:bg-white/10 border-l border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>

              {/* Inline Content Areas */}
              {activeFeature === 'podcast' && (
                <div className="bg-black/20 p-4 rounded-xl border border-white/5 animate-fade-in">
                  <h4 className="font-bold text-electric-blue mb-2 text-sm flex items-center gap-2">
                    <AudioLines size={16} /> Podcast Generator
                  </h4>
                  {!audioUrl ? (
                    <div className="flex flex-col gap-3">
                      <p className="text-xs text-gray-400">Tạo bản thu âm trò chuyện giữa 2 MC ảo.</p>
                      

                      <button 
                        onClick={generatePodcast}
                        disabled={podcastGenerating}
                        className="w-full bg-gradient-to-r from-electric-blue to-neon-purple hover:opacity-90 text-white font-medium py-2 rounded-xl transition-all disabled:opacity-50 flex justify-center items-center gap-2 text-sm"
                      >
                        {podcastGenerating ? <RefreshCw className="animate-spin" size={16} /> : <Headphones size={16} />}
                        {podcastGenerating ? "Đang tạo..." : "Tạo Podcast"}
                      </button>
                    </div>
                  ) : (
                    <div className="mt-2">
                      <audio controls className="w-full h-10 rounded outline-none" src={audioUrl} />
                    </div>
                  )}
                </div>
              )}
              
              {activeFeature === 'flashcard' && studyGuide?.flashcards && (
                <div className="bg-black/20 p-4 rounded-xl border border-white/5 animate-fade-in flex flex-col items-center">
                  <div className="w-full flex justify-between items-center mb-4 text-sm text-gray-400">
                    <span>Thẻ {currentFlashcard + 1} / {studyGuide.flashcards.length}</span>
                  </div>
                  
                  <div 
                    className="relative w-full aspect-[4/3] perspective-1000 cursor-pointer group"
                    onClick={() => setFlashcardFlipped(!flashcardFlipped)}
                  >
                    <div className={`w-full h-full absolute top-0 left-0 transition-all duration-500 transform-style-preserve-3d ${flashcardFlipped ? 'rotate-y-180' : ''}`}>
                      <div className="absolute w-full h-full backface-hidden bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-center text-center shadow-lg group-hover:border-neon-purple/50 transition-colors">
                        <p className="text-sm font-medium">{studyGuide.flashcards[currentFlashcard].front}</p>
                      </div>
                      <div className="absolute w-full h-full backface-hidden bg-neon-purple/10 border border-neon-purple/30 rounded-xl p-4 flex items-center justify-center text-center rotate-y-180 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                        <p className="text-sm text-gray-200">{studyGuide.flashcards[currentFlashcard].back}</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 mt-4 w-full">
                    <button 
                      onClick={() => { setFlashcardFlipped(false); setCurrentFlashcard(Math.max(0, currentFlashcard - 1)); }}
                      disabled={currentFlashcard === 0}
                      className="flex-1 bg-white/5 py-2 rounded-lg text-xs disabled:opacity-30"
                    >
                      Trước
                    </button>
                    <button 
                      onClick={() => { setFlashcardFlipped(false); setCurrentFlashcard(Math.min(studyGuide.flashcards.length - 1, currentFlashcard + 1)); }}
                      disabled={currentFlashcard === studyGuide.flashcards.length - 1}
                      className="flex-1 bg-white/5 py-2 rounded-lg text-xs disabled:opacity-30"
                    >
                      Sau
                    </button>
                  </div>
                </div>
              )}

              {activeFeature === 'mindmap' && (
                <div className="bg-black/20 p-4 rounded-xl border border-white/5 animate-fade-in flex flex-col">
                  <h4 className="font-bold text-pink-400 mb-2 text-sm flex items-center gap-2">
                    <Network size={16} /> Bản đồ tư duy
                  </h4>
                  <div className="text-sm text-gray-300 whitespace-pre-wrap mt-2 overflow-y-auto max-h-96 pr-2 custom-scrollbar">
                    {studyGuide?.mindmap || "Chưa có bản đồ tư duy. Hãy click vào mũi tên bên cạnh để tạo một bản đồ tư duy tùy chỉnh!"}
                  </div>
                </div>
              )}
              
              {activeFeature === 'quiz' && studyGuide?.quiz && (
                <div className="bg-black/20 p-4 rounded-xl border border-white/5 animate-fade-in flex flex-col">

                    <div className="space-y-4">
                      {studyGuide.quiz.map((q, idx) => (
                        <div key={idx} className="bg-white/5 p-3 rounded-lg border border-white/10">
                          <p className="font-semibold text-xs mb-2">{idx + 1}. {q.question}</p>
                          <div className="space-y-1">
                            {q.options.map((opt, oIdx) => {
                              const isSelected = quizAnswers[idx] === oIdx;
                              const isCorrect = q.answer === oIdx;
                              let btnClass = "w-full text-left p-2 rounded border transition-all text-xs ";
                              
                              if (!quizSubmitted) {
                                btnClass += isSelected ? "border-electric-blue bg-electric-blue/20 text-white" : "border-white/10 hover:bg-white/10 text-gray-400";
                              } else {
                                if (isCorrect) btnClass += "border-green-500 bg-green-500/20 text-white";
                                else if (isSelected && !isCorrect) btnClass += "border-red-500 bg-red-500/20 text-white";
                                else btnClass += "border-white/5 text-gray-500 opacity-50";
                              }

                              return (
                                <button 
                                  key={oIdx} 
                                  disabled={quizSubmitted}
                                  onClick={() => setQuizAnswers({...quizAnswers, [idx]: oIdx})}
                                  className={btnClass}
                                >
                                  {opt}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                      {!quizSubmitted ? (
                        <button 
                          onClick={() => setQuizSubmitted(true)}
                          disabled={Object.keys(quizAnswers).length !== studyGuide.quiz.length}
                          className="bg-electric-blue text-white px-4 py-2 rounded-lg text-xs w-full disabled:opacity-50"
                        >
                          Nộp bài
                        </button>
                      ) : (
                        <button 
                          onClick={() => {setQuizAnswers({}); setQuizSubmitted(false);}}
                          className="bg-white/10 text-white px-4 py-2 rounded-lg text-xs w-full"
                        >
                          Làm lại
                        </button>
                      )}
                    </div>
                </div>
              )}

            </div>
        </div>
      </div>

      {configModal === 'quiz' && (
        <QuizConfigModal 
          onClose={() => setConfigModal(null)} 
          onSubmit={(config) => handleCustomGenerate('quiz', config)} 
        />
      )}
      {configModal === 'flashcard' && (
        <FlashcardConfigModal 
          onClose={() => setConfigModal(null)} 
          onSubmit={(config) => handleCustomGenerate('flashcards', config)} 
        />
      )}
      {configModal === 'podcast' && (
        <PodcastConfigModal 
          onClose={() => setConfigModal(null)} 
          onSubmit={(config) => handleCustomGenerate('podcast', config)} 
        />
      )}
      {configModal === 'mindmap' && (
        <MindmapConfigModal 
          onClose={() => setConfigModal(null)} 
          onSubmit={(config) => handleCustomGenerate('mindmap', config)} 
        />
      )}

      {modelModalConfig && (
        <ModelSelectionModal
          isOpen={true}
          onClose={() => setModelModalConfig(null)}
          type={modelModalConfig.type}
          fileToUpload={modelModalConfig.fileToUpload}
          onSuccess={(file) => {
            setModelModalConfig(null);
            proceedWithUpload(file);
          }}
        />
      )}

    </div>
  );
}

export default Studio;
