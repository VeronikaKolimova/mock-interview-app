import os
import subprocess
import shutil
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from models.schemas import InterviewStart, AnswerSubmit, InterviewResponse, Message, SessionData
from services.llm import ask_llm
from services.tts import text_to_speech
from services.database import get_supabase_client
import uuid
from datetime import datetime
from pathlib import Path
import tempfile
import logging
import re
from services.file_parser import extract_text_from_file
from pydantic import BaseModel
from typing import Optional

# ==========================================
# ИНИЦИАЛИЗАЦИЯ
# ==========================================
supabase = get_supabase_client()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="Mock Interview API", version="1.2.0")


# ==========================================
# СЛОВАРЬ КОМПАНИЙ
# ==========================================
COMPANY_PROFILES = {
    "google": {
        "name": "Google",
        "style": "Google славится поведенческими интервью (STAR-метод), вопросами про масштабируемость, алгоритмами и культурой 'Googliness'. Интервьюеры ценят структурированное мышление и командную работу.",
        "focus": "алгоритмы, системный дизайн, поведенческие вопросы"
    },
    "meta": {
        "name": "Meta (Facebook)",
        "style": "Meta делает упор на скорость решения задач, работу с большими данными, A/B тестирование. Ценится инициативность и 'Move Fast' менталитет.",
        "focus": "скорость, данные, продуктовое мышление"
    },
    "apple": {
        "name": "Apple",
        "style": "Apple фокусируется на внимании к деталям, качестве продукта, deep technical знаниях. Вопросы часто про оптимизацию и работу в команде с дизайнерами.",
        "focus": "качество, детали, UX"
    },
    "amazon": {
        "name": "Amazon",
        "style": "Amazon проводит интервью по 16 Leadership Principles. Каждый вопрос привязан к принципу: Customer Obsession, Ownership, Dive Deep и т.д.",
        "focus": "Leadership Principles, бизнес-кейсы"
    },
    "microsoft": {
        "name": "Microsoft",
        "style": "Microsoft ценит growth mindset, умение работать в экосистеме продуктов, решение бизнес-задач. Технические вопросы + системный дизайн.",
        "focus": "growth mindset, экосистема"
    },
    "netflix": {
        "name": "Netflix",
        "style": "Netflix ищет 'fully formed adults', ценит свободу и ответственность. Вопросы на самостоятельность, принятие решений без микроменеджмента.",
        "focus": "самостоятельность, ответственность"
    },
    "nvidia": {
        "name": "NVIDIA",
        "style": "NVIDIA фокусируется на GPU, параллельных вычислениях, AI/ML. Глубокие технические вопросы по архитектуре и оптимизации.",
        "focus": "GPU, AI/ML, архитектура"
    },
    "yandex": {
        "name": "Яндекс",
        "style": "Яндекс проводит алгоритмические секции, системный дизайн, поведенческие интервью. Ценится умение работать с высоконагруженными системами.",
        "focus": "алгоритмы, highload"
    },
    "vk": {
        "name": "VK",
        "style": "VK делает упор на работу с соцграфами, рекомендательными системами, высоконагруженными сервисами. Алгоритмы + продуктовое мышление.",
        "focus": "соцграфы, рекомендации"
    },
    "sber": {
        "name": "Сбер",
        "style": "Сбер (SberTech) фокусируется на финтехе, ML для кредитного скоринга, NLP. Вопросы про безопасность данных и регуляторику.",
        "focus": "финтех, ML, NLP"
    },
    "tinkoff": {
        "name": "Т-Банк (Тинькофф)",
        "style": "Т-Банк ценит предпринимательский подход, скорость принятия решений, работу с данными. Алгоритмы + бизнес-кейсы.",
        "focus": "предпринимательство, данные"
    },
    "ozon": {
        "name": "Ozon",
        "style": "Ozon фокусируется на e-commerce, логистике, рекомендательных системах. Вопросы про масштабирование и работу с большими данными.",
        "focus": "e-commerce, логистика, big data"
    },
    "avito": {
        "name": "Авито",
        "style": "Авито — классифайды, поиск, модерация. Вопросы про ML для модерации контента, поиск, ранжирование.",
        "focus": "поиск, модерация, ML"
    },
    "wildberries": {
        "name": "Wildberries",
        "style": "Wildberries — e-commerce с фокусом на логистику, ценообразование, рекомендательные системы.",
        "focus": "логистика, ценообразование"
    },
    "kaspersky": {
        "name": "Лаборатория Касперского",
        "style": "Касперский — кибербезопасность. Вопросы про malware analysis, reverse engineering, сетевую безопасность.",
        "focus": "кибербезопасность"
    },
    "jetbrains": {
        "name": "JetBrains",
        "style": "JetBrains — разработка инструментов для программистов. Вопросы про языки программирования, компиляторы, IDE.",
        "focus": "языки, инструменты, IDE"
    },
    "custom": {
        "name": "выбранная компания",
        "style": "Стандартное профессиональное собеседование.",
        "focus": "общие вопросы"
    }
}


