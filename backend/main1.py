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
# 1. ФУНКЦИЯ ОЧИСТКИ (Переименована для соответствия вызову)
# ==========================================

def clean_llm_output(text: str) -> str:
    """Агрессивно удаляет thinking-блоки, иероглифы и азиатскую пунктуацию."""
    if not text:
        return ""
    
    # 1. Удаляем теги <think>...</think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = text.replace("<think>", "").replace("</think>", "")
    
    # 2. Жестко удаляем ВСЕ китайские/японские/корейские иероглифы
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)
    
    # 3. НОВОЕ: Удаляем азиатские знаки препинания (полноширинные символы)
    # \u3000-\u303F : CJK Symbols and Punctuation
    # \uFF00-\uFFEF : Halfwidth and Fullwidth Forms (включая ： ， ？ ！)
    text = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF]+', '', text)
    
    # 4. Чистим артефакты: заменяем множественные пробелы и переносы строк на аккуратные
    text = re.sub(r'\s+', ' ', text) # Схлопываем все лишние пробелы в один
    text = re.sub(r'\n{3,}', '\n\n', text) # Не более двух переносов строки подряд
    
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

HR_PROMPT = """Ты — HR-менеджер Анна. Ты проводишь первичное собеседование. Твоя цель — оценить мотивацию, soft skills и карьерные цели.

❌ ЖЕСТКИЕ ПРАВИЛА КОНТЕНТА:
1. ТОЛЬКО РУССКИЙ ЯЗЫК. Никаких английских слов, иероглифов или смешения языков.
2. ЗАПРЕЩЕНО задавать технические вопросы (про код, алгоритмы, гиперпараметры). 
3. ПРАВИЛО ПЕРЕХВАТА: Если кандидат упоминает технические детали, НЕ спрашивай, КАК он это делал технически. Спроси про мотивацию, коммуникацию или трудности в команде.
4. ВНИМАТЕЛЬНО ЧИТАЙ КОНТЕКСТ: Не приписывай кандидату роли, которые он только упоминал (например, если он сказал "общался с сисадмином", не спрашивай "какие задачи ты решал как сисадмин").
5. ГОВОРИ ЕСТЕСТВЕННО: Избегай канцеляризмов. Говори как живой, эмпатичный человек.
6. ОБРАБОТКА НЕПОНЯТНОГО ТЕКСТА: Если ответ кандидата состоит из явного набора случайных символов (например, "фывамп", "asd", "<|im_start|>"), вежливо скажи: "Кажется, в вашем ответе есть опечатки. Пожалуйста, напишите ответ на русском языке, чтобы я смогла его оценить." 
   ❗️ ВАЖНО: НЕ применяй это правило, если кандидат просто дал короткий, честный или отрицательный ответ (например, "не знаю", "нет опыта", "я не поняла вопрос"). В этом случае просто мягко уточни или переходи к следующему вопросу.
7. АКТИВНОЕ ИСПОЛЬЗОВАНИЕ ВАКАНСИИ (КРИТИЧЕСКИ ВАЖНО) в случае ее загрузки: Если кандидат рассказывает о своем опыте, то ты должна связать это с требованиям вакансии.

❌ ЖЕСТКИЕ ПРАВИЛА ФОРМАТА (КРИТИЧЕСКИ ВАЖНО):
Твой ответ должен начинаться СТРОГО со слова "**Оценка:**". Никакого текста, приветствий или вопросов до этого слова!
Даже если ответ кандидата очень короткий (1-3 слова), ты ОБЯЗАН соблюсти этот формат.
В блоке "**Вопрос:**" должен быть РОВНО ОДИН вопрос, заканчивающийся на знак (?). Запрещено задавать два вопроса подряд или добавлять уточнения после основного вопроса.

Формат ответа:
**Оценка:** [1-2 предложения. Спокойная реакция на ответ. ЗАПРЕЩЕНО использовать знак вопроса (?) в этом блоке].
**Вопрос:** [Ровно один новый, естественный вопрос о мотивации, команде или карьерных планах. Обязательно заканчивается знаком вопроса (?).]

✅ ПРИМЕР (скопируй структуру):
**Оценка:** Понятно, что работа с данными вам действительно близка. Это отличная основа для старта.
**Вопрос:** С какими самыми интересными типами данных вам доводилось работать в прошлом?"""

