'use client';

// html2pdf импортируется динамически внутри функции (для совместимости с SSR)
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx';
import { saveAs } from 'file-saver';

import { useState, useRef, useEffect } from "react";
import { supabase } from '../lib/supabase';
import { User } from '@supabase/supabase-js';
import AuthForm from '../components/AuthForm';

import UploadSection from '@/components/UploadSection';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ==========================================
// СПИСОК КОМПАНИЙ С ЛОГОТИПАМИ
// ==========================================
const COMPANIES = [
  { id: "google",    name: "Google",              domain: "google.com",    emoji: "🔍" },
  { id: "meta",      name: "Meta (Facebook)",     domain: "meta.com",      emoji: "📘" },
  { id: "apple",     name: "Apple",               domain: "apple.com",     emoji: "🍎" },
  { id: "amazon",    name: "Amazon",              domain: "amazon.com",    emoji: "📦" },
  { id: "microsoft", name: "Microsoft",           domain: "microsoft.com", emoji: "🪟" },
  { id: "netflix",   name: "Netflix",             domain: "netflix.com",   emoji: "🎬" },
  { id: "nvidia",    name: "NVIDIA",              domain: "nvidia.com",    emoji: "🎮" },
  { id: "yandex",    name: "Яндекс",              domain: "yandex.ru",     emoji: "🟡" },
  { id: "vk",        name: "VK",                  domain: "vk.com",        emoji: "🔵" },
  { id: "sber",      name: "Сбер",                domain: "sberbank.ru",   emoji: "🟢" },
  { id: "tinkoff",   name: "Т-Банк",              domain: "tinkoff.ru",    emoji: "🟨" },
  { id: "ozon",      name: "Ozon",                domain: "ozon.ru",       emoji: "📦" },
  { id: "avito",     name: "Авито",               domain: "avito.ru",      emoji: "🔵" },
  { id: "wildberries", name: "Wildberries",       domain: "wildberries.ru",emoji: "🟣" },
  { id: "kaspersky", name: "Лаборатория Касперского", domain: "kaspersky.ru", emoji: "🛡️" },
  { id: "kotlin",    name: "JetBrains",           domain: "jetbrains.com", emoji: "⚡" },
];

// ==========================================
// КАСТОМНЫЙ КОМПОНЕНТ: DROPDOWN С КОМПАНИЯМИ
// ==========================================
interface CompanyDropdownProps {
  value: string;
  onChange: (companyId: string) => void;
}

