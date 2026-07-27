'use client';

export const dynamic = 'force-dynamic';

import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';

interface Message {
  role: string;
  content: string;
  audioUrl?: string;
}

export default function InterviewPage() {
  const searchParams = useSearchParams();
  const interviewer = searchParams.get('interviewer') || 'hr';
  
  const [inputMode, setInputMode] = useState<'text' | 'voice'>('text');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ttsEnabled, setTtsEnabled] = useState(true); 
  const [isStarted, setIsStarted] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const playAudio = (url: string) => {
    if (!ttsEnabled || !url) return;
    const audio = new Audio(`http://127.0.0.1:8001${url}`);
    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch(error => {
        console.warn("Автовоспроизведение заблокировано браузером:", error);
      });
    }
  };

  const endsWithPunctuation = (text: string): boolean => {
    return /[.?!…]$/.test(text.trim());
  };

  const startInterview = async () => {
    setIsStarted(true);
    setLoading(true);
    const vacancyText = sessionStorage.getItem('mock_interview_vacancy') || '';
    
    try {
      const response = await fetch('http://127.0.0.1:8001/api/interview/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          interviewer, 
          tts_enabled: ttsEnabled,
          vacancy_text: vacancyText
        }),
      });
      
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      
      setSessionId(data.session_id);
      const initialMessage: Message = { 
        role: 'assistant', 
        content: data.message.content,
        audioUrl: data.audio_url 
      };
      setMessages([initialMessage]);
      playAudio(data.audio_url);
      
    } catch (error) {
      console.error('Ошибка начала интервью:', error);
      setMessages([{ 
        role: 'assistant', 
        content: '⚠️ Не удалось подключиться к серверу. Убедитесь, что backend запущен на порту 8001.' 
      }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleRecording = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Ваш браузер не поддерживает распознавание речи. Пожалуйста, используйте Google Chrome или Edge.');
      return;
    }

    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    } else {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.lang = 'ru-RU';
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;

      recognitionRef.current.onresult = (event: any) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setInput(prev => (prev ? prev + ' ' + finalTranscript : finalTranscript));
        }
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error('Ошибка распознавания:', event.error);
        if (event.error === 'not-allowed') {
          alert('Доступ к микрофону запрещен. Разрешите его в настройках браузера.');
        }
        setIsRecording(false);
      };

      recognitionRef.current.onend = () => {
        setIsRecording(false);
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      };

      recognitionRef.current.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => setRecordingTime(prev => prev + 1), 1000);
    }
  };
  
  const submitAnswer = async () => {
    if (!input.trim() || !sessionId) return;
    
    setLoading(true);
    const currentInput = input;
    setInput('');
    
    const userMessage: Message = { role: 'user', content: currentInput };
    setMessages(prev => [...prev, userMessage]);
    
    try {
      const response = await fetch('http://127.0.0.1:8001/api/interview/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          answer: currentInput,
          tts_enabled: ttsEnabled
        }),
      });
      
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      
      const assistantMessage: Message = { 
        role: 'assistant', 
        content: data.message.content,
        audioUrl: data.audio_url 
      };
      setMessages(prev => [...prev, assistantMessage]);
      playAudio(data.audio_url);
      
      if (data.is_finished) {
        setMessages(prev => [...prev, { 
          role: 'system', 
          content: '🎉 Интервью успешно завершено! Вы можете начать новое собеседование.' 
        }]);
      }
    } catch (error) {
      console.error('Ошибка отправки ответа:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: '⚠️ Ошибка сервера при обработке ответа.' 
      }]);
    } finally {
      setLoading(false);
    }
  };

  if (!isStarted) {
    return (
      <div className="flex flex-col h-screen bg-gray-50 items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-xl text-center max-w-md w-full">
          <h1 className="text-3xl font-bold mb-4">
            {interviewer === 'hr' ? '👩 Анна (HR)' : '👨‍💻 Дмитрий (Техлид)'}
          </h1>
          <p className="text-gray-600 mb-6">
            Для корректной работы озвучки браузер требует вашего разрешения. 
            Нажмите кнопку ниже, чтобы начать интервью и включить звук.
          </p>
          
          <div className="mb-6 flex items-center justify-center gap-2">
            <input
              type="checkbox"
              id="tts-init"
              checked={ttsEnabled}
              onChange={(e) => setTtsEnabled(e.target.checked)}
              className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="tts-init" className="text-gray-700 font-medium cursor-pointer">
              🔊 Включить озвучку ответов
            </label>
          </div>

          <button
            onClick={startInterview}
            disabled={loading}
            className="w-full px-6 py-4 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-400 font-bold text-lg transition flex items-center justify-center gap-2 shadow-lg"
          >
            {loading ? <span className="animate-spin">⏳</span> : '▶️ Начать интервью'}
          </button>
          
          <a href="/" className="block mt-6 text-gray-500 hover:text-gray-800 transition">
            ← Вернуться на главную
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-gray-800 text-white p-4 shadow-lg">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">
            {interviewer === 'hr' ? '👩 Анна (HR)' : '👨‍💻 Дмитрий (Техлид)'}
          </h1>
          <a href="/" className="text-gray-300 hover:text-white transition">← На главную</a>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] p-4 rounded-lg shadow relative ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : msg.role === 'system'
                  ? 'bg-green-100 text-green-800 border border-green-300 w-full text-center font-medium'
                  : 'bg-white text-gray-900 border border-gray-200'
              }`}>
                <div className="whitespace-pre-wrap leading-relaxed">
                  {msg.role === 'assistant' ? (
                    (() => {
                      const rawText = msg.content || "";
                      const feedbackMatch = rawText.match(/(?:\*\*|---)?\s*Оценка\s*:\s*(?:\*\*|---)?([\s\S]*?)(?=(?:\*\*|---)?\s*Вопрос\s*:|$)/i);
                      const questionMatch = rawText.match(/(?:\*\*|---)?\s*Вопрос\s*:\s*(?:\*\*|---)?([\s\S]*)/i);

                      let feedback = "Хорошо, я вас услышала.";
                      let question = "";

                      if (feedbackMatch) {
                        feedback = feedbackMatch[1].replace(/\?/g, ".").replace(/\*+|---/g, "").trim();
                      }
                      if (questionMatch) {
                        question = questionMatch[1].replace(/\*+|---/g, "").trim();
                      }
                      if (!feedbackMatch && !questionMatch) {
                        feedback = rawText.replace(/\*+|---/g, "").trim();
                        question = "";
                      }

                      return (
                        <>
                          <div className="text-gray-600 mb-3 italic">{feedback}</div>
                          {question && (
                            <div className="text-blue-700 font-semibold text-lg mt-2">{question}</div>
                          )}
                        </>
                      );
                    })()
                  ) : (
                    <>
                      {msg.content}
                      {msg.role === 'user' && msg.content && !endsWithPunctuation(msg.content) && '...'}
                    </>
                  )}
                </div>
                
                {msg.role === 'assistant' && msg.audioUrl && ttsEnabled && (
                  <button
                    onClick={() => playAudio(msg.audioUrl!)}
                    className="absolute -bottom-3 -right-3 bg-blue-100 hover:bg-blue-200 text-blue-700 p-2 rounded-full shadow-md transition"
                    title="Повторить озвучку"
                  >
                    🔊
                  </button>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t bg-white p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setInputMode('text')}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                inputMode === 'text' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              ⌨️ Текст
            </button>
            <button
              onClick={() => setInputMode('voice')}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                inputMode === 'voice' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              🎤 Голос
            </button>
          </div>

          {inputMode === 'text' ? (
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    submitAnswer();
                  }
                }}
                placeholder="Введите ваш ответ..."
                className="flex-1 p-3 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100"
                rows={3}
                disabled={loading}
              />
              <button
                onClick={submitAnswer}
                disabled={loading || !input.trim()}
                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 font-medium transition flex items-center justify-center min-w-[80px]"
              >
                {loading ? <span className="animate-spin">⏳</span> : '📤'}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={toggleRecording}
                  disabled={loading}
                  className={`px-6 py-3 rounded-lg font-medium transition flex items-center gap-2 ${
                    isRecording ? 'bg-red-600 text-white hover:bg-red-700 animate-pulse' : 'bg-purple-600 text-white hover:bg-purple-700'
                  }`}
                >
                  {isRecording ? '⏹️ Остановить' : '🎤 Начать запись'}
                </button>
                {isRecording && (
                  <span className="text-sm text-gray-600">Запись... {recordingTime}с</span>
                )}
              </div>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Нажмите 'Начать запись' и говорите. Текст появится здесь..."
                className="w-full p-3 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100"
                rows={4}
                disabled={loading}
              />
              <button
                onClick={submitAnswer}
                disabled={loading || !input.trim()}
                className="w-full px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 font-medium transition flex items-center justify-center gap-2"
              >
                {loading ? <span className="animate-spin">⏳</span> : '📤 Отправить ответ'}
              </button>
            </div>
          )}
        </div>
        
        {messages.some(m => m.role === 'system' && m.content.includes('Интервью успешно завершено')) && (
          <div className="max-w-4xl mx-auto mt-4 text-center pb-4">
            <a href="/" className="inline-block px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium shadow">
              🔄 Пройти интервью заново
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

