from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from models.schemas import InterviewStart, AnswerSubmit, InterviewResponse, Message, SessionData
from services.llm import ask_llm
from services.tts import text_to_speech
import uuid
from datetime import datetime
from pathlib import Path
import tempfile
import logging
import os
import re
from services.file_parser import extract_text_from_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Interview API", version="1.0.0")

# ==========================================
# 1. ФУНКЦИЯ ОЧИСТКИ
# ==========================================
def clean_llm_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)
    text = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF]+', '', text)
    # Удаляем роботизированные фразы, если модель их все-таки сгенерировала
    text = re.sub(r'Понятно, спасибо за уточнение\.?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Хорошо, я вас услышала\.?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ==========================================
# 2. НАСТРОЙКИ И ПРОМПТЫ
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, SessionData] = {}

HR_PROMPT = """Ты — HR-менеджер Анна. Ты проводишь первичный скрининг на позицию ML-инженера.
Твоя цель: оценить мотивацию, soft skills и наличие базового опыта по ключевым требованиям.

❌ ЖЕСТКИЕ ПРАВИЛА КОНТЕНТА:
1. ТОЛЬКО РУССКИЙ ЯЗЫК.
2. НЕ ПРОВЕРЯЙ ГЛУБИНУ ЗНАНИЙ. Спрашивай о наличии опыта ("Был ли у вас опыт с PySpark?"), а не о том, как он работает.
3. ❗ АНТИ-ПОВТОР: Внимательно читай ИСТОРИЮ ДИАЛОГА. ЗАПРЕЩЕНО задавать один и тот же вопрос дважды. Если кандидат сказал "этот вопрос уже был", извинись и задай СОВЕРШЕННО ДРУГОЙ вопрос (про мотивацию, команду или другой навык).
4. ❗ АНТИ-РОБОТ: ЗАПРЕЩЕНО использовать фразы "Понятно, спасибо за уточнение", "Хорошо, я вас услышала", "Да, это очень важно". Отвечай как живой человек: "Понятно, спасибо, что поделились" или "Ясно, это полезный опыт".
5. Если кандидат говорит "нет опыта", прими это и спроси про готовность обучаться или про другой навык из вакансии."""

TECHLEAD_PROMPT = """Ты — технический лид Дмитрий. Ты проводишь техническое собеседование.
❌ ЖЕСТКИЕ ПРАВИЛА:
1. ТОЛЬКО РУССКИЙ ЯЗЫК (кроме терминов: Python, SQL, ETL, PySpark).
2. Задавай вопросы по существу: алгоритмы, данные, архитектура.
3. Не повторяй вопросы. Проверяй историю диалога."""

# ==========================================
# 3. ЭНДПОИНТЫ
# ==========================================
@app.post("/api/interview/start")
async def start_interview(data: InterviewStart) -> InterviewResponse:
    session_id = str(uuid.uuid4())
    session = SessionData(
        session_id=session_id,
        interviewer=data.interviewer,
        vacancy_text=data.vacancy_text,
        created_at=datetime.now().isoformat(),
        question_idx=1
    )
    sessions[session_id] = session
    
    if data.interviewer == "hr":
        greeting = "Анна (HR): Здравствуйте! Я изучила вашу вакансию. Начнём: расскажите немного о себе и почему вас заинтересовала именно эта позиция?"
    else:
        greeting = "Дмитрий (Техлид): Здравствуйте! Я ознакомился с требованиями вакансии. Расскажите о вашем опыте работы с технологиями, указанными в ней."
            
    session.messages.append(Message(role="assistant", content=greeting))
    
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

