import os
import httpx
from typing import List, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

# Используем бесплатный Hugging Face Inference API вместо локальной модели.
# Это спасает Render от нехватки памяти (OOM)! Модель та же самая.
HF_API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class RAGService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase: Client = create_client(url, key)

    def _embed_query(self, text: str) -> List[float]:
        """Считает эмбеддинг через внешний API, не нагружая память сервера."""
        try:
            headers = {}
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"
            
            response = httpx.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": text, "options": {"wait_for_model": True}},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # HF API может вернуть [[...]] или [...]
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], list):
                    return result[0]
                return result
            raise ValueError("Неожиданный формат ответа от HF API")
            
        except Exception as e:
            logger.error(f"Ошибка при получении эмбеддинга от HF: {e}")
            # Фоллбэк: возвращаем нулевой вектор размерности 384, чтобы не крашить всё приложение
            return [0.0] * 384

    def search_similar_questions(
        self,
        query: str,
        direction: Optional[str] = None,
        company: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """Векторный поиск похожих вопросов через Supabase RPC."""
        try:
            query_embedding = self._embed_query(query)

            result = self.supabase.rpc(
                "match_questions",
                {
                    "query_embedding": query_embedding,
                    "match_count": top_k,
                    "filter_direction": direction,
                    "filter_company": company
                }
            ).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Ошибка при поиске вопросов: {e}")
            return []

    def build_context_for_interview(
        self,
        vacancy_text: Optional[str] = None,
        direction: str = "ML",
        company: Optional[str] = None,
        top_k: int = 5
    ) -> str:
        """Возвращает готовый контекст для LLM с похожими вопросами."""
        query = vacancy_text or f"{direction} Engineer interview questions"
        similar = self.search_similar_questions(
            query=query,
            direction=direction,
            company=company,
            top_k=top_k
        )

        if not similar:
            logger.warning("RAG не нашёл похожих вопросов")
            return ""

        lines = [
            "",
            "=== Контекст: релевантные вопросы (используй как ориентир, не копируй дословно) ==="
        ]
        for i, q in enumerate(similar, 1):
            hint = q.get("answer_hints") or ""
            hint_str = f" [ключевые моменты: {hint[:150]}...]" if hint else ""
            lines.append(f"{i}. {q.get('question', '')}{hint_str}")
        lines.append("=" * 70)

        context = "\n".join(lines)
        logger.info(f"🎯 RAG: найдено {len(similar)} вопросов для направления {direction}")
        return context


_rag_instance = None


def get_rag_service() -> RAGService:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