def get_company_info(company_id: Optional[str]) -> Optional[dict]:
    """Получить информацию о компании по ID"""
    if not company_id:
        return None
    return COMPANY_PROFILES.get(company_id, COMPANY_PROFILES["custom"])


def build_company_context(company_id: Optional[str]) -> str:
    """Построить контекст компании для промпта"""
    info = get_company_info(company_id)
    if not info:
        return ""
    return f"""
=== КОМПАНИЯ: {info['name']} ===
Стиль интервью: {info['style']}
Фокус компании: {info['focus']}
Веди себя как типичный интервьюер этой компании.
=========================
"""


# ==========================================
# ФУНКЦИИ ОЧИСТКИ
# ==========================================
def sanitize_pii(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', text, flags=re.IGNORECASE)
    text = re.sub(r'(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', '[ТЕЛЕФОН]', text)
    text = re.sub(r'(https?://t\.me/|@)[a-zA-Z0-9_]{5,32}', '[TELEGRAM]', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+', '[ССЫЛКА]', text)
    lines = text.split('\n')
    if lines:
        first_line = lines[0].strip()
        if re.match(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(\s+[А-ЯЁ][а-яё]+)?$', first_line):
            lines[0] = '[ИМЯ ФАМИЛИЯ]'
    text = '\n'.join(lines)
    text = re.sub(r'(Дата рождения|Возраст|Год рождения)[:\s]*.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(Женщина|Мужчина)\b', '', text)
    return text.strip()


def clean_llm_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = text.replace("<think>", "").replace("</think>", "")
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)
    text = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF]+', '', text)
    lines = text.split('\n')
    cleaned_lines = [re.sub(r' {2,}', ' ', line.strip()) for line in lines if line.strip() or True]
    text = '\n'.join(cleaned_lines)
    return re.sub(r'\n{4,}', '\n\n', text).strip()


# ==========================================
# НАСТРОЙКИ
# ==========================================
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
sessions: dict[str, SessionData] = {}
resumes: dict[str, str] = {}


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПОСТРОЕНИЯ ПРОМПТОВ
# ==========================================

def build_interview_context(vacancy_text: Optional[str], resume_text: Optional[str], company_id: Optional[str]) -> dict:
    """
    Строит контекст интервью на основе доступных данных.
    Возвращает словарь с готовыми блоками для промптов.
    """
    has_vacancy = bool(vacancy_text and vacancy_text.strip())
    has_resume = bool(resume_text and resume_text.strip())
    company_info = get_company_info(company_id)
    has_company = company_info is not None and company_id is not None
    
    # Формируем блоки контекста
    company_block = ""
    if has_company:
        company_block = f"""
=== КОМПАНИЯ: {company_info['name']} ===
Стиль интервью: {company_info['style']}
Фокус: {company_info['focus']}
Веди себя как типичный интервьюер этой компании.
"""
    
    vacancy_block = ""
    if has_vacancy:
        vacancy_block = f"""
=== ТЕКСТ ВАКАНСИИ ===
{vacancy_text[:1500]}
=== КОНЕЦ ВАКАНСИИ ===
"""
    
    resume_block = ""
    if has_resume:
        resume_block = f"""
=== РЕЗЮМЕ КАНДИДАТА ===
{resume_text[:1200]}
=== КОНЕЦ РЕЗЮМЕ ===
"""
    
    # Определяем инструкции для LLM в зависимости от наличия данных
    instructions = []
    
    if has_resume:
        instructions.append("✅ У тебя ЕСТЬ резюме кандидата — используй его для персонализированных вопросов о его опыте, навыках и проектах.")
    else:
        instructions.append("⚠️ У кандидата НЕТ резюме — не упоминай резюме, спрашивай об опыте в общем виде.")
    
    if has_vacancy:
        instructions.append("✅ У тебя ЕСТЬ вакансия — задавай вопросы, релевантные требованиям этой позиции.")
    else:
        instructions.append("⚠️ Вакансия НЕ указана — задавай общие профессиональные вопросы.")
    
    if has_company:
        instructions.append(f"✅ Ты интервьюер из {company_info['name']} — придерживайся стиля и ценностей этой компании.")
    
    # Определяем тип интервью (для логики вопросов)
    interview_mode = "general"
    if has_vacancy and has_resume:
        interview_mode = "full"
    elif has_vacancy:
        interview_mode = "vacancy_only"
    elif has_resume:
        interview_mode = "resume_only"
    elif has_company:
        interview_mode = "company_only"
    
    return {
        "has_vacancy": has_vacancy,
        "has_resume": has_resume,
        "has_company": has_company,
        "company_name": company_info["name"] if has_company else None,
        "company_block": company_block,
        "vacancy_block": vacancy_block,
        "resume_block": resume_block,
        "instructions": "\n".join(instructions),
        "interview_mode": interview_mode
    }


def build_greeting_prompt(ctx: dict, interviewer_role: str, interviewer_name: str) -> str:
    """Строит промпт для приветствия в зависимости от контекста"""
    company_mention = f" из компании {ctx['company_name']}" if ctx['has_company'] else ""
    
    base = f"""{ctx['company_block']}
Поздоровайся с кандидатом и представься как {interviewer_role} {interviewer_name}{company_mention}.
"""
    
    if ctx['interview_mode'] == "full":
        base += "Скажи, что ты изучила и вакансию, и резюме кандидата. Задай первый открытый вопрос о мотивации или опыте кандидата, связанный с вакансией и его биографией."
    elif ctx['interview_mode'] == "vacancy_only":
        base += f"Скажи, что ты изучила требования вакансии.{ctx['vacancy_block']}\nЗадай первый открытый вопрос о мотивации или опыте, релевантном этой позиции."
    elif ctx['interview_mode'] == "resume_only":
        base += f"Скажи, что ты ознакомилась с резюме кандидата.{ctx['resume_block']}\nЗадай первый вопрос о его опыте, основываясь на резюме."
    elif ctx['interview_mode'] == "company_only":
        base += "Задай первый открытый вопрос о кандидате в стиле твоей компании."
    else:
        base += "Задай первый открытый вопрос о кандидате, его опыте и карьерных целях."
    
    base += f"\n\nИНСТРУКЦИИ:\n{ctx['instructions']}"
    return base


def build_question_prompt(ctx: dict, dialog_text: str, last_answer: str) -> str:
    """Строит промпт для следующего вопроса"""
    prompt = f"""{ctx['company_block']}
История диалога:
{dialog_text}

{ctx['vacancy_block']}
{ctx['resume_block']}

Дай КРАТКУЮ реакцию (1-2 предложения) на последний ответ кандидата: '{last_answer}'

Затем задай ОДИН следующий вопрос кандидату.

ИНСТРУКЦИИ:
{ctx['instructions']}
"""
    return prompt


def build_final_prompt(ctx: dict, dialog_text: str) -> str:
    """Строит промпт для финального решения"""
    return f"""{ctx['company_block']}
Подведи итоги интервью. 

Полный диалог:
{dialog_text}

{ctx['vacancy_block']}
{ctx['resume_block']}

Дай решение и оценку из 10. Учитывай все доступные данные.

ИНСТРУКЦИИ:
{ctx['instructions']}
"""


# ==========================================
# ЭНДПОИНТЫ
# ==========================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.2.0"}


@app.post("/api/interview/start")
async def start_interview(data: InterviewStart, user_token: str = Query("")) -> InterviewResponse:
    session_id = str(uuid.uuid4())
    
    # Получаем резюме: сначала из запроса, затем из БД
    resume_text = data.resume_text
    if not resume_text and user_token:
        try:
            resume_data = supabase.table("resumes") \
                .select("resume_text") \
                .eq("user_token", user_token) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            if resume_data.data:
                resume_text = resume_data.data[0]["resume_text"]
                logger.info(f"📄 Резюме подтянуто из БД для пользователя {user_token}")
        except Exception as e:
            logger.warning(f"Не удалось получить резюме из БД: {e}")
    
    # Получаем информацию о компании
    company_info = get_company_info(data.company)
    company_name = company_info["name"] if company_info else None
    
    # Сохраняем интервью в БД
    try:
        supabase.table("interviews").insert({
            "id": session_id,
            "user_token": user_token,
            "interviewer_type": data.interviewer,
            "company_name": company_name,
            "status": "in_progress",
            "final_feedback": None
        }).execute()
    except Exception as e:
        logger.error(f"Ошибка создания интервью в БД: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания интервью: {str(e)}")
    
    # Создаём сессию со всеми доступными данными
    session = SessionData(
        session_id=session_id,
        interviewer=data.interviewer,
        vacancy_text=data.vacancy_text,
        resume_text=resume_text,
        company=data.company,
        created_at=datetime.now().isoformat(),
        question_idx=1,
        messages=[]
    )
    sessions[session_id] = session
    
    # Логируем режим интервью
    ctx = build_interview_context(data.vacancy_text, resume_text, data.company)
    logger.info(f"🎯 Режим интервью: {ctx['interview_mode']} | Вакансия: {ctx['has_vacancy']} | Резюме: {ctx['has_resume']} | Компания: {ctx['has_company']}")
    
    interviewer_name = "Анна" if data.interviewer == "hr" else "Дмитрий"
    interviewer_role = "HR-менеджер" if data.interviewer == "hr" else "технический лид"
    
    # Генерируем приветствие с учётом всех доступных данных
    greeting_prompt = build_greeting_prompt(ctx, interviewer_role, interviewer_name)
    
    greeting_messages = [
        {"role": "system", "content": f"Ты {interviewer_role} {interviewer_name}{f' из компании {company_name}' if ctx['has_company'] else ''}. Отвечай на русском языке."},
        {"role": "user", "content": greeting_prompt}
    ]
    
    greeting = ask_llm(greeting_messages, max_tokens=250)
    greeting = clean_llm_output(greeting)
    
    # Добавляем префикс имени
    company_suffix = f", {company_name}" if ctx['has_company'] else ""
    if data.interviewer == "hr":
        greeting = f"Анна (HR{company_suffix}): {greeting}"
    else:
        greeting = f"Дмитрий (Техлид{company_suffix}): {greeting}"
    
    session.messages.append(Message(role="assistant", content=greeting))
    
    # Сохраняем приветствие в БД
    try:
        supabase.table("messages").insert({
            "interview_id": session_id,
            "user_token": user_token,
            "role": "assistant",
            "content": greeting
        }).execute()
    except Exception as e:
        logger.error(f"Ошибка сохранения приветствия: {e}")
    
    # TTS
    audio_url = None
    if data.tts_enabled:
        try:
            audio_path = await text_to_speech(greeting, data.interviewer)
            if audio_path:
                audio_url = f"/audio/{Path(audio_path).name}"
        except Exception as e:
            logger.error(f"Ошибка TTS: {e}")
    
    return InterviewResponse(
        session_id=session_id,
        message=Message(role="assistant", content=greeting),
        audio_url=audio_url
    )


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...), user_token: str = Query("")):
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой. Макс: 10 MB")
        
        raw_text = extract_text_from_file(file_bytes, file.filename)
        if not raw_text or len(raw_text) < 50:
            raise HTTPException(status_code=400, detail="Не удалось извлечь текст.")
        
        clean_text = sanitize_pii(raw_text)
        resume_id = str(uuid.uuid4())
        resumes[resume_id] = clean_text
        
        try:
            supabase.table("resumes").insert({
                "id": resume_id,
                "user_token": user_token,
                "resume_text": clean_text,
                "filename": file.filename
            }).execute()
        except Exception as e:
            logger.error(f"Ошибка сохранения резюме в БД: {e}")
        
        return {"resume_id": resume_id, "filename": file.filename, "text": clean_text, "length": len(clean_text)}
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-vacancy")
async def upload_vacancy(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой.")
        
        vacancy_text = extract_text_from_file(file_bytes, file.filename)
        if not vacancy_text or len(vacancy_text) < 50:
            raise HTTPException(status_code=400, detail="Не удалось извлечь текст.")
        
        return {"filename": file.filename, "text": vacancy_text, "length": len(vacancy_text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/answer")
async def submit_answer(data: AnswerSubmit, user_token: str = Query("")) -> InterviewResponse:
    if data.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    session = sessions[data.session_id]
    session.messages.append(Message(role="user", content=data.answer))
    
    # Сохраняем сообщение в БД
    try:
        supabase.table("messages").insert({
            "interview_id": data.session_id,
            "user_token": user_token,
            "role": "user",
            "content": data.answer
        }).execute()
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщения: {e}")
    
    # Строим контекст из данных сессии
    ctx = build_interview_context(session.vacancy_text, session.resume_text, session.company)
    
    interviewer_name = "Анна" if session.interviewer == "hr" else "Дмитрий"
    interviewer_role = "HR-менеджер" if session.interviewer == "hr" else "технический лид"
    system_content = f"Ты {interviewer_role} {interviewer_name}{f' из компании {ctx['company_name']}' if ctx['has_company'] else ''}."
    
    min_questions = 3
    is_last_question = (session.question_idx >= min_questions)
    dialog_text = "\n\n".join([
        f"{'Интервьюер' if m.role == 'assistant' else 'Кандидат'}: {m.content}" 
        for m in session.messages
    ])
    
    if is_last_question:
        # Финальный этап: реакция + итоги
        
        # 1. Реакция на последний ответ (без новых вопросов)
        last_answer = data.answer
        reaction_prompt = f"""{ctx['company_block']}
Дай КРАТКУЮ реакцию (2-3 предложения) на последний ответ кандидата: '{last_answer}'.
{ctx['vacancy_block']}
{ctx['resume_block']}
❗️ СТРОГО ЗАПРЕЩЕНО задавать новые вопросы, это финальный ответ перед завершением интервью.

ИНСТРУКЦИИ:
{ctx['instructions']}"""
        
        reaction_messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": reaction_prompt}
        ]
        reaction = ask_llm(reaction_messages, max_tokens=200)
        reaction = clean_llm_output(reaction)
        
        try:
            supabase.table("messages").insert({
                "interview_id": data.session_id,
                "user_token": user_token,
                "role": "assistant",
                "content": reaction
            }).execute()
        except Exception as e:
            logger.error(f"Ошибка сохранения реакции: {e}")
        
        # 2. Итоговое решение
        final_prompt = build_final_prompt(ctx, dialog_text)
        final_messages = [
            {"role": "system", "content": "Ты эксперт по найму. Отвечай на русском. Включи в ответ '🎯 РЕШЕНИЕ:'"},
            {"role": "user", "content": final_prompt}
        ]
        raw_response = ask_llm(final_messages, max_tokens=800)
        clean_response = clean_llm_output(raw_response)
        
        combined_response = f"{reaction}\n\n{clean_response}"
        session.messages.append(Message(role="assistant", content=combined_response))
        
        try:
            supabase.table("interviews").update({
                "status": "finished",
                "final_feedback": clean_response
            }).eq("id", data.session_id).execute()
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
        
        return InterviewResponse(
            session_id=data.session_id,
            message=Message(role="assistant", content=combined_response),
            is_finished=True,
            final_feedback=clean_response
        )
    else:
        # Обычный этап: реакция + следующий вопрос
        question_prompt = build_question_prompt(ctx, dialog_text, data.answer)
        
        question_messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question_prompt}
        ]
        combined = ask_llm(question_messages, max_tokens=400)
        combined = clean_llm_output(combined)
        
        try:
            supabase.table("messages").insert({
                "interview_id": data.session_id,
                "user_token": user_token,
                "role": "assistant",
                "content": combined
            }).execute()
        except Exception as e:
            logger.error(f"Ошибка сохранения ответа: {e}")
        
        session.messages.append(Message(role="assistant", content=combined))
        session.question_idx += 1
        
        return InterviewResponse(
            session_id=data.session_id,
            message=Message(role="assistant", content=combined),
            is_finished=False
        )


