import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI
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

class SearchQuestionsRequest(BaseModel):
    query: str
    direction: Optional[str] = None
    company: Optional[str] = None
    limit: int = 5

# === ОТЛОЖЕННАЯ ЗАГРУЗКА МОДЕЛИ (LAZY LOADING) ===
# Модель не загружается при старте, экономя RAM. Она загрузится при первом запросе.
rag_model = None

def get_rag_model():
    global rag_model
    if rag_model is None:
        print("🧠 Загрузка RAG модели (отложенная загрузка для экономии RAM)...")
        # Подавляем предупреждение onnxruntime о GPU, так как на Render его нет
        os.environ["ORT_DISABLE_GPU_MEM_PATTERN"] = "1"
        rag_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        print("✅ RAG модель успешно загружена в память!")
    return rag_model
# =================================================

@app.post("/api/questions/search")
async def search_questions(request: SearchQuestionsRequest):
    try:
        # 1. Получаем или загружаем модель
        model = get_rag_model()
        
        # 2. Превращаем запрос в вектор
        embeddings = list(model.embed([request.query]))
        query_embedding = embeddings[0].tolist()
        
        # 3. Вызываем SQL-функцию в Supabase
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
            
        return {
            "query": request.query,
            "found_count": len(results),
            "questions": results
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
