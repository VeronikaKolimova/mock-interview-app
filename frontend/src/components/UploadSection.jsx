'use client';

import { useState } from 'react';
import { Upload, FileText, Briefcase, Building2, CheckCircle, AlertCircle } from 'lucide-react';

// Список популярных компаний для подсказок
const POPULAR_COMPANIES = [
  "Ozon",
  "Яндекс",
  "Авито",
  "Сбер",
  "Тинькофф",
  "VK",
  "Wildberries",
  "МТС",
  "Лаборатория Касперского",
  "Газпром Нефть",
  "Другая компания"
];

export default function UploadSection({ onStartInterview }) {
  const [resumeFile, setResumeFile] = useState(null);
  const [vacancyFile, setVacancyFile] = useState(null);
  const [companyName, setCompanyName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  
  // Состояния для визуализации загрузки
  const [resumeUploading, setResumeUploading] = useState(false);
  const [vacancyUploading, setVacancyUploading] = useState(false);

  const handleFileChange = async (e, type) => {
    const file = e.target.files[0];
    if (!file) return;

    // Проверка типа файла
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!validTypes.includes(file.type)) {
      setError("Пожалуйста, загрузите файл в формате PDF или DOCX");
      return;
    }

    setError("");
    
    if (type === 'resume') {
      setResumeFile(file);
      setResumeUploading(true);
    } else {
      setVacancyFile(file);
      setVacancyUploading(true);
    }

    // Здесь можно добавить логику предзагрузки файла на сервер, если нужно
    // Но пока мы просто сохраняем файл в стейт и отправим всё вместе при старте
    if (type === 'resume') setResumeUploading(false);
    else setVacancyUploading(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!resumeFile || !vacancyFile) {
      setError("Пожалуйста, загрузите и резюме, и описание вакансии");
      return;
    }

    if (!companyName.trim()) {
      setError("Пожалуйста, укажите название компании");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append('resume', resumeFile);
      formData.append('vacancy', vacancyFile);
      formData.append('company_name', companyName);

      // Вызываем функцию из родителя (страницы), которая сделает запрос к API
      await onStartInterview(formData);
      
      // Очистка после успешного старта (если нужно)
      // setResumeFile(null);
      // setVacancyFile(null);
      // setCompanyName("");
      
    } catch (err) {
      console.error("Ошибка при старте интервью:", err);
      setError(err.message || "Не удалось начать интервью. Проверьте подключение.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-white rounded-xl shadow-lg p-6 md:p-8 border border-gray-100">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Подготовка к собеседованию</h2>
        <p className="text-gray-500">Загрузите документы и укажите компанию, чтобы начать симуляцию</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        
        {/* Выбор компании */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            В какую компанию вы планируете собеседование?
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Building2 className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Например: Яндекс, Ozon, Сбер..."
              className="block w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition-colors"
              list="companies-list"
            />
            <datalist id="companies-list">
              {POPULAR_COMPANIES.map((company) => (
                <option key={company} value={company} />
              ))}
            </datalist>
          </div>
        </div>

        {/* Загрузка Резюме */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Ваше резюме (PDF или DOCX)
          </label>
          <div className={`mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed rounded-lg transition-colors ${resumeFile ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'}`}>
            <div className="space-y-1 text-center">
              {resumeFile ? (
                <div className="flex items-center justify-center space-x-2 text-green-600">
                  <CheckCircle className="h-6 w-6" />
                  <span className="font-medium">{resumeFile.name}</span>
                  <button 
                    type="button" 
                    onClick={() => setResumeFile(null)}
                    className="text-xs text-red-500 hover:text-red-700 underline ml-2"
                  >
                    Удалить
                  </button>
                </div>
              ) : (
                <>
                  <Upload className="mx-auto h-12 w-12 text-gray-400" />
                  <div className="flex text-sm text-gray-600 justify-center">
                    <label className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none">
                      <span>Загрузить файл</span>
                      <input 
                        type="file" 
                        className="sr-only" 
                        accept=".pdf,.docx" 
                        onChange={(e) => handleFileChange(e, 'resume')}
                        disabled={resumeUploading}
                      />
                    </label>
                    <p className="pl-1">или перетащите сюда</p>
                  </div>
                  <p className="text-xs text-gray-500">PDF или DOCX до 10MB</p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Загрузка Вакансии */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Описание вакансии (PDF или DOCX)
          </label>
          <div className={`mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed rounded-lg transition-colors ${vacancyFile ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'}`}>
            <div className="space-y-1 text-center">
              {vacancyFile ? (
                <div className="flex items-center justify-center space-x-2 text-green-600">
                  <CheckCircle className="h-6 w-6" />
                  <span className="font-medium">{vacancyFile.name}</span>
                  <button 
                    type="button" 
                    onClick={() => setVacancyFile(null)}
                    className="text-xs text-red-500 hover:text-red-700 underline ml-2"
                  >
                    Удалить
                  </button>
                </div>
              ) : (
                <>
                  <Briefcase className="mx-auto h-12 w-12 text-gray-400" />
                  <div className="flex text-sm text-gray-600 justify-center">
                    <label className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none">
                      <span>Загрузить файл</span>
                      <input 
                        type="file" 
                        className="sr-only" 
                        accept=".pdf,.docx" 
                        onChange={(e) => handleFileChange(e, 'vacancy')}
                        disabled={vacancyUploading}
                      />
                    </label>
                    <p className="pl-1">или перетащите сюда</p>
                  </div>
                  <p className="text-xs text-gray-500">PDF или DOCX до 10MB</p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Сообщения об ошибках */}
        {error && (
          <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg text-sm">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Кнопка старта */}
        <button
          type="submit"
          disabled={isLoading || !resumeFile || !vacancyFile || !companyName}
          className={`w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white 
            ${isLoading || !resumeFile || !vacancyFile || !companyName
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transform transition hover:-translate-y-0.5'
            }`}
        >
          {isLoading ? (
            <span className="flex items-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Обработка документов...
            </span>
          ) : (
            "Начать собеседование"
          )}
        </button>
      </form>
    </div>
  );
}
