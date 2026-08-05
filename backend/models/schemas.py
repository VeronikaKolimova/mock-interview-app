from pydantic import BaseModel, Field
from typing import List, Optional


class Message(BaseModel):
    """Одно сообщение в диалоге (от пользователя или интервьюера)."""
    role: str = Field(..., description="Роль: 'user' (кандидат) или 'assistant' (интервьюер)")
    content: str = Field(..., description="Текст сообщения")


class SessionData(BaseModel):
    """Полное состояние сессии интервью (хранится в памяти сервера)."""
    session_id: str
    interviewer: str  # "hr" или "techlead"
    vacancy_text: Optional[str] = None
    created_at: str
    question_idx: int = 1
    current_stage: int = 1  # 🆕 1: Опыт, 2: Вакансия, 3: Софт-скиллы, 4: Карьера
    messages: List[Message] = Field(default_factory=list)
    
class SessionData(BaseModel):
    """Полное состояние сессии интервью."""
    session_id: str
    interviewer: str  # "hr" или "techlead"
    vacancy_text: Optional[str] = None
    created_at: str
    question_idx: int = 1
    current_stage: int = 1  # 🆕 1: Опыт, 2: Вакансия, 3: Софт-скиллы, 4: Карьера
    messages: List[Message] = Field(default_factory=list)


class InterviewStart(BaseModel):
    """Запрос на начало интервью (приходит с фронтенда)."""
    interviewer: str = Field(..., description="Тип интервьюера: 'hr' или 'techlead'")
    vacancy_text: Optional[str] = Field(None, description="Текст вакансии (если загружен)")
    tts_enabled: bool = Field(False, description="Нужна ли озвучка")
    company_name: str = Field(..., description="Название компании, куда кандидат проходит собеседование")
    user_token: Optional[str] = None # Токен может приходить в query params или теле

class InterviewMessage(BaseModel):
    interview_id: str
    text: str

class AnswerSubmit(BaseModel):
    """Ответ кандидата на вопрос интервьюера."""
    session_id: str
    answer: str
    tts_enabled: bool = Field(False, description="Нужна ли озвучка ответа")


class InterviewResponse(BaseModel):
    """Ответ сервера после обработки действия."""
    session_id: str
    message: Message
    audio_url: Optional[str] = None
    is_finished: bool = False
    final_feedback: Optional[str] = None
