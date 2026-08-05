from pydantic import BaseModel
from typing import Optional, List


class InterviewStart(BaseModel):
    """Запрос на запуск интервью"""
    interviewer: str  # "hr" или "techlead"
    vacancy_text: Optional[str] = None
    tts_enabled: bool = False
    company: Optional[str] = None  # ID компании из списка (google, yandex и т.д.) или None


class AnswerSubmit(BaseModel):
    """Запрос на отправку ответа кандидата"""
    session_id: str
    answer: str
    tts_enabled: bool = False


class Message(BaseModel):
    """Сообщение в диалоге"""
    role: str  # "user" или "assistant"
    content: str


class SessionData(BaseModel):
    """Данные сессии интервью (хранятся в памяти)"""
    session_id: str
    interviewer: str
    vacancy_text: Optional[str] = None
    company: Optional[str] = None  # 👈 ID выбранной компании
    created_at: str
    question_idx: int = 1
    messages: List[Message] = []


class InterviewResponse(BaseModel):
    """Ответ API на действия интервью"""
    session_id: str
    message: Message
    audio_url: Optional[str] = None
    is_finished: bool = False
    final_feedback: Optional[str] = None


class ResumeAdaptRequest(BaseModel):
    """Запрос на адаптацию резюме"""
    session_id: str
    resume_text: Optional[str] = None
