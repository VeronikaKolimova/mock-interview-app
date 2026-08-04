import numpy as np
from typing import List, Dict, Optional
import re

# Простая база знаний для примера (в реальности будет загружаться из CSV/DB)
VACANCY_KNOWLEDGE_BASE = {
    "Data Scientist": [
        {
            "topic": "Python & Libraries",
            "requirements": "Pandas, NumPy, Scikit-learn",
            "sample_questions": [
                "Как работает GroupBy в Pandas?",
                "В чем разница между loc и iloc?",
                "Как оптимизировать работу с большим DataFrame?"
            ]
        },
        {
            "topic": "Machine Learning",
            "requirements": "Regression, Classification, Clustering",
            "sample_questions": [
                "Объясните разницу между L1 и L2 регуляризацией.",
                "Что такое переобучение и как с ним бороться?",
                "Как работает Random Forest?"
            ]
        }
    ],
    "ML Engineer": [
        {
            "topic": "Deployment",
            "requirements": "Docker, Kubernetes, FastAPI",
            "sample_questions": [
                "Как упаковать модель в Docker?",
                "Что такое CI/CD для ML?",
                "Как масштабировать сервис предсказаний?"
            ]
        },
        {
            "topic": "MLOps",
            "requirements": "MLflow, DVC, Monitoring",
            "sample_questions": [
                "Как отслеживать версии моделей?",
                "Что такое дрифт данных?",
                "Как настроить мониторинг качества предсказаний?"
            ]
        }
    ],
    "Data Analyst": [
        {
            "topic": "SQL",
            "requirements": "Joins, Aggregations, Window Functions",
            "sample_questions": [
                "В чем разница между INNER JOIN и LEFT JOIN?",
                "Как использовать оконные функции?",
                "Как оптимизировать медленный запрос?"
            ]
        },
        {
            "topic": "Visualization",
            "requirements": "Tableau, PowerBI, Matplotlib",
            "sample_questions": [
                "Какой график лучше выбрать для временных рядов?",
                "Как показать распределение данных?",
                "Что такое dashboard best practices?"
            ]
        }
    ]
}


class RAGService:
    def __init__(self):
        self.knowledge_base = VACANCY_KNOWLEDGE_BASE
        # В будущем здесь будет загрузка векторной базы данных

    def search_context(self, query: str, role: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """
        Ищет наиболее релевантный контекст по запросу.
        Пока реализовано через простой поиск по ключевым словам.
        В будущем заменим на векторный поиск (FAISS/Chroma).
        """
        results = []
        query_lower = query.lower()

        # Если роль указана, ищем только в ней, иначе во всех
        roles_to_search = [role] if role else list(self.knowledge_base.keys())

        for r in roles_to_search:
            if r not in self.knowledge_base:
                continue

            for topic_data in self.knowledge_base[r]:
                # Проверяем вхождение слов запроса в тему или требования
                score = 0
                if any(word in topic_data["topic"].lower() for word in query_lower.split()):
                    score += 2
                if any(word in topic_data["requirements"].lower() for word in query_lower.split()):
                    score += 1

                # Проверяем вопросы
                for q in topic_data["sample_questions"]:
                    if any(word in q.lower() for word in query_lower.split()):
                        score += 3

                if score > 0:
                    results.append({
                        "role": r,
                        "topic": topic_data["topic"],
                        "requirements": topic_data["requirements"],
                        "relevance_score": score,
                        "suggested_question": topic_data["sample_questions"][0]
                    })

        # Сортировка по релевантности
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_k]


# Глобальный экземпляр
_rag_instance = None


def get_rag_service() -> RAGService:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
