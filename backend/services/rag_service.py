"""
RAG Service для работы с вакансиями Data Scientist, ML Engineer, Data Analyst
Использует векторный поиск для нахождения релевантных вопросов-ответов из базы знаний
"""
import os
import csv
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# Пытаемся импортировать sentence-transformers для качественных эмбеддингов
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("✅ sentence-transformers доступен для качественных эмбеддингов")
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("⚠️ sentence-transformers недоступен, используется упрощённая модель эмбеддингов")


@dataclass
class QuestItem:
    """Элемент базы знаний: вопрос-ответ"""
    role: str
    question: str
    answer: str
    full_text: str


class RAGService:
    """
    RAG (Retrieval-Augmented Generation) сервис для работы с вакансиями.
    
    Этот сервис:
    1. Хранит базу знаний (вопросы-ответы по ролям) из CSV файла
    2. Создаёт эмбеддинги для семантического поиска
    3. Находит релевантные вопросы-ответы по запросу
    """
    
    def __init__(self, quests_file: str = "quests.csv"):
        """
        Инициализация RAG сервиса.
        
        Args:
            quests_file: Путь к CSV файлу с вопросами-ответами
        """
        self.model = self._load_model()
        self.knowledge_base: List[QuestItem] = []
        self.quest_embeddings = None
        
        # Загружаем вопросы из CSV
        self._load_quests(quests_file)
    
    def _load_model(self):
        """Загрузка модели для эмбеддингов."""
        # Пока отключаем тяжелую модель из-за ограничений памяти
        # Используем упрощённый поиск по ключевым словам
        logger.info("ℹ️ Используем упрощённый поиск по ключевым словам")
        return None
        
        # Если хотите использовать нейросеть, раскомментируйте код ниже:
        # if not SENTENCE_TRANSFORMERS_AVAILABLE:
        #     return None
        # try:
        #     logger.info("🔄 Загрузка модели эмбеддингов...")
        #     model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        #     logger.info("✅ Модель загружена успешно")
        #     return model
        # except Exception as e:
        #     logger.error(f"⚠️ Ошибка загрузки модели: {e}")
        #     return None
    
    def _load_quests(self, quests_file: str):
        """Загрузка вопросов-ответов из CSV файла."""
        # Пробуем разные пути к файлу
        possible_paths = [
            quests_file,
            os.path.join(os.path.dirname(__file__), quests_file),
            os.path.join(os.path.dirname(__file__), '..', quests_file),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            logger.warning(f"⚠️ Файл {quests_file} не найден. Создаём пустую базу.")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    role = row.get('role', '').strip()
                    question = row.get('question', '').strip()
                    answer = row.get('answer', '').strip()
                    
                    if role and question and answer:
                        self.knowledge_base.append(QuestItem(
                            role=role,
                            question=question,
                            answer=answer,
                            full_text=f"{role}: {question} {answer}"
                        ))
            
            logger.info(f"✅ Загружено {len(self.knowledge_base)} вопросов-ответов")
            
            # Создаём эмбеддинги для всех вопросов
            self._create_embeddings()
            
        except Exception as e:
            logger.error(f"⚠️ Ошибка загрузки CSV: {e}")
    
    def _create_embeddings(self):
        """Создание эмбеддингов для всей базы знаний."""
        if not self.knowledge_base or not self.model:
            logger.warning("⚠️ Невозможно создать эмбеддинги: нет модели или базы знаний")
            return
        
        texts = [item.full_text for item in self.knowledge_base]
        try:
            logger.info("🔄 Создание эмбеддингов для базы знаний...")
            self.quest_embeddings = self.model.encode(texts, convert_to_numpy=True)
            logger.info(f"✅ Создано {len(self.quest_embeddings)} эмбеддингов")
        except Exception as e:
            logger.error(f"⚠️ Ошибка создания эмбеддингов: {e}")
            self.quest_embeddings = None
    
    def search(self, query: str, role_filter: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """
        Семантический поиск релевантных вопросов-ответов.
        
        Args:
            query: Поисковый запрос (например, вопрос кандидата или тема)
            role_filter: Фильтр по роли (Data Scientist, ML Engineer, Data Analyst)
            top_k: Количество лучших результатов
            
        Returns:
            Список релевантных вопросов-ответов
        """
        if not self.knowledge_base:
            logger.warning("⚠️ База знаний пуста")
            return []
        
        if self.quest_embeddings is None or not self.model:
            return self._fallback_search(query, role_filter, top_k)
        
        try:
            # Создаём эмбеддинг для запроса
            query_embedding = self.model.encode([query], convert_to_numpy=True)[0]
            
            # Вычисляем косинусное сходство
            similarities = np.dot(self.quest_embeddings, query_embedding)
            
            # Применяем фильтр по роли если указан
            if role_filter:
                for i, item in enumerate(self.knowledge_base):
                    if item.role != role_filter:
                        similarities[i] = -1  # Исключаем из поиска
            
            # Находим top_k наиболее релевантных
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0:  # Только релевантные результаты
                    item = self.knowledge_base[idx]
                    results.append({
                        'role': item.role,
                        'question': item.question,
                        'answer': item.answer,
                        'relevance_score': float(similarities[idx])
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"⚠️ Ошибка поиска: {e}")
            return self._fallback_search(query, role_filter, top_k)
    
    def _fallback_search(self, query: str, role_filter: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """Резервный поиск по ключевым словам (если модель не загружена)."""
        query_lower = query.lower()
        scored_items = []
        
        for item in self.knowledge_base:
            if role_filter and item.role != role_filter:
                continue
            
            score = 0
            text = f"{item.question} {item.answer}".lower()
            
            # Простой подсчёт совпадений слов
            for word in query_lower.split():
                if len(word) > 2 and word in text:  # Уменьшили порог с 3 до 2 для лучших результатов
                    score += 1
            
            if score > 0:
                scored_items.append({
                    'role': item.role,
                    'question': item.question,
                    'answer': item.answer,
                    'relevance_score': score
                })
        
        # Сортируем по релевантности
        scored_items.sort(key=lambda x: x['relevance_score'], reverse=True)
        return scored_items[:top_k]
    
    def get_vacancy_template(self, role: str) -> str:
        """Получение шаблона вакансии по роли."""
        templates = {
            "Data Scientist": """
Требования:
- Опыт работы с Python и ML-библиотеками (scikit-learn, pandas, numpy)
- Знание алгоритмов машинного обучения (классификация, регрессия, кластеризация)
- Опыт работы с нейронными сетями (PyTorch или TensorFlow)
- Умение работать с большими данными (SQL, Spark)
- Понимание статистики и математического анализа

Обязанности:
- Разработка и обучение ML-моделей
- Анализ данных и выявление инсайтов
- Внедрение моделей в продакшен
- Мониторинг качества моделей
""",
            "ML Engineer": """
Требования:
- Опыт разработки на Python
- Знание Docker и Kubernetes
- Опыт работы с MLOps инструментами (MLflow, Airflow, Kubeflow)
- Понимание CI/CD процессов
- Опыт развёртывания моделей в продакшене

Обязанности:
- Проектирование ML-пайплайнов
- Контейнеризация и деплой моделей
- Мониторинг и логирование
- Оптимизация производительности моделей
- Автоматизация процессов обучения
""",
            "Data Analyst": """
Требования:
- Продвинутый уровень SQL
- Опыт работы с Python (pandas, matplotlib, seaborn)
- Знание инструментов визуализации (Tableau, Power BI, Looker)
- Понимание A/B тестирования и статистики
- Умение работать с большими объёмами данных

Обязанности:
- Анализ данных и построение дашбордов
- Подготовка отчётов для стейкхолдеров
- Проведение A/B тестов
- Выявление аномалий и трендов
- Формулировка рекомендаций на основе данных
"""
        }
        
        return templates.get(role, "Шаблон вакансии не найден")
    
    def add_quest(self, role: str, question: str, answer: str, save_to_file: bool = True, filename: str = "quests.csv"):
        """Добавление нового вопроса-ответа в базу."""
        new_item = QuestItem(
            role=role,
            question=question,
            answer=answer,
            full_text=f"{role}: {question} {answer}"
        )
        
        self.knowledge_base.append(new_item)
        
        # Пересоздаём эмбеддинги
        if self.model:
            self._create_embeddings()
        
        # Сохраняем в файл если нужно
        if save_to_file:
            self._save_quests_to_csv(filename)
    
    def _save_quests_to_csv(self, filename: str = "quests.csv"):
        """Сохранение базы знаний в CSV файл."""
        try:
            # Сохраняем в директорию backend
            save_path = os.path.join(os.path.dirname(__file__), '..', filename)
            
            with open(save_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['role', 'question', 'answer'])
                writer.writeheader()
                for item in self.knowledge_base:
                    writer.writerow({
                        'role': item.role,
                        'question': item.question,
                        'answer': item.answer
                    })
            logger.info(f"✅ База знаний сохранена в {save_path}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка сохранения: {e}")
    
    def get_all_roles(self) -> List[str]:
        """Получение списка всех уникальных ролей в базе."""
        roles = set(item.role for item in self.knowledge_base)
        return sorted(list(roles))
    
    def get_stats(self) -> Dict:
        """Получение статистики по базе знаний."""
        stats = {
            'total_questions': len(self.knowledge_base),
            'roles': {},
            'embeddings_ready': self.quest_embeddings is not None
        }
        
        for item in self.knowledge_base:
            if item.role not in stats['roles']:
                stats['roles'][item.role] = 0
            stats['roles'][item.role] += 1
        
        return stats


# Глобальный экземпляр сервиса
rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Получение экземпляра RAG сервиса (ленивая инициализация)."""
    global rag_service
    if rag_service is None:
        rag_service = RAGService()
    return rag_service