function CompanyDropdown({ value, onChange }: CompanyDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const selected = COMPANIES.find((c) => c.id === value);

  // Закрытие по клику вне
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Автофокус на поиск при открытии
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Фильтрация компаний
  const filtered = COMPANIES.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="relative" ref={dropdownRef}>
      {/* 🔽 Кнопка открытия */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full p-3 border-2 rounded-xl bg-white flex items-center justify-between transition-all duration-200 ${
          isOpen
            ? "border-blue-500 ring-2 ring-blue-100"
            : "border-gray-200 hover:border-blue-400"
        }`}
      >
        {selected ? (
          <div className="flex items-center gap-3">
            <img
              src={`https://www.google.com/s2/favicons?domain=${selected.domain}&sz=64`}
              alt={selected.name}
              className="w-8 h-8 rounded-md object-contain bg-gray-50 p-0.5"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
            <div className="text-left">
              <div className="font-semibold text-gray-800">{selected.name}</div>
              <div className="text-xs text-gray-500">Собеседование в стиле этой компании</div>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center text-lg">
              🏢
            </div>
            <div className="text-left">
              <div className="font-medium text-gray-700">Выберите компанию</div>
              <div className="text-xs text-gray-500">Интервьюер адаптируется под её стиль</div>
            </div>
          </div>
        )}

        {/* Стрелочка */}
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* 📋 Выпадающий список */}
      {isOpen && (
        <div className="absolute z-50 mt-2 w-full bg-white border border-gray-200 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          {/* 🔍 Поиск */}
          <div className="p-3 border-b border-gray-100 bg-gray-50">
            <div className="relative">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <input
                ref={searchInputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск компании..."
                className="w-full pl-10 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
              />
            </div>
          </div>

          {/* 📄 Список компаний */}
          <div className="max-h-72 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="p-6 text-center text-gray-500 text-sm">
                😕 Компания не найдена
              </div>
            ) : (
              filtered.map((company) => (
                <button
                  key={company.id}
                  type="button"
                  onClick={() => {
                    onChange(company.id);
                    setIsOpen(false);
                    setSearch("");
                  }}
                  className={`w-full p-3 flex items-center gap-3 hover:bg-blue-50 transition-colors text-left ${
                    value === company.id ? "bg-blue-50 border-l-4 border-blue-500" : "border-l-4 border-transparent"
                  }`}
                >
                  <img
                    src={`https://www.google.com/s2/favicons?domain=${company.domain}&sz=64`}
                    alt={company.name}
                    className="w-8 h-8 rounded-md object-contain bg-gray-50 p-0.5"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.style.display = 'none';
                    }}
                  />
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">{company.name}</div>
                    <div className="text-xs text-gray-500">{company.domain}</div>
                  </div>
                  {value === company.id && (
                    <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>

          {/* ✨ Другая компания */}
          <div className="p-2 border-t border-gray-100 bg-gray-50">
            <button
              type="button"
              onClick={() => {
                onChange("custom");
                setIsOpen(false);
                setSearch("");
              }}
              className="w-full p-2 flex items-center gap-2 hover:bg-white rounded-lg transition-colors text-sm text-gray-600"
            >
              <span className="text-lg">✏️</span>
              <span>Другая компания (свободный режим)</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// ТИПЫ
// ==========================================
type Message = {
  role: "user" | "assistant";
  content: string;
  audioUrl?: string;
};

type HistoryItem = {
  interview_id: string;
  interviewer_type: string;
  company_name: string | null;
  status: string;
  final_feedback: string;
  created_at: string;
  adapted_resume: string;
  vacancy_text: string;
};

// ==========================================
// ОСНОВНОЙ КОМПОНЕНТ
// ==========================================
export default function InterviewPage() {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [userToken, setUserToken] = useState("");
  const [view, setView] = useState<"interview" | "history">("interview");
  
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
  const [selectedCompany, setSelectedCompany] = useState<string>(""); // 👈 НОВОЕ
  const [isFinished, setIsFinished] = useState(false);
  const [showAdaptedResume, setShowAdaptedResume] = useState(false);
  const [adaptedResumeContent, setAdaptedResumeContent] = useState("");
  
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [expandedResumeId, setExpandedResumeId] = useState<string | null>(null);
  const [expandedChatId, setExpandedChatId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<Message[]>([]);
  const [loadingChat, setLoadingChat] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const vacancyFileRef = useRef<HTMLInputElement>(null);
  const resumeFileRef = useRef<HTMLInputElement>(null);

  // 🔥 1. Проверка аутентификации Supabase
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      if (session?.user) setUserToken(session.user.id);
      setAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (session?.user) setUserToken(session.user.id);
      setAuthLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, showAdaptedResume]);

  useEffect(() => {
    if (view === "history" && userToken) fetchHistory();
  }, [view, userToken]);

  const fetchInterviewMessages = async (interviewId: string) => {
    if (expandedChatId === interviewId) {
      setExpandedChatId(null);
      return;
    }
    setLoadingChat(true);
    try {
      const response = await fetch(`${API_URL}/api/history/${interviewId}/messages`);
      if (!response.ok) throw new Error("Ошибка загрузки");
      const data = await response.json();
      setChatMessages(data.messages || []);
      setExpandedChatId(interviewId);
    } catch (error) {
      console.error("Ошибка получения сообщений:", error);
      alert("Не удалось загрузить историю диалога");
    } finally {
      setLoadingChat(false);
    }
  };

  const deleteInterview = async (interviewId: string) => {
    if (!confirm('Вы уверены, что хотите удалить это интервью? Это действие нельзя отменить.')) return;
    try {
      const response = await fetch(`${API_URL}/api/history/${interviewId}?user_token=${userToken}`, { method: 'DELETE' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Ошибка удаления');
      }
      fetchHistory();
    } catch (error) {
      console.error('Ошибка удаления:', error);
      alert('Не удалось удалить интервью');
    }
  };

  const fetchHistory = async () => {
    if (!userToken) return;
    setLoadingHistory(true);
    try {
      const response = await fetch(`${API_URL}/api/history?user_token=${userToken}`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Ошибка загрузки истории: ${response.status}`);
      }
      const data = await response.json();
      setHistory(data.interviews || []);
    } catch (error) {
      console.error("Ошибка получения истории:", error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: "vacancy" | "resume") => {
    const file = e.target.files?.[0];
    if (!file || !userToken) return;

    const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExtensions.includes(fileExtension)) {
      alert(`Неподдерживаемый формат. Используйте: ${allowedExtensions.join(', ')}`);
      return;
    }

    setIsLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    const endpoint = type === "vacancy" ? "/api/upload-vacancy" : `/api/upload-resume?user_token=${userToken}`;

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
    if (!userToken) return;
    
    // 👇 ВАЛИДАЦИЯ КОМПАНИИ
    if (!selectedCompany) {
      alert("⚠️ Пожалуйста, выберите компанию для собеседования!");
      return;
    }
    
    setIsLoading(true);
    setIsFinished(false);
    try {
      const response = await fetch(`${API_URL}/api/interview/start?user_token=${userToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interviewer: interviewerType,
          company: selectedCompany, // 👈 ПЕРЕДАЁМ КОМПАНИЮ
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
    if (!input.trim() || !sessionId || isFinished || !userToken) return;
    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/interview/answer?user_token=${userToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, answer: userMessage, tts_enabled: true }),
      });
      if (!response.ok) throw new Error("Ошибка отправки");
      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.message.content, audioUrl: data.audio_url }]);
      if (data.is_finished) setIsFinished(true);
      if (data.audio_url) playAudio(data.audio_url);
    } catch (error) {
      alert("Ошибка связи с сервером.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdaptResume = async () => {
    if (!sessionId || !userToken) return;
    if (!resumeText || resumeText.length < 20) {
      alert("⚠️ Сначала загрузите файл резюме или вставьте его текст на стартовом экране!");
      return;
    }

    setIsAdapting(true);
    try {
      const response = await fetch(`${API_URL}/api/adapt-resume?user_token=${userToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, resume_text: resumeText }),
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

  const downloadPDF = async (content: string, filename: string) => {
    const html2pdf = (await import('html2pdf.js')).default;
    const element = document.createElement('div');
    element.style.fontFamily = 'Arial, "Helvetica Neue", Helvetica, sans-serif';
    element.style.padding = '50px';
    element.style.color = '#1f2937';
    element.style.lineHeight = '1.8';
    element.style.maxWidth = '800px';
    element.style.margin = '0 auto';
    element.style.backgroundColor = 'white';
    
    element.innerHTML = `
      <div style="text-align: center; margin-bottom: 40px; border-bottom: 3px solid #2563eb; padding-bottom: 20px;">
        <h1 style="color: #2563eb; font-size: 28px; margin: 0; font-weight: 700; font-family: Arial, sans-serif;">Адаптированное резюме</h1>
        <p style="color: #6b7280; font-size: 14px; margin-top: 8px; font-family: Arial, sans-serif;">Подготовлено с помощью AI для вакансии ML-инженера</p>
      </div>
      <div style="white-space: pre-wrap; font-size: 13px; color: #374151; font-family: Arial, sans-serif;">${content.replace(/\n/g, '<br>')}</div>
      <div style="margin-top: 50px; padding-top: 20px; border-top: 2px solid #e5e7eb; text-align: center;">
        <p style="font-size: 11px; color: #9ca3af; margin: 0; font-family: Arial, sans-serif;">Сгенерировано с помощью Mock Interview SaaS • ${new Date().toLocaleDateString('ru-RU')}</p>
      </div>
    `;
    
    const opt = {
      margin: 10,
      filename: filename,
      image: { type: 'jpeg' as const, quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, letterRendering: true, logging: false },
      jsPDF: { unit: 'mm' as const, format: 'a4' as const, orientation: 'portrait' as const, compress: true }
    } as const;
    
    html2pdf().set(opt as any).from(element).save();
  };

  const downloadWord = async (content: string, filename: string) => {
    const lines = content.split('\n').filter(line => line.trim());
    const sections: Paragraph[] = [];
    
    const sectionKeywords = ['опыт работы', 'образование', 'навыки', 'о себе', 'желаемая', 'контакты', 'дополнительная', 'специализация', 'ключевые навыки', 'языки'];
    
    for (const line of lines) {
      const trimmed = line.trim();
      const lowerLine = trimmed.toLowerCase();
      const isSection = sectionKeywords.some(keyword => lowerLine.includes(keyword) && trimmed.length < 80 && !trimmed.includes(':'));
      
      if (isSection) {
        sections.push(new Paragraph({
          text: trimmed, heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 100 },
          border: { bottom: { color: "2563eb", space: 4, style: "single", size: 6 } }
        }));
      } else if (trimmed.startsWith('•') || trimmed.startsWith('-') || trimmed.startsWith('*')) {
        sections.push(new Paragraph({
          children: [new TextRun({ text: trimmed.substring(1).trim(), size: 22, font: "Arial" })],
          bullet: { level: 0 }, spacing: { after: 80 }
        }));
      } else if (trimmed.startsWith('#') || trimmed.length < 50 && trimmed === trimmed.toUpperCase()) {
        sections.push(new Paragraph({
          text: trimmed.replace(/^#+\s*/, ''), heading: HeadingLevel.HEADING_1, alignment: "center", spacing: { after: 200 }
        }));
      } else {
        sections.push(new Paragraph({
          children: [new TextRun({ text: trimmed, size: 22, font: "Arial" })], spacing: { after: 120 }
        }));
      }
    }
    
    const doc = new Document({
      sections: [{
        properties: {},
        children: [
          new Paragraph({ text: "Адаптированное резюме", heading: HeadingLevel.TITLE, alignment: "center", spacing: { after: 100 } }),
          new Paragraph({
            children: [new TextRun({ text: "Подготовлено с помощью AI для вакансии ML-инженера", size: 20, color: "6b7280", font: "Arial", italics: true })],
            alignment: "center", spacing: { after: 400 }
          }),
          ...sections,
          new Paragraph({
            children: [new TextRun({ text: `\nСгенерировано с помощью Mock Interview SaaS • ${new Date().toLocaleDateString('ru-RU')}`, size: 18, color: "9ca3af", font: "Arial", italics: true })],
            alignment: "center", spacing: { before: 400 },
            border: { top: { color: "e5e7eb", space: 4, style: "single", size: 6 } }
          })
        ]
      }]
    });
    
    const blob = await Packer.toBlob(doc);
    saveAs(blob, filename);
  };

  const convertToPDF = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch(`${API_URL}/api/convert-to-pdf`, { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Ошибка конвертации');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'resume.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Ошибка конвертации:', error);
      alert('Не удалось конвертировать файл');
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
    setSelectedCompany("");
    setView("interview");
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!user) return <AuthForm />;

  if (view === "history") {
    return (
      <div className="min-h-screen bg-gray-100 flex flex-col">
        <header className="bg-white shadow-sm p-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-gray-800">📜 История собеседований</h1>
          <button onClick={() => setView("interview")} className="text-sm text-blue-600 hover:text-blue-800 font-medium">← Начать новое интервью</button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 max-w-4xl mx-auto w-full">
          {loadingHistory ? (
            <div className="text-center py-10 text-gray-500">Загрузка истории...</div>
          ) : history.length === 0 ? (
            <div className="text-center py-10 text-gray-500 bg-white rounded-2xl shadow-sm">У вас пока нет пройденных собеседований.</div>
          ) : (
            <div className="space-y-4">
              {history.map((item, idx) => (
                <div key={item.interview_id || idx} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-bold text-lg text-gray-800">
                        {item.interviewer_type === "hr" ? "👩 HR-менеджер" : "👨‍💻 Техлид"}
                      </h3>
                      {/* 👇 НОВЫЙ БЕЙДЖ КОМПАНИИ */}
                      {item.company_name && (
                        <span className="inline-block mt-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                          🏢 {item.company_name}
                        </span>
                      )}
                      <p className="text-sm text-gray-500">{new Date(item.created_at).toLocaleString("ru-RU")}</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${item.status === "finished" ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}`}>
                      {item.status === "finished" ? "Завершено" : "В процессе"}
                    </span>
                  </div>
                  
                  {item.final_feedback && (
                    <div className="mb-4 p-3 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap max-h-40 overflow-y-auto">
                      <strong>Итоговый фидбек:</strong><br/>{item.final_feedback}
                    </div>
                  )}

                  <button 
                    onClick={() => fetchInterviewMessages(item.interview_id)}
                    disabled={loadingChat && expandedChatId === item.interview_id}
                    className="w-full mt-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium text-sm flex items-center justify-center gap-2"
                  >
                    {loadingChat && expandedChatId === item.interview_id ? '⏳ Загрузка...' : '💬 Показать полный диалог'}
                  </button>

                  {expandedChatId === item.interview_id && (
                    <div className="mt-3 border border-gray-200 rounded-lg p-4 bg-gray-50 max-h-96 overflow-y-auto space-y-3">
                      {chatMessages.length === 0 ? (
                        <p className="text-center text-gray-500 text-sm py-4">Сообщения не найдены</p>
                      ) : (
                        chatMessages.map((msg, idx) => (
                          <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div className={`max-w-[85%] p-3 rounded-xl text-sm whitespace-pre-wrap leading-relaxed ${msg.role === "user" ? "bg-blue-600 text-white rounded-br-none" : "bg-white text-gray-800 border border-gray-200 rounded-bl-none"}`}>
                              {msg.content}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  <div className="mt-3 flex justify-end">
                    <button onClick={() => deleteInterview(item.interview_id)} className="text-red-600 hover:text-red-800 text-xs font-medium flex items-center gap-1">
                      🗑️ Удалить
                    </button>
                  </div>

                  {item.adapted_resume && (
                    <div className="mt-3">
                      {expandedResumeId === item.interview_id ? (
                        <div className="border border-green-200 rounded-lg p-4 bg-green-50">
                          <div className="flex justify-between items-center mb-3">
                            <h4 className="font-bold text-green-800">✅ Адаптированное резюме</h4>
                            <button onClick={() => setExpandedResumeId(null)} className="text-gray-500 hover:text-gray-700 text-sm">✕ Свернуть</button>
                          </div>
                          <div className="whitespace-pre-wrap text-sm text-gray-800 bg-white p-3 rounded border border-gray-200 max-h-96 overflow-y-auto font-mono leading-relaxed">
                            {item.adapted_resume}
                          </div>
                          <div className="mt-3 flex flex-col sm:flex-row justify-center items-center gap-3">
                            <button onClick={() => downloadWord(item.adapted_resume, 'adapted_resume.docx')} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition shadow-md">📝 Скачать Word</button>
                            <label className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition shadow-md cursor-pointer">
                              📄 Конвертировать в PDF
                              <input type="file" accept=".docx" onChange={(e) => { const file = e.target.files?.[0]; if (file) convertToPDF(file); e.target.value = ''; }} className="hidden" />
                            </label>
                            <button onClick={() => downloadPDF(item.adapted_resume, 'adapted_resume.pdf')} className="text-gray-600 hover:text-gray-800 text-sm font-medium underline">📄 PDF</button>
                            <button onClick={() => navigator.clipboard.writeText(item.adapted_resume)} className="text-gray-600 hover:text-gray-800 text-sm font-medium underline">📋 Скопировать</button>
                          </div>
                        </div>
                      ) : (
                        <button onClick={() => setExpandedResumeId(item.interview_id)} className="w-full py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition font-medium text-sm flex items-center justify-center gap-2">
                          📄 Показать адаптированное резюме
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    );
  }

  // ==========================================
  // ЭКРАН ИНТЕРВЬЮ
  // ==========================================
  if (!sessionId) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-2xl max-w-4xl w-full">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800">🎙️ Mock Interview SaaS</h1>
            <button onClick={() => setView("history")} className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">📜 Моя история</button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">1. Ваше резюме</label>
              <p className="text-[11px] text-gray-500 mb-2 flex items-center gap-1">
                <span>🔒</span> Личные данные удаляются автоматически. Мы их не храним.
              </p>
              <p className="text-[10px] text-amber-600 mb-2 flex items-start gap-1">
                <span>⚠️</span> <span>Без резюме кнопка "Адаптировать" будет недоступна после интервью.</span>
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
              <p className="text-[10px] text-blue-600 mb-2 flex items-start gap-1">
                <span>ℹ️</span> <span>Без вакансии вопросы будут общими, не привязанными к позиции.</span>
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

          {/* 👇👇👇 НОВЫЙ БЛОК: ВЫБОР КОМПАНИИ 👇👇👇 */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-1">
              3. Компания для собеседования
            </label>
            <p className="text-[11px] text-gray-500 mb-2 flex items-start gap-1">
              <span>🎯</span> 
              <span>AI-интервьюер будет задавать вопросы в стиле выбранной компании: её культура, процессы и стандарты оценки</span>
            </p>
            <CompanyDropdown
              value={selectedCompany}
              onChange={setSelectedCompany}
            />
          </div>
          {/* 👆👆👆 КОНЕЦ НОВОГО БЛОКА 👆👆👆 */}

          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">4. Тип интервьюера:</label>
            <div className="flex gap-4">
              {(["hr", "techlead"] as const).map((type) => (
                <button key={type} onClick={() => setInterviewerType(type)} className={`flex-1 py-3 rounded-lg border-2 font-semibold transition ${interviewerType === type ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600'}`}>
                  {type === "hr" ? "👩 HR-менеджер" : "👨‍💻 Техлид"}
                </button>
              ))}
            </div>
          </div>

          <button onClick={startInterview} disabled={isLoading || !selectedCompany} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl transition disabled:opacity-50 disabled:cursor-not-allowed">
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
        <button onClick={resetAll} className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">🔄 Начать заново</button>
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
        
        {isFinished && !showAdaptedResume && (
          <div className="my-6">
            {resumeText ? (
              <div className="flex justify-center animate-pulse">
                <button onClick={handleAdaptResume} disabled={isAdapting} className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-8 rounded-xl shadow-lg transition flex items-center gap-2">
                  {isAdapting ? "⏳ Адаптируем с помощью AI..." : "✨ Адаптировать моё резюме под эту вакансию"}
                </button>
              </div>
            ) : (
              <div className="max-w-2xl mx-auto p-4 bg-amber-50 border border-amber-200 rounded-xl text-center">
                <p className="text-amber-800 font-medium text-sm">⚠️ Кнопка адаптации недоступна</p>
                <p className="text-amber-700 text-xs mt-1">Вы не загрузили резюме на стартовом экране.</p>
              </div>
            )}
            {!resumeText && !vacancyText && (
              <p className="text-center text-gray-500 text-xs mt-3">Совет: загрузите и резюме, и вакансию для максимального эффекта адаптации.</p>
            )}
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
            <div className="mt-4 flex flex-col sm:flex-row justify-center items-center gap-3">
              <button onClick={() => downloadWord(adaptedResumeContent, 'adapted_resume.docx')} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition shadow-md">📝 Скачать Word</button>
              <label className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition shadow-md cursor-pointer">
                📄 Конвертировать Word → PDF
                <input type="file" accept=".docx" onChange={(e) => { const file = e.target.files?.[0]; if (file) convertToPDF(file); e.target.value = ''; }} className="hidden" />
              </label>
              <button onClick={() => downloadPDF(adaptedResumeContent, 'adapted_resume.pdf')} className="text-gray-600 hover:text-gray-800 text-sm font-medium flex items-center gap-1 underline">📄 или PDF</button>
              <button onClick={() => navigator.clipboard.writeText(adaptedResumeContent)} className="text-gray-600 hover:text-gray-800 text-sm font-medium flex items-center gap-1 underline">📋 Скопировать</button>
            </div>
          </div>
        )}

        {isLoading && !isAdapting && (
          <div className="flex justify-start"><div className="bg-white p-4 rounded-2xl rounded-bl-none border border-gray-200 shadow-sm flex gap-1"><span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span><span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></span><span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></span></div></div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="bg-white border-t p-4">
        {isFinished ? (
          <div className="max-w-4xl mx-auto flex justify-center">
            <button onClick={resetAll} className="bg-red-600 hover:bg-red-700 text-white px-8 py-3 rounded-xl font-semibold transition flex items-center gap-2 shadow-md">
              🏁 Завершить и начать новое интервью
            </button>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto flex gap-3">
            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !isLoading && sendMessage()} placeholder="Введите ваш ответ..." disabled={isLoading} className="flex-1 p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100" />
            <button onClick={sendMessage} disabled={isLoading || !input.trim()} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-semibold transition disabled:opacity-50">Отправить</button>
          </div>
        )}
      </footer>
    </div>
  );
}
