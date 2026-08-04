"""
Пример использования RAG-сервиса для вакансий
"""
from services.rag_service import rag_service

def test_rag_search():
    """Тестирует поиск релевантных фрагментов вакансий"""
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ RAG ПО ВАКАНСИЯМ")
    print("=" * 60)
    
    # 1. Получаем требования для Data Scientist
    print("\n1️⃣ Требования для Data Scientist:")
    ds_reqs = rag_service.get_role_specific_requirements("Data Scientist")
    for section, items in ds_reqs.items():
        if items:
            print(f"   {section.upper()}:")
            for item in items[:2]:
                print(f"   - {item[:100]}...")
    
    # 2. Добавляем пользовательскую вакансию
    print("\n2️⃣ Добавляем пользовательскую вакансию ML Engineer:")
    custom_vacancy = """
    Мы ищем ML Engineer для разработки рекомендательных систем.
    
    Требования:
    - Опыт работы с Python и фреймворками глубокого обучения (PyTorch или TensorFlow)
    - Знание принципов MLOps, опыт деплоя моделей в production
    - Опыт работы с Docker, Kubernetes, CI/CD пайплайнами
    - Умение работать с большими данными (Spark, Kafka)
    - Опыт мониторинга моделей и A/B тестирования
    
    Обязанности:
    - Разработка и внедрение ML-моделей для персонализации контента
    - Оптимизация производительности существующих моделей
    - Построение ML-пайплайнов и автоматизация процессов
    - Взаимодействие с backend-разработчиками для интеграции моделей
    """
    
    chunk_ids = rag_service.add_vacancy(
        vacancy_text=custom_vacancy,
        role="ML Engineer",
        source="test_upload"
    )
    print(f"   ✅ Добавлено чанков: {len(chunk_ids)}")
    print(f"   IDs: {chunk_ids[:3]}...")
    
    # 3. Поиск релевантных фрагментов
    print("\n3️⃣ Поиск по запросу 'опыт работы с пайплайнами и деплоем':")
    results = rag_service.search_relevant_chunks(
        query="опыт работы с пайплайнами и деплоем моделей",
        role_filter="ML Engineer",
        top_k=3
    )
    
    for i, result in enumerate(results, 1):
        print(f"\n   Результат #{i} (score: {result['relevance_score']:.3f}):")
        print(f"   Роль: {result['role']}")
        print(f"   Текст: {result['chunk_text'][:150]}...")
    
    # 4. Формирование контекста для интервью
    print("\n\n4️⃣ Формирование контекста для интервью:")
    candidate_answer = "Я разрабатывал рекомендательные системы на PyTorch, использовал Docker для контейнеризации и Kubernetes для оркестрации"
    
    context = rag_service.get_context_for_interview(
        candidate_answer=candidate_answer,
        vacancy_text=custom_vacancy,
        role="ML Engineer",
        max_context_length=800
    )
    
    print(f"   Ответ кандидата: {candidate_answer[:80]}...")
    print(f"\n   Сформированный контекст из вакансии:")
    if context:
        for line in context.split('\n'):
            print(f"   {line}")
    else:
        print("   ⚠️ Контекст не найден")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    test_rag_search()
