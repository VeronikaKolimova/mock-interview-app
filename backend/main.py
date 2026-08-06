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
logger = logging.getLogger(__name__)  # ✅ ИСПРАВЛЕНО: было __name__
app = FastAPI(title="Mock Interview API", version="1.0.0")


# ==========================================
# СЛОВАРЬ КОМПАНИЙ
# ==========================================
COMPANY_PROFILES = {
    "google": {"name": "Google", "style": "Google славится поведенческими интервью (STAR-метод), масштабией и культурой 'Googliness'.", "focus": "алгоритмы, системный дизайн"},
    "meta": {"name": "Meta", "style": "Meta делает упор на скорость, A/B тестирование, Move Fast менталитет.", "focus": "скорость, данные"},
    "apple": {"name": "Apple", "style": "Apple фокусируется на деталях и качестве продукта.", "focus": "качество, UX"},
    "amazon": {"name": "Amazon", "style": "Amazon проводит интервью по 16 Leadership Principles.", "focus": "Leadership Principles"},
    "microsoft": {"name": "Microsoft", "style": "Microsoft ценит growth mindset и экосистему продуктов.", "focus": "growth mindset"},
    "netflix": {"name": "Netflix", "style": "Netflix ценит свободу и ответственность.", "focus": "самостоятельность"},
    "nvidia": {"name": "NVIDIA", "style": "NVIDIA фокусируется на GPU, AI/ML и архитект.", "focus": "GPU, AI/ML"},
    "yandex": {"name": "Яндекс", "style": "Яндекс: алгоритмы, системный дизайн, highload.", "focus": "алгоритмы, highload"},
    "vk": {"name": "VK", "style": "VK: соцграфы, рекомендательные системы.", "focus": "соцграфы, рекомендации"},
    "sber": {"name": "Сбер", "style": "Сбер: финтех, ML, NLP.", "focus": "финтех, ML"},
    "tinkoff": {"name": "Т-Банк", "style": "Т-Банк: предпринимательский подход, данные.", "focus": "предпринимательство"},
    "ozon": {"name": "Ozon", "style": "Ozon: e-commerce, логистика, big data.", "focus": "e-commerce, big data"},
    "avito": {"name": "Авито", "style": "Авито: поиск, модерация, ML.", "focus": "поиск, ML"},
    "wildberries": {"name": "Wildberries", "style": "Wildberries: логистика, ценообразование.", "focus": "логистика"},
    "kaspersky": {"name": "Лаборатория Касперского", "style": "Касперский: кибербезопасность.", "focus": "кибербезопасность"},
    "jetbrains": {"name": "JetBrains", "style": "JetBrains: языки программи tools, IDE.", "focus": "языки, IDE"},
    "custom": {"name": "выбранная компания", "style": "Стандартное собеседование.", "focus": "общие вопросы"},
}


def get_company_info(company_id: Optional[str]) -> Optional[dict]:
    if not company_id:
        return None
    return COMPANY_PROFILES.get(company_id, COMPANY_PROFILES["custom"])


def build_interview_context(vacancy_text: Optional[str], resume_text: Optional[str], company_id: Optional[str]) -> dict:
    """Строит контекст интервью на основе доступных данных."""
    has_vacancy = bool(vacancy_text and vacancy_text.strip())
    has_resume = bool(resume_text and resume_text.strip())
    company_info = get_company_info(company_id)
    has_company = company_info is not None and company_id is not None

    company_block = ""
    if has_company:
        company_block = f"""
=== КОМПА: {company_info['name']} ===
Стиль: {company_info['style']}
Фокус: {company_info['focus']}
"""

    vacancy_block = ""
    if has_vacancy:
        vacancy_block = f"""
=== ТЕКСТ ВАКАНСИИ ===
{vacancy_text[:1500]}
=== КОНЕЦ ВАКСТІИ ===
"""

    resume_block = ""
    if has_resume:
        resume_block = f"""
=== РЕЗЮМЕ КАНДИДАТА ===
{resume_text[:1200]}
=== КОНЕЦ РЕЗЮМЕ ===
"""

    instructions = []
    if has_resume:
        instructions.append("✅ Есть резюме — используй его для персонализации.")
    else:
        instructions.append("⚠️ Резюме нет — не упоминай его.")

    if has_vacancy:
        instructions.append("✅ Есть вакансия — задавай релевантные вопросы.")
    else:
        instructions.append("⚠️ Вакансии нет — задавай общие вопросы.")

    if has_company:
        instructions.append(f"✅ Ты из {company_info['name']} — придерживайся стиля.")

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