TECHLEAD_PROMPT = """Ты — технический лид Дмитрий. Ты проводишь техническое собеседование на позицию Data Scientist / ML Engineer.

❌ ЖЕСТКИЕ ПРАВИЛА КОНТЕНТА:
1. ТОЛЬКО РУССКИЙ ЯЗЫК. Никаких английских слов (кроме общепринятых технических терминов, таких как Python, SQL, ETL, но не целых фраз), иероглифов или смешения языков.
2. ЗАДАВАЙ ВОПРОСЫ ПО СУЩЕСТВУ: проверяй понимание алгоритмов, работы с данными, архитектуры решений и Python.
3. ВНИМАТЕЛЬНО ЧИТАЙ КОНТЕКСТ: Не придумывай кандидату опыт, которого не было. Опирайся только на его ответы.
4. УЧЕТ ВАКАНСИИ: Если в системном контексте передан текст вакансии, фокусируй вопросы на технологиях и задачах, указанных в ней.
5. ЗАПРЕЩЕНО обрывать фразы на полуслове.

❌ ЖЕСТКИЕ ПРАВИЛА ФОРМАТА (КРИТИЧЕСКИ ВАЖНО):
Твой ответ должен начинаться СТРОГО со слова "**Оценка:**". 
В блоке "**Вопрос:**" должен быть РОВНО ОДИН технический вопрос, заканчивающийся на знак (?).

Формат ответа:
**Оценка:** [1-2 предложения. Краткий технический фидбек на ответ кандидата. Без вопросов].
**Вопрос:** [Ровно один новый технический вопрос. Обязательно заканчивается знаком вопроса (?).]

✅ ПРИМЕР (скопируй структуру):
**Оценка:** Вы верно описали принцип работы градиентного спуска и упомянули проблему затухающих градиентов.
**Вопрос:** Какие конкретные методы оптимизации или функции активации вы бы использовали, чтобы решить эту проблему в вашей модели?"""

