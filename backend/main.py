import os
import subprocess
import shutil
from fastapi import BackgroundTasks,  FastAPI, HTTPException, UploadFile, File, Query
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

supabase = get_supabase_client()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Interview API", version="1.0.0")

# ==========================================
# 1. ФУНКЦИИ ОЧИСТКИ
# ==========================================
def sanitize_pii(text: str) -> str:
    if not text: return text
    
    # 1. Удаляем email и телефоны (это 100% ПДн)
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', text, flags=re.IGNORECASE)
    text = re.sub(r'(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', '[ТЕЛЕФОН]', text)
    
    # 2. Удаляем ссылки и Telegram
    text = re.sub(r'(https?://t\.me/|@)[a-zA-Z0-9_]{5,32}', '[TELEGRAM]', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+', '[ССЫЛКА]', text)
    
    # 3. БЕЗОПАСНОЕ удаление ФИО: только если это самая первая строка документа
    lines = text.split('\n')
    if lines:
        first_line = lines[0].strip()
        # Проверяем, выглядит ли первая строка как "Фамилия Имя" (2-3 слова с большой буквы)
        if re.match(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(\s+[А-ЯЁ][а-яё]+)?$', first_line):
            lines[0] = '[ИМЯ ФАМИЛИЯ]'
    text = '\n'.join(lines)
    
    # 4. Убираем возраст и пол (явные маркеры)
    text = re.sub(r'(Дата рождения|Возраст|Год рождения)[:\s]*.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(Женщина|Мужчина)\b', '', text)
    
    return text.strip()
def clean_llm_output(text: str) -> str:
    if not text: return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = text.replace("<think>", "").replace("</think>", "")
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)
    text = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF]+', '', text)
    
    # ИСПРАВЛЕНО: Сохраняем переносы строк, убираем только лишние пробелы внутри строк
    lines = text.split('\n')
    cleaned_lines = [re.sub(r' {2,}', ' ', line.strip()) for line in lines if line.strip() or True]
    text = '\n'.join(cleaned_lines)
    return re.sub(r'\n{4,}', '\n\n', text).strip()

# ==========================================
# 2. НАСТРОЙКИ
# ==========================================
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
sessions: dict[str, SessionData] = {}
resumes: dict[str, str] = {}

class ResumeAdaptRequest(BaseModel):
    session_id: str
    resume_text: Optional[str] = None

