"""
Тестовый скрипт для проверки работы RAG сервиса
Запустите: python test_my_rag.py
"""

from services.rag_service import get_rag_service

print("=" * 60)
print("🧪 ТЕСТ RAG СЕРВИСА")
print("=" * 60)

# Получаем сервис
rag = get_rag_service()

# Смотрим статистику
print("\n📊 СТАТИСТИКА БАЗЫ ЗНАНИЙ:")
stats = rag.get_stats()
print(f"Всего вопросов: {stats['total_questions']}")
print(f"Эмбеддинги готовы: {stats['embeddings_ready']}")
print("Вопросы по ролям:")
for role, count in stats['roles'].items():
    print(f"  - {role}: {count}")

# Тест 1: Поиск по теме "переобучение"
print("\n" + "=" * 60)
print("🔍 ТЕСТ 1: Поиск по теме 'переобучение' (Data Scientist)")
print("=" * 60)
results = rag.search("переобучение модели", role_filter="Data Scientist", top_k=2)

if results:
    for i, r in enumerate(results, 1):
        print(f"\n{i}. Вопрос: {r['question']}")
        print(f"   Ответ: {r['answer'][:100]}...")
        print(f"   Релевантность: {r['relevance_score']:.3f}")
else:
    print("❌ Ничего не найдено")

# Тест 2: Поиск по теме "Docker"
print("\n" + "=" * 60)
print("🔍 ТЕСТ 2: Поиск по теме 'Docker' (ML Engineer)")
print("=" * 60)
results = rag.search("контейнеризация Docker", role_filter="ML Engineer", top_k=2)

if results:
    for i, r in enumerate(results, 1):
        print(f"\n{i}. Вопрос: {r['question']}")
        print(f"   Ответ: {r['answer'][:100]}...")
        print(f"   Релевантность: {r['relevance_score']:.3f}")
else:
    print("❌ Ничего не найдено")

# Тест 3: Поиск по теме "SQL"
print("\n" + "=" * 60)
print("🔍 ТЕСТ 3: Поиск по теме 'SQL' (Data Analyst)")
print("=" * 60)
results = rag.search("SQL джойны таблицы", role_filter="Data Analyst", top_k=2)

if results:
    for i, r in enumerate(results, 1):
        print(f"\n{i}. Вопрос: {r['question']}")
        print(f"   Ответ: {r['answer'][:100]}...")
        print(f"   Релевантность: {r['relevance_score']:.3f}")
else:
    print("❌ Ничего не найдено")

# Тест 4: Получение шаблона вакансии
print("\n" + "=" * 60)
print("📄 ТЕСТ 4: Шаблон вакансии Data Scientist")
print("=" * 60)
template = rag.get_vacancy_template("Data Scientist")
print(template[:300] + "...")

print("\n" + "=" * 60)
print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
print("=" * 60)
