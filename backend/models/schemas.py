from pydantic import BaseModel, Field
from typing import List, Optional


class Message(BaseModel):
    """Одно сообщение в диалоге (от пользователя или интервьюера)."""
    role: str = Field(..., description="Роль: 'user' (кандидат) или 'assistant' (интервьюер)")
    content: str = Field(..., description="Текст сообщения")


class SessionData(BaseModel):
    """Полное состояние сессии интервью (хранится в памяти сервера)."""
    session_id: str = Field(..., description="Уникальный ID сессии")
    interviewer: str = Field(..., description="Тип интервьюера: 'hr' или 'techlead'")
    vacancy_text: Optional[str] = Field(None, description="Текст вакансии")
    company: Optional[str] = Field(None, description="🆕 ID компании, в которую проходит собеседование")
    created_at: str = Field(..., description="Время создания сессии (ISO формат)")
    question_idx: int = Field(1, description="Номер текущего вопроса")
    current_stage: int = Field(1, description="🆕 Этап: 1-Опыт, 2-Вакансия, 3-Софт-скиллы, 4-Карьера")
    messages: List[Message] = Field(default_factory=list, description="История сообщений")


class InterviewStart(BaseModel):
    """Запрос на начало интервью (приходит с фронтенда)."""
    interviewer: str = Field(..., description="Тип интервьюера: 'hr' или 'techlead'")
    vacancy_text: Optional[str] = Field(None, description="Текст вакансии (если загружен)")
    tts_enabled: bool = Field(False, description="Нужна ли озвучка")
    company: Optional[str] = Field(
        None, 
        description="🆕 ID компании ('google', 'meta', 'yandex', ...). Если None — стандартный режим"
    )
    user_token: Optional[str] = Field(None, description="Токен пользователя (может приходить в query params или теле)")


class InterviewMessage(BaseModel):
    """Сообщение в рамках интервью (для истории)."""
    interview_id: str = Field(..., description="ID интервью")
    text: str = Field(..., description="Текст сообщения")


class AnswerSubmit(BaseModel):
    """Ответ кандидата на вопрос интервьюера."""
    session_id: str = Field(..., description="ID активной сессии")
    answer: str = Field(..., description="Текст ответа кандидата")
    tts_enabled: bool = Field(False, description="Нужна ли озвучка ответа")


class InterviewResponse(BaseModel):
    """Ответ сервера после обработки действия."""
    session_id: str = Field(..., description="ID сессии")
    message: Message = Field(..., description="Сообщение от интервьюера")
    audio_url: Optional[str] = Field(None, description="URL аудио (если TTS включён)")
    is_finished: bool = Field(False, description="Завершено ли интервью")
    final_feedback: Optional[str] = Field(None, description="Итоговый фидбек (если завершено)")
