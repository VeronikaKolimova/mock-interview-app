from fastapi import APIRouter, HTTPException
from models.schemas import InterviewStart, AnswerSubmit, InterviewResponse, Message, SessionData
from services.llm import ask_llm
from services.tts import text_to_speech
from app.services.prompts import (
    HR_SYSTEM_PROMPT, TECHLEAD_SYSTEM_PROMPT, 
    get_hr_user_message, get_techlead_user_message,
    get_final_hr_prompt, get_final_techlead_prompt
)
from app.utils.text_cleaner import clean_llm_output
import uuid
from datetime import datetime
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# Хранилище сессий (в будущем заменим на БД)
sessions: dict[str, SessionData] = {}

@router.post("/api/interview/start", response_model=InterviewResponse)
async def start_interview(data: InterviewStart):
    session_id = str(uuid.uuid4())
    session = SessionData(
        session_id=session_id,
        interviewer=data.interviewer,
        vacancy_text=data.vacancy_text,
        created_at=datetime.now().isoformat(),
        question_idx=1,
        messages=[]
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

@router.post("/api/interview/answer", response_model=InterviewResponse)
async def submit_answer(data: AnswerSubmit):
    if data.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
        
    session = sessions[data.session_id]
    session.messages.append(Message(role="user", content=data.answer))
    
    min_questions = 8 if session.interviewer == "hr" else 12
    is_last_question = (session.question_idx >= min_questions)
    
    # 🔥 КРИТИЧЕСКИ ВАЖНО: Собираем историю диалога для КАЖДОГО шага
    dialog_text = "\n".join([
        f"{'Интервьюер' if m.role == 'assistant' else 'Кандидат'}: {m.content}"
        for m in session.messages
    ])

    if is_last_question:
        prompt = get_final_hr_prompt(dialog_text) if session.interviewer == "hr" else get_final_techlead_prompt(dialog_text)
        system_prompt = "Ты — эксперт по найму. Отвечай ТОЛЬКО на русском."
    else:
        prompt = get_hr_user_message(data.answer, dialog_text, session.vacancy_text or "") if session.interviewer == "hr" else get_techlead_user_message(data.answer, dialog_text)
        system_prompt = HR_SYSTEM_PROMPT if session.interviewer == "hr" else TECHLEAD_SYSTEM_PROMPT

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    raw_response = ask_llm(messages, max_tokens=800 if is_last_question else 600)
    clean_response = clean_llm_output(raw_response)
    session.messages.append(Message(role="assistant", content=clean_response))
    
    if not is_last_question:
        session.question_idx += 1
        
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
        audio_url=audio_url,
        is_finished=is_last_question,
        final_feedback=clean_response if is_last_question else None
    )
