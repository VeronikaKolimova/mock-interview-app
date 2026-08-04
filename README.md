# Mock Interview Platform

Платформа для проведения симуляций технических и HR собеседований с использованием AI.

## 📋 Описание

Проект состоит из двух основных компонентов:
- **Backend** (FastAPI/Python) - API для проведения интервью, обработки резюме и генерации вопросов
- **Frontend** (Next.js/TypeScript) - Веб-интерфейс для взаимодействия с платформой

## 🚀 Быстрый старт

### Требования
- Docker и Docker Compose
- API ключи для LLM (Groq/OpenRouter)
- Supabase проект для базы данных

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd mock-interview-platform
```

### 2. Настройка переменных окружения

#### Backend (.env)
```bash
cp backend/.env.example backend/.env
# Отредактируйте backend/.env и добавьте ваши ключи
```

#### Frontend (.env.local)
```bash
cp frontend/.env.example frontend/.env.local
# Отредактируйте frontend/.env.local при необходимости
```

### 3. Запуск через Docker Compose

```bash
docker-compose up --build
```

Приложение будет доступно по адресам:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- Health check: http://localhost:8001/health

## 📁 Структура проекта

```
.
├── backend/           # FastAPI приложение
│   ├── app/          # Основной код приложения
│   ├── services/     # Сервисы (LLM, TTS, база данных)
│   ├── models/       # Pydantic модели
│   ├── Dockerfile    # Docker конфигурация
│   └── .env.example  # Шаблон переменных окружения
├── frontend/         # Next.js приложение
│   ├── app/          # Next.js App Router
│   ├── components/   # React компоненты
│   ├── lib/          # Утилиты и клиенты
│   ├── Dockerfile    # Docker конфигурация
│   └── .env.example  # Шаблон переменных окружения
├── docker-compose.yml
└── README.md
```

## 🔧 Разработка

### Запуск backend локально

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### Запуск frontend локально

```bash
cd frontend
npm install
npm run dev
```

## 🐳 Docker

### Сборка образов

```bash
docker-compose build
```

### Запуск в фоновом режиме

```bash
docker-compose up -d
```

### Просмотр логов

```bash
docker-compose logs -f
```

### Остановка

```bash
docker-compose down
```

## 📊 API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/interview/start` | Начать новое интервью |
| POST | `/api/interview/answer` | Отправить ответ на вопрос |
| POST | `/api/upload-resume` | Загрузить резюме |
| POST | `/api/upload-vacancy` | Загрузить описание вакансии |
| GET | `/api/history` | Получить историю интервью |
| GET | `/health` | Health check endpoint |

## 🔐 Переменные окружения

### Backend
- `GROQ_API_KEY` - API ключ Groq для LLM
- `OPENROUTER_API_KEY` - API ключ OpenRouter (альтернатива)
- `SUPABASE_URL` - URL вашего Supabase проекта
- `SUPABASE_KEY` - Anon ключ Supabase
- `PORT` - Порт сервера (по умолчанию 8001)

### Frontend
- `NEXT_PUBLIC_API_URL` - URL backend API
- `NEXT_PUBLIC_SUPABASE_URL` - URL Supabase
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Anon ключ Supabase

## 🔄 CI/CD

Проект использует GitHub Actions для автоматического тестирования и деплоя. При пуше в ветку `main`:
1. Запускаются линтеры и тесты
2. Собираются Docker образы
3. Деплой на продакшен (при наличии конфигурации)

## 📝 Лицензия

MIT
