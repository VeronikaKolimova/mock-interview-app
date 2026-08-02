import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from services.database import get_supabase_client
from fastembed import TextEmbedding
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Mock Interview API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = get_supabase_client()

# === ОТЛОЖЕННАЯ ЗАГРУЗКА МОДЕЛИ (LAZY LOADING) ===
rag_model = None

def get_rag_model():
    global rag_model
    if rag_model is None:
        print("🧠 Загрузка RAG модели (отложенная загрузка для экономии RAM)...")
        os.environ["ORT_DISABLE_GPU_MEM_PATTERN"] = "1"
        rag_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        print("✅ RAG модель успешно загружена в память!")
    return rag_model
# =================================================

class SearchQuestionsRequest(BaseModel):
    query: str
    direction: Optional[str] = None
    company: Optional[str] = None
    limit: int = 5

@app.post("/api/questions/search")
async def search_questions(request: SearchQuestionsRequest):
    try:
        model = get_rag_model()
        embeddings = list(model.embed([request.query]))
        query_embedding = embeddings[0].tolist()
        
        response = supabase.rpc(
            "match_questions",
            {
                "query_embedding": query_embedding,
                "match_count": request.limit,
                "filter_direction": request.direction,
                "filter_company": request.company
            }
        ).execute()
        
        results = []
        for row in response.data:
            results.append({
                "question": row["question"],
                "direction": row["direction"],
                "company": row["company"],
                "topic": row["topic"],
                "difficulty": row["difficulty"],
                "answer_hints": row["answer_hints"],
                "similarity": round(float(row["similarity"]), 4)
            })
            
        return {"query": request.query, "found_count": len(results), "questions": results}
    except Exception as e:
        return {"error": str(e)}

# =================================================
# НОВЫЙ ЭНДПОИНТ: Старт собеседования
# =================================================
@app.post("/api/interview/start")
async def start_interview(
    user_token: str = Query(..., description="Токен пользователя"),
    direction: str = Query("ML", description="Направление: ML, DS, BI, DI"),
    company: str = Query("Общий", description="Компания")
):
    try:
        print(f"🚀 Старт интервью для направления: {direction}, компания: {company}")
        model = get_rag_model()
        
        # Генерируем запрос для получения первого, самого базового вопроса по направлению
        starter_query = f"Самый важный базовый вопрос для собеседования по {direction}"
        embeddings = list(model.embed([starter_query]))
        query_embedding = embeddings[0].tolist()
        
        response = supabase.rpc(
            "match_questions",
            {
                "query_embedding": query_embedding,
                "match_count": 1, # Берем только 1 вопрос для старта
                "filter_direction": direction,
                "filter_company": company
            }
        ).execute()
        
        if response.data and len(response.data) > 0:
            first_question = response.data[0]
            return {
                "status": "success",
                "message": "Интервью успешно начато!",
                "first_question": {
                    "question": first_question["question"],
                    "topic": first_question["topic"],
                    "difficulty": first_question["difficulty"]
                }
            }
        else:
            return {
                "status": "success",
                "message": "Интервью начато, но вопросы не найдены. Расскажите о себе.",
                "first_question": None
            }
            
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}