# ==========================================
# 3. ЭНДПОИНТЫ
# ==========================================
@app.post("/api/interview/start")
async def start_interview(data: InterviewStart, user_token: str = Query("")) -> InterviewResponse:
    session_id = str(uuid.uuid4())
    # Сохраняем интервью в БД (без try-except, чтобы видеть ошибки)
    supabase.table("interviews").insert({"id": session_id, "user_token": user_token, "interviewer_type": data.interviewer, "status": "in_progress", "final_feedback": None}).execute()
    
    session = SessionData(session_id=session_id, interviewer=data.interviewer, vacancy_text=data.vacancy_text, created_at=datetime.now().isoformat(), question_idx=1, messages=[])
    sessions[session_id] = session
    
    # 🔥 НОВОЕ: Генерируем приветствие с учётом вакансии (СТРОГИЙ ЗАПРЕТ на упоминание резюме)
    if data.vacancy_text:
        vacancy_context = f"\n\n=== ТЕКСТ ВАКАНСИИ ===\n{data.vacancy_text[:1500]}\n=== КОНЕЦ ВАКАНСИИ ==="
        greeting_prompt = f"Поздоровайся с кандидатом и представься. Скажи, что ты изучила требования этой вакансии и готова провести собеседование. Задай первый открытый вопрос о мотивации кандидата или его общем опыте, релевантном этой вакансии.\n\n❗️ ВАЖНО: НИ В КОЕМ СЛУЧАЕ не упоминай, что ты читала резюме кандидата, так как он его не загружал. Опирайся ТОЛЬКО на текст вакансии ниже.{vacancy_context}"
        greeting_messages = [{"role": "system", "content": "Ты HR-менеджер Анна." if data.interviewer == "hr" else "Ты технический лид Дмитрий."}, {"role": "user", "content": greeting_prompt}]
        greeting = ask_llm(greeting_messages, max_tokens=200)
        greeting = clean_llm_output(greeting)
        if data.interviewer == "hr":
            greeting = f"Анна (HR): {greeting}"
        else:
            greeting = f"Дмитрий (Техлид): {greeting}"
    else:
        greeting = "Анна (HR): Здравствуйте! Расскажите о себе и почему вас заинтересовала эта позиция?" if data.interviewer == "hr" else "Дмитрий (Техлид): Здравствуйте! Расскажите о вашем опыте с технологиями из вакансии."
    
    session.messages.append(Message(role="assistant", content=greeting))
    
    # 🔥 НОВОЕ: Сохраняем приветствие интервьюера в БД
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
            if audio_path: audio_url = f"/audio/{Path(audio_path).name}"
        except Exception as e: logger.error(f"Ошибка TTS: {e}")
            
    return InterviewResponse(session_id=session_id, message=Message(role="assistant", content=greeting), audio_url=audio_url)

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...), user_token: str = Query("")):
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024: raise HTTPException(status_code=400, detail="Файл слишком большой. Макс: 10 MB")
        raw_text = extract_text_from_file(file_bytes, file.filename)
        if not raw_text or len(raw_text) < 50: raise HTTPException(status_code=400, detail="Не удалось извлечь текст.")
        
        clean_text = sanitize_pii(raw_text)
        resume_id = str(uuid.uuid4())
        resumes[resume_id] = clean_text
        
        try:
            supabase.table("resumes").insert({"id": resume_id, "user_token": user_token, "resume_text": clean_text, "filename": file.filename}).execute()
        except Exception as e: logger.error(f"Ошибка сохранения резюме в БД: {e}")
        
        return {"resume_id": resume_id, "filename": file.filename, "text": clean_text, "length": len(clean_text)}
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-vacancy")
async def upload_vacancy(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024: raise HTTPException(status_code=400, detail="Файл слишком большой.")
        vacancy_text = extract_text_from_file(file_bytes, file.filename)
        if not vacancy_text or len(vacancy_text) < 50: raise HTTPException(status_code=400, detail="Не удалось извлечь текст.")
        return {"filename": file.filename, "text": vacancy_text, "length": len(vacancy_text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/interview/answer")
async def submit_answer(data: AnswerSubmit, user_token: str = Query("")) -> InterviewResponse:
    if data.session_id not in sessions: raise HTTPException(status_code=404, detail="Сессия не найдена")
    session = sessions[data.session_id]
    session.messages.append(Message(role="user", content=data.answer))
    
    # Сохраняем сообщение в БД (без try-except, чтобы видеть ошибки)
    supabase.table("messages").insert({"interview_id": data.session_id, "user_token": user_token, "role": "user", "content": data.answer}).execute()
    
    min_questions = 3 # Временно для теста
    is_last_question = (session.question_idx >= min_questions)
    dialog_text = "\n\n".join([f"{'Интервьюер' if m.role == 'assistant' else 'Кандидат'}: {m.content}" for m in session.messages])
    
    if is_last_question:
        # 1. Реакция на последний ответ
        last_answer = data.answer
        vacancy_context = f"\n\n=== ВАКАНСИЯ ===\n{session.vacancy_text[:1000]}\n=== КОНЕЦ ===" if session.vacancy_text else ""
        
        reaction_prompt = f"Дай КРАТКУЮ реакцию (2-3 предложения) на последний ответ кандидата: '{last_answer}'. Учитывай контекст вакансии. ❗️ СТРОГО ЗАПРЕЩЕНО задавать новые вопросы, это финальный ответ перед завершением интервью.{vacancy_context}"
        reaction_messages = [{"role": "system", "content": "Ты HR-менеджер Анна." if session.interviewer == "hr" else "Ты технический лид Дмитрий."}, {"role": "user", "content": reaction_prompt}]
        reaction = ask_llm(reaction_messages, max_tokens=200)
        reaction = clean_llm_output(reaction)
        
        # Сохраняем реакцию в messages
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
        final_prompt = f"Подведи итоги интервью. Диалог: {dialog_text}{vacancy_context}. Дай решение и оценку из 10."
        messages = [{"role": "system", "content": "Ты эксперт по найму. Отвечай на русском. Включи в ответ '🎯 РЕШЕНИЕ:'"}, {"role": "user", "content": final_prompt}]
        raw_response = ask_llm(messages, max_tokens=800)
        clean_response = clean_llm_output(raw_response)
        
        # Объединяем для отображения в чате
        combined_response = f"{reaction}\n\n{clean_response}"
        session.messages.append(Message(role="assistant", content=combined_response))
        
        # Сохраняем только решение в final_feedback
        try:
            supabase.table("interviews").update({"status": "finished", "final_feedback": clean_response}).eq("id", data.session_id).execute()
        except Exception as e: 
            logger.error(f"Ошибка обновления статуса: {e}")
            
        return InterviewResponse(session_id=data.session_id, message=Message(role="assistant", content=combined_response), is_finished=True, final_feedback=clean_response)
    else:
        # 🔥 НОВОЕ: Генерируем реакцию и вопрос отдельно
        vacancy_context = ""
        if session.vacancy_text:
            vacancy_context = f"\n\n=== ВАКАНСИЯ ===\n{session.vacancy_text[:1500]}\n=== КОНЕЦ ==="
        
        # 1. Генерируем ТОЛЬКО реакцию на последний ответ
        reaction_prompt = f"Дай КРАТКУЮ реакцию (1-2 предложения) на последний ответ кандидата: '{data.answer}'{vacancy_context}"
        reaction_messages = [{"role": "system", "content": "Ты HR-менеджер Анна." if session.interviewer == "hr" else "Ты технический лид Дмитрий."}, {"role": "user", "content": reaction_prompt}]
        reaction = ask_llm(reaction_messages, max_tokens=150)
        reaction = clean_llm_output(reaction)
        
        # Сохраняем реакцию в messages
        try:
            supabase.table("messages").insert({
                "interview_id": data.session_id,
                "user_token": user_token,
                "role": "assistant",
                "content": reaction
            }).execute()
        except Exception as e:
            logger.error(f"Ошибка сохранения реакции: {e}")
        
        # 2. Генерируем следующий вопрос
        question_prompt = f"История диалога: {dialog_text}\n\nЗадай ОДИН следующий вопрос кандидату{vacancy_context}"
        question_messages = [{"role": "system", "content": "Ты HR-менеджер Анна." if session.interviewer == "hr" else "Ты технический лид Дмитрий."}, {"role": "user", "content": question_prompt}]
        question = ask_llm(question_messages, max_tokens=300)
        question = clean_llm_output(question)
        
        # Сохраняем вопрос в messages
        try:
            supabase.table("messages").insert({
                "interview_id": data.session_id,
                "user_token": user_token,
                "role": "assistant",
                "content": question
            }).execute()
        except Exception as e:
            logger.error(f"Ошибка сохранения вопроса: {e}")
        
        # Объединяем для отображения в чате
        combined_response = f"{reaction}\n\n{question}"
        session.messages.append(Message(role="assistant", content=combined_response))
        session.question_idx += 1
        
        return InterviewResponse(session_id=data.session_id, message=Message(role="assistant", content=combined_response), is_finished=False)

@app.post("/api/adapt-resume")
async def adapt_resume(data: ResumeAdaptRequest, user_token: str = Query("")):
    if data.session_id not in sessions: raise HTTPException(status_code=404, detail="Сессия не найдена")
    session = sessions[data.session_id]
    
    resume_text = data.resume_text or (list(resumes.values())[-1] if resumes else "")
    if not resume_text: raise HTTPException(status_code=400, detail="Текст резюме не найден.")
    
    vacancy_text = session.vacancy_text or ""
    dialog_text = "\n".join([f"{m.role}: {m.content}" for m in session.messages])
    
    clean_resume = re.sub(r'\|.*?\|', '\n', resume_text)
    clean_resume = re.sub(r'\n{3,}', '\n\n', clean_resume).strip()
    
    adapt_prompt = f"""Адаптируй резюме под вакансию ML-инженера.

СТРОГИЕ ПРАВИЛА (нарушение недопустимо):
1. Используй ТОЛЬКО факты из исходного резюме. Не выдумывай данные (пиши [ИМЯ ФАМИЛИЯ], [ТЕЛЕФОН]).
2. ❗️ СОХРАНЯЙ ВСЕ ДАТЫ (месяц и год) для КАЖДОГО места работы и учебы. Не удаляй их и не сокращай только до годов.
3. ❗️ КАЖДЫЙ РАЗДЕЛ ДОЛЖЕН БЫТЬ ТОЛЬКО ОДИН РАЗ. Не дублируй заголовки.
4. ❗️ ЗАПРЕЩЕНО добавлять любые примечания, комментарии от себя, пояснения или заключительные фразы в конце текста (например, "Примечание: В резюме я исключил..."). Резюме должно заканчиваться сразу после последнего пункта раздела "Дополнительная информация" или "Навыки".

Структура:
- Контакты
- Желаемая должность
- Опыт работы (строго с датами!)
- Образование (строго с датами!)
- Навыки
- Дополнительная информация

Резюме:
{clean_resume}

Вакансия:
{vacancy_text}

Интервью:
{dialog_text}"""
    
    messages = [{"role": "system", "content": "Ты профессиональный карьерный консультант. Никогда не выдумывай факты."}, {"role": "user", "content": adapt_prompt}]
    
    clean_response = "Ошибка AI."
    try:
        raw_response = ask_llm(messages, max_tokens=2000)
        clean_response = clean_llm_output(raw_response)
    except Exception as e: logger.error(f"Ошибка LLM: {e}")

    try:
        # 🔥 UPSERT: если запись уже существует (например, была "Ошибка AI"), обновляем её
        # Сначала пытаемся удалить старую запись для этого interview_id
        supabase.table("adapted_resumes").delete().eq("interview_id", data.session_id).execute()
        
        # Затем создаём новую запись с успешным результатом
        supabase.table("adapted_resumes").insert({
            "interview_id": data.session_id, 
            "user_token": user_token, 
            "adapted_text": clean_response, 
            "vacancy_text": vacancy_text
        }).execute()
        logger.info(f"✅ Адаптированное резюме сохранено/обновлено для интервью {data.session_id}")
    except Exception as e: 
        logger.error(f"Ошибка сохранения адаптации: {e}")

    return {"original_resume_preview": clean_resume[:200] + "...", "adapted_resume": clean_response, "session_id": data.session_id}

@app.get("/api/history")
async def get_history(user_token: str = Query("")):
    if not user_token: raise HTTPException(status_code=400, detail="user_token не предоставлен")
    try:
        response = supabase.rpc('get_user_history', {'user_token_param': user_token}).execute()
        return {"interviews": response.data}
    except Exception as e:
        logger.error(f"Ошибка истории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка")

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path(tempfile.gettempdir()) / "mock_interview_tts" / filename
    if audio_path.exists(): return FileResponse(audio_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Аудио не найдено")
    
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


@app.get("/api/history/{interview_id}/messages")
async def get_interview_messages(interview_id: str):
    """Получить полную историю сообщений конкретного интервью из БД."""
    logger.info(f"🔍 Запрос сообщений для интервью: {interview_id}")
    try:
        # Используем select("*") и явную сортировку для надежности
        response = supabase.table("messages").select("*").eq("interview_id", interview_id).order("created_at", desc=False).execute()
        logger.info(f"✅ Найдено сообщений: {len(response.data) if response.data else 0}")
        return {"messages": response.data or []}
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА получения сообщений: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения сообщений: {str(e)}")


@app.delete("/api/history/{interview_id}")
async def delete_interview(interview_id: str, user_token: str = Query("")):
    """Удалить конкретное интервью и связанные данные."""
    logger.info(f"🗑️ ЗАПРОС НА УДАЛЕНИЕ: interview_id={interview_id}, user_token={user_token}")
    
    if not user_token:
        logger.error("❌ Ошибка: user_token пустой!")
        raise HTTPException(status_code=400, detail="user_token не предоставлен")
    
    try:
        # 1. Проверяем принадлежность
        interview = supabase.table("interviews").select("id").eq("id", interview_id).eq("user_token", user_token).execute()
        logger.info(f"🔍 Результат проверки интервью: {interview.data}")
        
        if not interview.data:
            raise HTTPException(status_code=404, detail="Интервью не найдено или не принадлежит вам")
        
        # 2. Удаляем связанные данные (по отдельности, чтобы сбой одной таблицы не ломал всё)
        try:
            logger.info("Удаляем сообщения...")
            supabase.table("messages").delete().eq("interview_id", interview_id).execute()
        except Exception as e:
            logger.warning(f"Сообщения не удалены (возможно, их нет): {e}")
            
        try:
            logger.info("Удаляем адаптированное резюме...")
            supabase.table("adapted_resumes").delete().eq("interview_id", interview_id).execute()
        except Exception as e:
            logger.warning(f"Адаптированное резюме не удалено (возможно, его нет): {e}")
        
        # 3. Удаляем само интервью (это главное)
        logger.info("Удаляем интервью...")
        supabase.table("interviews").delete().eq("id", interview_id).execute()
        
        logger.info("✅ Интервью успешно удалено из БД!")
        return {"message": "Интервью удалено"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА УДАЛЕНИЯ: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")


@app.post("/api/convert-to-pdf")
async def convert_to_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Конвертирует Word в PDF транзитно (без сохранения на сервере)."""
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Поддерживается только формат .docx")
    
    # Создаём временную директорию
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "resume.docx")
    output_path = os.path.join(temp_dir, "resume.pdf")
    
    try:
        # Сохраняем загруженный файл
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Конвертируем через LibreOffice headless
        result = subprocess.run(
            ['libreoffice', '--headless', '--invisible', '--convert-to', 'pdf', '--outdir', temp_dir, input_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"❌ LibreOffice STDOUT: {result.stdout}")
            logger.error(f"❌ LibreOffice STDERR: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Ошибка конвертации: {result.stderr}")
        
        if not os.path.exists(output_path):
            logger.error(f"Файл {output_path} не найден. Содержимое папки: {os.listdir(temp_dir)}")
            raise HTTPException(status_code=500, detail="PDF не создан")
        
        # 🔥 КРИТИЧНО: Добавляем удаление в фоновую задачу ПОСЛЕ отправки ответа клиенту
        background_tasks.add_task(shutil.rmtree, temp_dir)
        logger.info("✅ Запланировано безопасное удаление временных файлов после отправки")
        
        return FileResponse(
            output_path,
            media_type="application/pdf",
            filename="resume.pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"}
        )
        
    except Exception as e:
        # В случае любой ошибки тоже чистим за собой
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
