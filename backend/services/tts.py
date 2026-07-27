import hashlib
import tempfile
from pathlib import Path
from gtts import gTTS
import logging

logger = logging.getLogger(__name__)

VOICE_LANG = "ru"
CACHE_DIR = Path(tempfile.gettempdir()) / "mock_interview_tts"
CACHE_DIR.mkdir(exist_ok=True)

async def text_to_speech(text: str, interviewer: str) -> str:
    """Генерация аудио через gTTS."""
    text_hash = hashlib.md5(text.encode()).hexdigest()[:10]
    audio_path = CACHE_DIR / f"tts_{interviewer}_{text_hash}.mp3"
    
    # Проверяем кэш
    if audio_path.exists() and audio_path.stat().st_size > 100:
        logger.info(f"✅ Аудио найдено в кэше: {audio_path.name}")
        return str(audio_path)
    
    try:
        logger.info(f"🎤 Генерируем аудио для: {text[:50]}...")
        tts = gTTS(text=text, lang=VOICE_LANG, slow=False)
        tts.save(str(audio_path))
        logger.info(f"✅ Аудио сохранено: {audio_path.name}")
        return str(audio_path)
    except Exception as e:
        logger.error(f"⚠️ Ошибка генерации TTS: {e}")
        return ""
