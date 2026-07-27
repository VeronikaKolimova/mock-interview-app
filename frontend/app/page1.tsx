'use client';

import { useState, useRef, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

type Message = {
  role: "user" | "assistant";
  content: string;
  audioUrl?: string;
};

export default function InterviewPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [vacancyText, setVacancyText] = useState("");
  const [vacancyFileName, setVacancyFileName] = useState<string>("");
  const [resumeText, setResumeText] = useState("");
  const [resumeFileName, setResumeFileName] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isAdapting, setIsAdapting] = useState(false);
  const [interviewerType, setInterviewerType] = useState<"hr" | "techlead">("hr");
  const [isFinished, setIsFinished] = useState(false);
  const [showAdaptedResume, setShowAdaptedResume] = useState(false);
  const [adaptedResumeContent, setAdaptedResumeContent] = useState("");
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const vacancyFileRef = useRef<HTMLInputElement>(null);
  const resumeFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, showAdaptedResume]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: "vacancy" | "resume") => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExtensions.includes(fileExtension)) {
      alert(`Неподдерживаемый формат. Используйте: ${allowedExtensions.join(', ')}`);
      return;
    }

    setIsLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    const endpoint = type === "vacancy" ? "/api/upload-vacancy" : "/api/upload-resume";

    try {
      const response = await fetch(`${API_URL}${endpoint}`, { method: 'POST', body: formData });
      if (!response.ok) throw new Error("Ошибка загрузки");
      const data = await response.json();
      
      if (type === "vacancy") {
        setVacancyText(data.text);
        setVacancyFileName(file.name);
      } else {
        setResumeText(data.text);
        setResumeFileName(file.name);
      }
      alert(`✅ Файл "${file.name}" успешно загружен!`);
    } catch (error) {
      alert('Не удалось загрузить файл.');
    } finally {
      setIsLoading(false);
    }
  };

  const startInterview = async () => {
    setIsLoading(true);
    setIsFinished(false);
    try {
      const response = await fetch(`${API_URL}/api/interview/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interviewer: interviewerType,
          vacancy_text: vacancyText.trim() || undefined,
          tts_enabled: true,
        }),
      });
      if (!response.ok) throw new Error("Ошибка запуска");
      const data = await response.json();
      setSessionId(data.session_id);
      setMessages([{ role: "assistant", content: data.message.content, audioUrl: data.audio_url }]);
      if (data.audio_url) playAudio(data.audio_url);
    } catch (error) {
      alert("Не удалось начать интервью. Проверьте бэкенд.");
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || isFinished) return;
    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/interview/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, answer: userMessage, tts_enabled: true }),
      });
      if (!response.ok) throw new Error("Ошибка отправки");
      const data = await response.json();
      
      setMessages((prev) => [...prev, { role: "assistant", content: data.message.content, audioUrl: data.audio_url }]);
      
      if (data.is_finished) {
        setIsFinished(true);
      }
      
      if (data.audio_url) playAudio(data.audio_url);
    } catch (error) {
      alert("Ошибка связи с сервером.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdaptResume = async () => {
    if (!sessionId) return;
    if (!resumeText || resumeText.length < 20) {
      alert("⚠️ Сначала загрузите файл резюме или вставьте его текст на стартовом экране!");
      return;
    }

    setIsAdapting(true);
    try {
      const response = await fetch(`${API_URL}/api/adapt-resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          resume_text: resumeText
        }),
      });
      
      let data = null;
      try { data = await response.json(); } catch (e) { console.error("Ошибка парсинга", e); }

      if (!response.ok || !data || !data.adapted_resume) {
        const errorMsg = data?.detail || data?.message || `Ошибка сервера: ${response.status}`;
        throw new Error(errorMsg);
      }
      
      setAdaptedResumeContent(data.adapted_resume);
      setShowAdaptedResume(true);
    } catch (error: any) {
      console.error("Ошибка адаптации:", error);
      alert(`❌ Не удалось адаптировать резюме:\n\n${error.message}`);
    } finally {
      setIsAdapting(false);
    }
  };

  const playAudio = (url: string) => {
    if (audioRef.current) {
      audioRef.current.src = `${API_URL}${url}`;
      audioRef.current.play().catch(() => {});
    }
  };

  const resetAll = () => {
    setSessionId(null);
    setMessages([]);
    setInput("");
    setVacancyText("");
    setVacancyFileName("");
    setResumeText("");
    setResumeFileName("");
    setIsFinished(false);
    setShowAdaptedResume(false);
    setAdaptedResumeContent("");
  };

  if (!sessionId) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-2xl max-w-4xl w-full">
          <h1 className="text-3xl font-bold text-gray-800 mb-6 text-center">🎙️ Mock Interview SaaS</h1>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">1. Ваше резюме</label>
              <p className="text-[11px] text-gray-500 mb-2 flex items-center gap-1">
                <span>🔒</span> Личные данные удаляются автоматически. Мы их не храним.
              </p>
              <input ref={resumeFileRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => handleFileUpload(e, "resume")} className="hidden" id="resume-file" />
              <label htmlFor="resume-file" className={`flex flex-col items-center justify-center w-full h-24 border-2 border-dashed rounded-xl cursor-pointer transition mb-3 ${resumeFileName ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-500'}`}>
                {resumeFileName ? <span className="text-green-700 font-medium text-sm px-2 text-center">✅ {resumeFileName}</span> : <span className="text-gray-500">📄 Загрузить файл</span>}
              </label>
              <textarea
                value={resumeText}
                onChange={(e) => { setResumeText(e.target.value); if (e.target.value.length > 50) setResumeFileName("Текст вставлен вручную"); }}
                placeholder="Или вставьте текст резюме сюда..."
                className="w-full h-32 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none resize-none text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">2. Текст вакансии</label>
              <p className="text-[11px] text-gray-500 mb-2 flex items-center gap-1">
                <span>🔒</span> Используется только для адаптации, не сохраняется.
              </p>
              <input ref={vacancyFileRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => handleFileUpload(e, "vacancy")} className="hidden" id="vacancy-file" />
              <label htmlFor="vacancy-file" className={`flex flex-col items-center justify-center w-full h-24 border-2 border-dashed rounded-xl cursor-pointer transition mb-3 ${vacancyFileName ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-500'}`}>
                {vacancyFileName ? <span className="text-green-700 font-medium text-sm px-2 text-center">✅ {vacancyFileName}</span> : <span className="text-gray-500">📄 Загрузить файл</span>}
              </label>
              <textarea
                value={vacancyText}
                onChange={(e) => { setVacancyText(e.target.value); if (e.target.value.length > 50) setVacancyFileName("Текст вставлен вручную"); }}
                placeholder="Или вставьте текст вакансии сюда..."
                className="w-full h-32 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none resize-none text-sm"
              />
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">Тип интервьюера:</label>
            <div className="flex gap-4">
              {(["hr", "techlead"] as const).map((type) => (
                <button key={type} onClick={() => setInterviewerType(type)} className={`flex-1 py-3 rounded-lg border-2 font-semibold transition ${interviewerType === type ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600'}`}>
                  {type === "hr" ? "👩 HR-менеджер" : "👨‍💻 Техлид"}
                </button>
              ))}
            </div>
          </div>

          <button onClick={startInterview} disabled={isLoading} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl transition disabled:opacity-50">
            {isLoading ? "Загрузка..." : "Начать собеседование 🚀"}
          </button>
        </div>
        <audio ref={audioRef} className="hidden" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <header className="bg-white shadow-sm p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold text-gray-800">{interviewerType === "hr" ? "👩 HR-менеджер" : "👨‍💻 Техлид"}</h1>
        <button onClick={resetAll} className="text-sm text-red-600 hover:text-red-800 font-medium">Завершить и начать заново</button>
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-4 max-w-4xl mx-auto w-full">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] p-4 rounded-2xl shadow-sm ${msg.role === "user" ? "bg-blue-600 text-white rounded-br-none" : "bg-white text-gray-800 rounded-bl-none border border-gray-200"}`}>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</div>
              {msg.audioUrl && (
                <button onClick={() => playAudio(msg.audioUrl!)} className="mt-3 flex items-center gap-2 text-xs font-medium opacity-80 hover:opacity-100 transition">🔊 Прослушать</button>
              )}
            </div>
          </div>
        ))}
        
        {isFinished && resumeText && !showAdaptedResume && (
          <div className="flex justify-center my-6 animate-pulse">
            <button onClick={handleAdaptResume} disabled={isAdapting} className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-8 rounded-xl shadow-lg transition flex items-center gap-2">
              {isAdapting ? "⏳ Адаптируем с помощью AI..." : "✨ Адаптировать моё резюме под эту вакансию"}
            </button>
          </div>
        )}

        {showAdaptedResume && (
          <div className="bg-white border-2 border-green-200 rounded-2xl p-6 shadow-lg my-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-green-800">✅ Адаптированное резюме</h2>
              <button onClick={() => setShowAdaptedResume(false)} className="text-gray-500 hover:text-gray-700">Свернуть</button>
            </div>
            <div className="whitespace-pre-wrap text-sm text-gray-800 bg-gray-50 p-4 rounded-lg border border-gray-200 max-h-96 overflow-y-auto font-mono leading-relaxed">
              {adaptedResumeContent}
            </div>
            <div className="mt-4 text-center">
              <button onClick={() => navigator.clipboard.writeText(adaptedResumeContent)} className="text-blue-600 hover:text-blue-800 text-sm font-medium">📋 Скопировать в буфер обмена</button>
            </div>
          </div>
        )}

        {isLoading && !isAdapting && (
          <div className="flex justify-start"><div className="bg-white p-4 rounded-2xl rounded-bl-none border border-gray-200 shadow-sm flex gap-1"><span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span><span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></span><span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></span></div></div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {!isFinished && (
        <footer className="bg-white border-t p-4">
          <div className="max-w-4xl mx-auto flex gap-3">
            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !isLoading && sendMessage()} placeholder="Введите ваш ответ..." disabled={isLoading} className="flex-1 p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100" />
            <button onClick={sendMessage} disabled={isLoading || !input.trim()} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-semibold transition disabled:opacity-50">Отправить</button>
          </div>
        </footer>
      )}
    </div>
  );
}