# ==========================================
# 3. ЭНДПОИНТЫ
# ==========================================
@app.post("/api/interview/start")
async def start_interview(data: InterviewStart) -> InterviewResponse:
    session_id = str(uuid.uuid4())
    
    session = SessionData(
        session_id=session_id,
        interviewer=data.interviewer,
        vacancy_text=data.vacancy_text,  # ← НОВОЕ
        created_at=datetime.now().isoformat(),
        question_idx=1
    )
    sessions[session_id] = session
    
    # Формируем приветствие с учетом вакансии
    if data.interviewer == "hr":
        if data.vacancy_text:
            greeting = "Анна (HR): Здравствуйте! Я изучила вашу вакансию и готова провести собеседование с её учётом. Начнём: расскажите немного о себе и о том, почему вас заинтересовала именно эта позиция?"
        else:
            greeting = "Анна (HR): Здравствуйте! Меня зовут Анна, я HR-менеджер. Сегодня проведу с вами первичное собеседование.\n\nНачнём: расскажите немного о себе и о том, что привело вас к Data Science?"
    else:
        if data.vacancy_text:
            greeting = "Дмитрий (Техлид): Здравствуйте! Я ознакомился с требованиями вакансии. Давайте проверим ваши технические навыки. Расскажите о вашем опыте работы с технологиями, указанными в вакансии."
        else:
            greeting = "Дмитрий (Техлид): Здравствуйте! Начнём техническое собеседование. Расскажите о вашем опыте работы с Python и ML-библиотеками."
    
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
    """Загрузка файла вакансии и извлечение текста."""
    try:
        # Проверяем размер файла (макс 10 MB)
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой. Максимальный размер: 10 MB")
        
        # Извлекаем текст
        vacancy_text = extract_text_from_file(file_bytes, file.filename)
        
        if not vacancy_text or len(vacancy_text) < 50:
            raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла. Убедитесь, что файл содержит текст, а не только изображения.")
        
        return {
            "filename": file.filename,
            "text": vacancy_text,
            "length": len(vacancy_text)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка загрузки вакансии: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {str(e)}")

@app.post("/api/interview/answer")
async def submit_answer(data: AnswerSubmit) -> InterviewResponse:
    """Отправка ответа кандидата."""
    if data.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    session = sessions[data.session_id]
    session.messages.append(Message(role="user", content=data.answer))
    
    min_questions = 8 if session.interviewer == "hr" else 12
    is_last_question = (session.question_idx >= min_questions)
    
    # ==========================================
    # ВАРИАНТ А: Это последний вопрос (Финальная оценка)
    # ==========================================
    if is_last_question:
        dialog_text = "\n\n".join([
            f"{'Интервьюер' if m.role == 'assistant' else 'Кандидат'}: {m.content}"
            for m in session.messages
        ])
        vacancy_context = f"\n\n=== ТЕКСТ ВАКАНСИИ ===\n{session.vacancy_text}\n" if session.vacancy_text else ""
        if session.interviewer == "hr":
            final_prompt = f"""Ты — HR-менеджер Анна. Это последний этап собеседования.

Твой ответ должен состоять из ДВУХ четко разделенных частей. Не используй квадратные скобки [] в своем ответе!

ЧАСТЬ 1: Фидбек на последний ответ
Напиши 1-2 предложения реакции ИМЕННО на последний ответ кандидата. Заканчивай этот абзац точкой.

ЧАСТЬ 2: Итоговая оценка
Сразу после фидбека выведи оценку по строгому шаблону ниже:

❌ ЖЕСТКИЕ ПРАВИЛА:
1. ТОЛЬКО РУССКИЙ ЯЗЫК. Никаких иероглифов, английских слов или смешения языков.
2. Оценивай ТОЛЬКО soft skills: мотивацию, коммуникацию, четкость изложения мыслей, стремление к развитию. 
3. ЗАПРЕЩЕНО упоминать "алгоритмы", "гиперпараметры", "код" или "модели" в сильных сторонах или зонах роста. Ты оцениваешь только личность и мотивацию.
4. ДИНАМИЧЕСКАЯ ЗАРПЛАТА: Оцени предполагаемый уровень кандидата (Junior, Middle, Senior) на основе сложности описанных им ситуаций (например, управление кросс-функциональной коммуникацией или обход бюрократии — это признаки Middle+ или Senior). 
   - Junior: 80 000 - 120 000 руб.
   - Middle: 150 000 - 250 000 руб.
   - Senior/Lead: 300 000+ руб.
   Укажи реалистичную вилку, соответствующую твоей оценке его уровня.


🎯 РЕШЕНИЕ: [ПРИНЯТЬ на следующий этап / ДОРАЗГОВОР / ОТКАЗАТЬ]
📊 Оценка HR: [X из 10]
💪 СИЛЬНЫЕ СТОРОНЫ (soft skills): [3 пункта, например: кросс-функциональное взаимодействие, эмпатия, четкая карьерная траектория]
📈 ЗОНЫ РОСТА (soft skills): [2-3 пункта, конструктивная критика, например: "Учиться формулировать более развернутые ответы, приводя конкретные примеры (метод STAR)", "Избегать общих фраз"]
💼 РЕКОМЕНДАЦИЯ: [Например: "Рекомендую передать техническому лиду для оценки хард-скиллов"]
💰 ОЦЕНКА РЫНОЧНОЙ СТОИМОСТИ: [Укажи уровень (Junior/Middle/Senior) и соответствующую вилку в рублях, исходя из правил выше]

История диалога:
{dialog_text}"""
        else:
            final_prompt = f"""Ты — технический лид Дмитрий. Подведи итоги технического собеседования.

❌ ЖЕСТКИЕ ПРАВИЛА:
1. Пиши ТОЛЬКО на русском языке.
2. Оценивай ТОЛЬКО hard skills: знание Python, ML, работу с данными.
3. Зарплатная вилка: реалистичная для рынка РФ (150 000 - 250 000 рублей для Middle).

Формат ответа:
🎯 РЕШЕНИЕ: [ПРИНЯТЬ / ДОРАЗГОВОР / ОТКАЗАТЬ]
📊 Оценка: [X из 10]
💪 СИЛЬНЫЕ СТОРОНЫ (hard skills): [3 пункта]
📈 ЗОНЫ РОСТА: [2-3 пункта]
💼 РЕКОМЕНДАЦИЯ: [Уровень позиции]
💰 ОЖИДАНИЯ ПО ЗАРПЛАТЕ: [Реалистичная вилка в рублях]

История диалога:
{dialog_text}"""
        
        messages = [
            {"role": "system", "content": "Ты — эксперт по найму. Отвечай ТОЛЬКО на русском языке."},
            {"role": "user", "content": final_prompt}
        ]
        
        raw_response = ask_llm(messages, max_tokens=800)
        clean_response = clean_llm_output(raw_response) # <-- ТЕПЕРЬ ИМЕНА СОВПАДАЮТ
        
        session.messages.append(Message(role="assistant", content=clean_response))
        
        # === ОЧИСТКА ДЛЯ TTS (ЧТОБЫ НЕ ЧИТАЛ ЗВЕЗДОЧКИ) ===
        audio_url = None
        if data.tts_enabled:
            try:
                # 1. Создаем очищенную версию текста специально для голоса
                text_for_tts = re.sub(r'\*+', '', clean_response).strip()
                
                # 2. Передаем в TTS именно очищенную версию!
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
    # ВАРИАНТ Б: Обычный ход интервью
    # ==========================================
    else:
        if session.interviewer == "hr":
            vacancy_hint = f"\nНАПОМИНАНИЕ О ВАКАНСИИ: {session.vacancy_text[:500]}..." if session.vacancy_text else ""
            user_message = f"""Ты — HR Анна. Кандидат только что ответил. {vacancy_hint}

Твоя задача:
1. Дать краткую реакцию (оценку) на сказанное.
2. Задать ОДИН следующий вопрос.

❌ ЖЕСТКИЕ ПРАВИЛА ФОРМАТА (СТРОГО СОБЛЮДАЙ ЭТУ СТРУКТУРУ):
Твой ответ должен состоять РОВНО из двух блоков. Никакого текста, приветствий или обрывков после второго блока:
**Оценка:** [1-2 предложения. Спокойная реакция. ЗАПРЕЩЕНО использовать знак вопроса (?) здесь].
**Вопрос:** [Ровно один новый вопрос о мотивации, команде или карьерных планах. Обязательно заканчивается на (?).]

❌ ЖЕСТКИЕ ПРАВИЛА КОНТЕНТА:
- ТОЛЬКО РУССКИЙ ЯЗЫК. Никаких английских слов (даже "Motivation", "OK").
- Если кандидат говорит о коде/Python, НЕ спорь с ним о содержании вакансии. Просто мягко переведи тему: "Понятно. А что именно в этой работе мотивирует вас помимо технических аспектов?"
- Если кандидат говорит о своем опыте, свяжи его с задачами из текста вакансии 
- Если ответ короткий или странный, вежливо попроси переформулировать: "Не могли бы вы выразиться чуть подробнее?"

=== ОТВЕТ КАНДИДАТА ===
{data.answer}"""
        else:
            user_message = f"""Ты — техлид Дмитрий. Кандидат ответил.
Дай краткую обратную связь (2-3 предложения).
Затем задай СЛЕДУЮЩИЙ технический вопрос.
Пиши ТОЛЬКО на русском.

=== ОТВЕТ КАНДИДАТА ===
{data.answer}"""
        
        messages = [
            {"role": "system", "content": HR_PROMPT if session.interviewer == "hr" else TECHLEAD_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        raw_response = ask_llm(messages, max_tokens=600) # <-- Уменьшили до 600, чтобы не генерировал лишнего
        clean_response = clean_llm_output(raw_response)
        
        session.messages.append(Message(role="assistant", content=clean_response))
        session.question_idx += 1
        
        audio_url = None
        if data.tts_enabled:
            try:
                text_for_tts = re.sub(r'\*+', '', clean_response).strip()
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
    """Раздача аудио файлов."""
    audio_path = Path(tempfile.gettempdir()) / "mock_interview_tts" / filename
    if audio_path.exists():
        return FileResponse(audio_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Аудио не найдено")

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Получить историю сессии."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