@app.post("/api/upload-vacancy")
async def upload_vacancy(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой. Макс: 10 MB")
            
        vacancy_text = extract_text_from_file(file_bytes, file.filename)
        if not vacancy_text or len(vacancy_text) < 50:
            raise HTTPException(status_code=400, detail="Не удалось извлечь текст.")
            
        return {"filename": file.filename, "text": vacancy_text, "length": len(vacancy_text)}
    except Exception as e:
        logger.error(f"Ошибка загрузки вакансии: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {str(e)}")

@app.post("/api/interview/answer")
async def submit_answer(data: AnswerSubmit) -> InterviewResponse:
    if data.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
        
    session = sessions[data.session_id]
    session.messages.append(Message(role="user", content=data.answer))
    
    min_questions = 8 if session.interviewer == "hr" else 12
    is_last_question = (session.question_idx >= min_questions)
    
    # КРИТИЧЕСКИ ВАЖНО: Собираем историю диалога для КАЖДОГО шага
    dialog_text = "\n".join([
        f"{'Интервьюер' if m.role == 'assistant' else 'Кандидат'}: {m.content}"
        for m in session.messages
    ])

    # ==========================================
    # ВАРИАНТ А: Финальная оценка
    # ==========================================
    if is_last_question:
        if session.interviewer == "hr":
            final_prompt = f"""Ты — HR-менеджер Анна. Подведи итоги.
❌ ЖЕСТКИЕ ПРАВИЛА:
1. Оценивай ТОЛЬКО soft skills: мотивацию, коммуникацию, честность, адаптивность.
2. ❗ ЗАПРЕЩЕНО упоминать отсутствие опыта в PySpark, QDrant, RECSYS или A/B тестах в "Зонах роста". Пиши ТОЛЬКО про поведение (например: "давать более развернутые ответы", "избегать односложных ответов").
3. Если решение "ДОРАЗГОВОР", рекомендация ОБЯЗАНА быть "Рекомендую передать техническому лиду".

Формат (без квадратных скобок):
🎯 РЕШЕНИЕ: [ПРИНЯТЬ на следующий этап / ДОРАЗГОВОР / ОТКАЗАТЬ]
📊 Оценка HR: [число от 1 до 10]
💪 СИЛЬНЫЕ СТОРОНЫ: [3 пункта, только soft skills]
📈 ЗОНЫ РОСТА: [2 пункта, только soft skills, НИКАКИХ технологий!]
💼 РЕКОМЕНДАЦИЯ: [Рекомендую передать техническому лиду / Кандидат не готов]
💰 ОЦЕНКА РЫНОЧНОЙ СТОИМОСТИ: [Junior (80-120к) / Middle (150-250к) / Senior (300к+)]

=== ИСТОРИЯ ДИАЛОГА ===
{dialog_text}"""
        else:
            final_prompt = f"""Ты — технический лид Дмитрий. Подведи итоги.
Формат:
🎯 РЕШЕНИЕ: [ПРИНЯТЬ / ДОРАЗГОВОР / ОТКАЗАТЬ]
📊 Оценка: [число от 1 до 10]
💪 СИЛЬНЫЕ СТОРОНЫ: [3 пункта, hard skills]
📈 ЗОНЫ РОСТА: [2-3 пункта, технические рекомендации]
💼 РЕКОМЕНДАЦИЯ: [Уровень позиции]
💰 ОЖИДАНИЯ ПО ЗАРПЛАТЕ: [Вилка в рублях]

=== ИСТОРИЯ ДИАЛОГА ===
{dialog_text}"""

        messages = [
            {"role": "system", "content": "Ты — эксперт по найму. Отвечай ТОЛЬКО на русском."},
            {"role": "user", "content": final_prompt}
        ]
        
        raw_response = ask_llm(messages, max_tokens=800)
        clean_response = clean_llm_output(raw_response)
        session.messages.append(Message(role="assistant", content=clean_response))
        
        audio_url = None
        if data.tts_enabled:
            try:
                text_for_tts = re.sub(r'[\*\#🎯📊💪📈💼💰]', '', clean_response).strip()
                audio_path = await text_to_speech(text_for_tts, session.interviewer)
                if audio_path:
                    audio_url = f"/audio/{Path(audio_path).name}"
            except Exception as e:
                logger.error(f"Ошибка TTS: {e}")
                
        return InterviewResponse(
            session_id=data.session_id,
            message=Message(role="assistant", content=clean_response),
            is_finished=True,
            final_feedback=clean_response
        )

    # ==========================================
    # ВАРИАНТ Б: Обычный ход интервью (ИСПРАВЛЕНО: добавлен dialog_text и полный текст вакансии)
    # ==========================================
    else:
        if session.interviewer == "hr":
            vacancy_context = f"\n\n=== ПОЛНЫЙ ТЕКСТ ВАКАНСИИ (Ключевые навыки: RECSYS, PySpark, OpenSearch, QDrant, A/B тесты) ===\n{session.vacancy_text}" if session.vacancy_text else ""
            
            user_message = f"""Ты — HR Анна. 
=== ИСТОРИЯ ДИАЛОГА (ВНИМАТЕЛЬНО ИЗУЧИ ЕЁ, ЧТОБЫ НЕ ПОВТОРЯТЬ ВОПРОСЫ!) ===
{dialog_text}

=== ПОСЛЕДНИЙ ОТВЕТ КАНДИДАТА ===
{data.answer}
{vacancy_context}

Твоя задача:
1. Дать естественную реакцию на последний ответ (НЕ используй фразы "Понятно, спасибо за уточнение" или "Хорошо, я вас услышала").
2. Задать ОДИН новый вопрос. Если ты уже спрашивала про RECSYS/PySpark/A/B тесты, спроси про QDrant, мотивацию или работу в команде.

❌ ЗАПРЕЩЕНО:
- Задавать один и тот же вопрос дважды. Если кандидат сказал "этот вопрос уже был", извинись и задай ДРУГОЙ вопрос.
- Спрашивать глубокие технические детали. Спрашивай только о наличии опыта.

✅ ФОРМАТ (СТРОГО 2 абзаца):
Оценка: [1-2 предложения реакции. Без вопросов.]
Вопрос: [Ровно один новый вопрос. Заканчивается на ?]"""
        else:
            user_message = f"""Ты — техлид Дмитрий. 
=== ИСТОРИЯ ДИАЛОГА ===
{dialog_text}

=== ПОСЛЕДНИЙ ОТВЕТ КАНДИДАТА ===
{data.answer}

Дай краткий технический фидбек. Затем задай СЛЕДУЮЩИЙ технический вопрос, который еще не задавался.
✅ ФОРМАТ:
Оценка: [Технический фидбек.]
Вопрос: [Один новый технический вопрос, заканчивающийся на ?]"""

        messages = [
            {"role": "system", "content": HR_PROMPT if session.interviewer == "hr" else TECHLEAD_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        raw_response = ask_llm(messages, max_tokens=600)
        clean_response = clean_llm_output(raw_response)
        session.messages.append(Message(role="assistant", content=clean_response))
        session.question_idx += 1
        
        audio_url = None
        if data.tts_enabled:
            try:
                text_for_tts = re.sub(r'[\*\#]', '', clean_response).strip()
                audio_path = await text_to_speech(text_for_tts, session.interviewer)
                if audio_path:
                    audio_url = f"/audio/{Path(audio_path).name}"
            except Exception as e:
                logger.error(f"Ошибка TTS: {e}")
                
        return InterviewResponse(
            session_id=data.session_id,
            message=Message(role="assistant", content=clean_response),
            audio_url=audio_url,
            is_finished=False
        )

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path(tempfile.gettempdir()) / "mock_interview_tts" / filename
    if audio_path.exists():
        return FileResponse(audio_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Аудио не найдено")

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