@app.post("/api/adapt-resume")
async def adapt_resume(data: ResumeAdaptRequest, user_token: str = Query("")):
    if data.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    session = sessions[data.session_id]
    resume_text = data.resume_text or session.resume_text or (list(resumes.values())[-1] if resumes else "")
    
    if not resume_text:
        raise HTTPException(status_code=400, detail="Текст резюме не найден.")
    
    vacancy_text = session.vacancy_text or ""
    dialog_text = "\n".join([f"{m.role}: {m.content}" for m in session.messages])
    
    clean_resume = re.sub(r'\|.*?\|', '\n', resume_text)
    clean_resume = re.sub(r'\n{3,}', '\n\n', clean_resume).strip()
    
    adapt_prompt = f"""Адаптируй резюме под вакансию ML-инженера.

СТРОГИЕ ПРАВИЛА (нарушение недопустимо):
Используй ТОЛЬКО факты из исходного резюме. Не выдумывай данные (пиши [ИМЯ ФАМИЛИЯ], [ТЕЛЕФОН]).
❗️ СОХРАНЯЙ ВСЕ ДАТЫ (месяц и год) для КАЖДОГО места работы и учебы.
❗️ КАЖДЫЙ РАЗДЕЛ ДОЛЖЕН БЫТЬ ТОЛЬКО ОДИН РАЗ.
❗️ ЗАПРЕЩЕНО добавлять примечания в конце текста.

Структура:
Контакты
Желаемая должность
Опыт работы (строго с датами!)
Образование (строго с датами!)
Навыки
Дополнительная информация

Резюме:
{clean_resume}

Вакансия:
{vacancy_text}

Интервью:
{dialog_text}"""
    
    messages = [
        {"role": "system", "content": "Ты профессиональный карьерный консультант. Никогда не выдумывай факты."},
        {"role": "user", "content": adapt_prompt}
    ]
    
    clean_response = "Ошибка AI."
    try:
        raw_response = ask_llm(messages, max_tokens=2000)
        clean_response = clean_llm_output(raw_response)
    except Exception as e:
        logger.error(f"Ошибка LLM: {e}")
    
    try:
        supabase.table("adapted_resumes").delete().eq("interview_id", data.session_id).execute()
        supabase.table("adapted_resumes").insert({
            "interview_id": data.session_id,
            "user_token": user_token,
            "adapted_text": clean_response,
            "vacancy_text": vacancy_text
        }).execute()
        logger.info(f"✅ Адаптированное резюме сохранено для интервью {data.session_id}")
    except Exception as e:
        logger.error(f"Ошибка сохранения адаптации: {e}")
    
    return {
        "original_resume_preview": clean_resume[:200] + "...",
        "adapted_resume": clean_response,
        "session_id": data.session_id
    }