# ==========================================
# HEALTHALTH CHECK
# ==========================================
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# ==========================================
# 1. ФУНКЦИИ ОЧИСТКИ
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
    cleaned_lines = [re.sub(r' {2,}', ' ', line.strip()) for line in lines]
    text = '\n'.join(cleaned_lines)
    return re.sub(r'\n{4,}', '\n\n', text).strip()


# ==========================================
# 2. НАСТРОЙКИ
# ==========================================
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
sessions: dict[str, SessionData] = {}
resumes: dict[str, str] = {}


# ✅ ИСПРАВЛЕНО: Класс определен ДО использования
class ResumeAdaptRequest(BaseModel):
    session_id: str
    resume_text: Optional[str] = None


# ==========================================
# 3. ЭНДПОИНТЫ
# ==========================================

@app.post("/api/interview/start")
async def start_interview(data: InterviewStart, user_token: str = Query("")) -> InterviewResponse:
    session_id = str(uuid.uuid4())

    # Получаем резюме
    resume_text = data.resume_text if hasattr(data, 'resume_text') else None
    if not resume_text and user_token:
        try:
            resume_data = supabase.table("resumes").select("resume_text").eq("user_token", user_token).order("created_at", desc=True).limit(1).execute()
            if resume_data.data:
                resume_text = resume_data.data[0]["resume_text"]
        except Exception as e:
            logger.warning(f"Не удалось получить резюме из БД: {e}")

    company_info = get_company_info(data.company)
    company_name = company_info["name"] if company_info else None

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
        logger.error(f"Ошибка создания интервью: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

    ctx = build_interview_context(data.vacancy_text, resume_text, data.company)
    logger.info(f"🎯 Режим: {ctx['interview_mode']} | Вакансия: {ctx['has_vacancy']} | Резюме: {ctx['has_resume']} | Компания: {ctx['has_company']}")

    interviewer_name = "Анна" if data.interviewer == "hr" else "Дмитрий"
    interviewer_role = "HR-менеджер" if data.interviewer == "hr" else "технический лид"

    # ✅ ИСПРАВЛЕНО: ДВОЙНЫЕ кавычки снаружи
    if ctx['has_company']:
        system_role = f"Ты {interviewer_role} {interviewer_name} из компании {ctx['company_name']}. Отвечай на русском."
    else:
        system_role = f"Ты {interviewer_role} {interviewer_name}. Отвечай на русском."

    company_mention = f" из компании {ctx['company_name']}" if ctx['has_company'] else ""

    # Выбор промпта в зависимости от режима
    if ctx['interview_mode'] == "full":
        greeting_prompt = f"""{ctx['company_block']}
Поздоровайся и представься как {interviewer_role} {interviewer_name}{company_mention}.
Скажи, что изучила вакансию и резюме. Задай первый вопрос.

{ctx['vacancy_block']}
{ctx['resume_block']}

ИНСТРУКЦИИ:
{ctx['instructions']}"""
    elif ctx['interview_mode'] == "vacancy_only":
        greeting_prompt = f"""{ctx['company_block']}
Поздоровайся и представься как {interviewer_role} {interviewer_name}{company_mention}.
Скажи, что изучила вакансию. Задай вопрос по ней.

{ctx['vacancy_block']}

ИНСТРУКЦИИ:
{ctx['instructions']}"""
    elif ctx['interview_mode'] == "resume_only":
        greeting_prompt = f"""{ctx['company_block']}
Поздоровайся и представься как {interviewer_role} {interviewer_name}{company_mention}.
Скажи, что ознакомилась с резюме. Задай вопрос по опыту.

{ctx['resume_block']}

ИНСТРУКЦИИ:
{ctx['instructions']}"""
    elif ctx['interview_mode'] == "company_only":
        greeting_prompt = f"""{ctx['company_block']}
Поздоровайся и представься как {interviewer_role} {interviewer_name}{company_mention}.
Задай первый открытый вопрос в стиле компании.

ИНСТРУКЦИИ:
{ctx['instructions']}"""
    else:
        greeting_prompt = f"""Поздоровайся и представься как {interviewer_role} {interviewer_name}.
Задай первый открытый вопрос о кандидате.

ИНСТРУКЦИИ:
{ctx['instructions']}"""

    greeting_messages = [
        {"role": "system", "content": system_role},
        {"role": "user", "content": greeting_prompt}
    ]

    greeting = ask_llm(greeting_messages, max_tokens=250)
    greeting = clean_llm_output(greeting)

    company_suffix = f", {ctx['company_name']}" if ctx['has_company'] else ""
    if data.interviewer == "hr":
        greeting = f"Анна (HR{company_suffix}): {greeting}"
    else:
        greeting = f"Дмитрий (Техлид{company_suffix}): {greeting}"

    session.messages.append(Message(role="assistant", content=greeting))

    try:
        supabase.table("messages").insert({
            "interview_id": session_id,
            "user_token": user_token,
            "role": "assistant",
            "content": greeting
        }).execute()
    except Exception as e:
        logger.error(f"Ошибка сохранения приветствия: {e}")

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
            logger.error(f"Ошибка сохранения резюме: {e}")

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

    try:
        supabase.table("messages").insert({
            "interview_id": data.session_id,
            "user_token": user_token,
            "role": "user",
            "content": data.answer
        }).execute()
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщения: {e}")

    min_questions = 3
    is_last_question = (session.question_idx >= min_questions)

    dialog_parts = []
    for m in session.messages:
        role_name = 'Интервьюер' if m.role == 'assistant' else 'Кандидат'
        dialog_parts.append(f"{role_name}: {m.content}")
    dialog_text = "\n\n".join(dialog_parts)

    ctx = build_interview_context(session.vacancy_text, session.resume_text, session.company)

    interviewer_name = "Анна" if session.interviewer == "hr" else "Дмитрий"
    interviewer_role = "HR-менеджер" if session.interviewer == "hr" else "технический лид"

    # ✅ ИСПРАВЛЕНО: ДВОЙНЫЕ кавычки снаружи
    if ctx['has_company']:
        system_content = f"Ты {interviewer_role} {interviewer_name} из компании {ctx['company_name']}."
    else:
        system_content = f"Ты {interviewer_role} {interviewer_name}."

    if is_last_question:
        reaction_prompt = f"""{ctx['company_block']}
Дай КРАТКУЮ реакцию (2-3 предложения) на ответ: '{data.answer}'
{ctx['vacancy_block']}
{ctx['resume_block']}
❗️ СТРОГО ЗАПРЕЩЕНО задавать новые вопросы.

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

        final_prompt = f"""{ctx['company_block']}
Подведи итоги. Диалог:
{dialog_text}

{ctx['vacancy_block']}
{ctx['resume_block']}

Дай решение и оценку из 10.

ИНСТРУКЦИИ:
{ctx['instructions']}"""

        final_messages = [
            {"role": "system", "content": "Ты эксперт по найму. Отвечай на русском. Включи '🎯 РЕШЕНИЕ:'"},
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
        question_prompt = f"""{ctx['company_block']}
История:
{dialog_text}

{ctx['vacancy_block']}
{ctx['resume_block']}

Дай КРАТКУЮ реакцию (1-2 предложения) на ответ: '{data.answer}'
Затем задай ОДИН следующий вопрос.

ИНСТУКЦИИ:
{ctx['instructions']}"""

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

    adapt_prompt = f"""Адаптируй резюме под вакансию.

СТРОГИЕ ПРАВИЛА:
- Используй ТОЛЬКО факты из резюме.
- ❗️ СОХРАНЯЙ ВСЕ ДАТЫ (месяц и год).
- ❗️ КАЖДЫЙ РАЗДЕЛ ТОЛЬКО ОДИН РАЗ.
- ❗️ ЗАПРЕЩЕНО добавлять примечания в конце.

Структура:
Контакты
Желаемая должность
Опыт работы (с датами!)
Образование (с датами!)
Навыки
Дополнительная информация

Резюме:
{clean_resume}

Вакансия:
{vacancy_text}

Интервью:
{dialog_text}"""

    messages = [
        {"role": "system", "content": "Ты карьерный консультант. Не выдумывай факты."},
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
        logger.info(f"✅ Адаптированное резюме сохранено для {data.session_id}")
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
    try:
        response = supabase.table("messages").select("*").eq("interview_id", interview_id).order("created_at", desc=False).execute()
        return {"messages": response.data or []}
    except Exception as e:
        logger.error(f"Ошибка получения сообщений: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/history/{interview_id}")
async def delete_interview(interview_id: str, user_token: str = Query("")):
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
            logger.warning(f"Резюме не удалено: {e}")

        supabase.table("interviews").delete().eq("id", interview_id).execute()
        return {"message": "Интервью удалено"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        except Exception:
            pass
        raise


# ✅ ИСПРАВЛЕНО: Читаем порт из переменной окружения Render
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
