from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import tempfile

router = APIRouter()

@router.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path(tempfile.gettempdir()) / "mock_interview_tts" / filename
    if audio_path.exists():
        return FileResponse(audio_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Аудио не найдено")