@app.get("/api/history")
async def get_history(user_token: str = Query("")):
    if not user_token:
        raise HTTPException(status_code=400, detail="user_token не предоставлен")
    try:
        response = supabase.rpc('get_user_history', {'user_token_param': user_token}).execute()
        return {"interviews": response.data}
    except Exception as e:
        logger.error(f"Ошибка истории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path(tempfile.gettempdir()) / "mock_interview_tts" / filename
    if audio_path.exists():
        return FileResponse(audio_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Аудио не найдено")


@app.get("/api/history/{interview_id}/messages")
async def get_interview_messages(interview_id: str):
    logger.info(f"🔍 Запрос сообщений для интервью: {interview_id}")
    try:
        response = supabase.table("messages").select("*").eq("interview_id", interview_id).order("created_at", desc=False).execute()
        return {"messages": response.data or []}
    except Exception as e:
        logger.error(f"❌ ОШИБКА получения сообщений: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.delete("/api/history/{interview_id}")
async def delete_interview(interview_id: str, user_token: str = Query("")):
    logger.info(f"🗑️ УДАЛЕНИЕ: interview_id={interview_id}, user_token={user_token}")
    
    if not user_token:
        raise HTTPException(status_code=400, detail="user_token не предоставлен")
    
    try:
        interview = supabase.table("interviews").select("id").eq("id", interview_id).eq("user_token", user_token).execute()
        
        if not interview.data:
            raise HTTPException(status_code=404, detail="Интервью не найдено")
        
        try:
            supabase.table("messages").delete().eq("interview_id", interview_id).execute()
        except Exception as e:
            logger.warning(f"Сообщения не удалены: {e}")
        
        try:
            supabase.table("adapted_resumes").delete().eq("interview_id", interview_id).execute()
        except Exception as e:
            logger.warning(f"Адаптированное резюме не удалено: {e}")
        
        supabase.table("interviews").delete().eq("id", interview_id).execute()
        return {"message": "Интервью удалено"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ ОШИБКА УДАЛЕНИЯ: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")


@app.post("/api/convert-to-pdf")
async def convert_to_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Только .docx")
    
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "resume.docx")
    output_path = os.path.join(temp_dir, "resume.pdf")
    
    try:
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        result = subprocess.run(
            ['libreoffice', '--headless', '--invisible', '--convert-to', 'pdf', '--outdir', temp_dir, input_path],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Ошибка: {result.stderr}")
        
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="PDF не создан")
        
        background_tasks.add_task(shutil.rmtree, temp_dir)
        
        return FileResponse(
            output_path,
            media_type="application/pdf",
            filename="resume.pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"}
        )
    except Exception as e:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        raise


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
