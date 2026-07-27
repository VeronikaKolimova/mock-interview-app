from fastapi import APIRouter, HTTPException, UploadFile, File
from services.file_parser import extract_text_from_file
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/upload-vacancy")
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
