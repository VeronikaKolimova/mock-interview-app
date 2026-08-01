import os
import pandas as pd
from fastembed import TextEmbedding
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Загружаем переменные окружения
load_dotenv("backend/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Не найдены SUPABASE_URL или SUPABASE_KEY в backend/.env")

print(f"✅ Подключаемся к Supabase: {SUPABASE_URL}")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Загружаем легкую модель для эмбеддингов (уже скачана, загрузится мгновенно)
print("📥 Загружаем модель эмбеддингов...")
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5") 
print("✅ Модель готова!")

# 3. Читаем CSV
csv_path = "data/all_questions.csv"
if not os.path.exists(csv_path):
    for name in ["data/ml_questions.csv", "data/ml_ds_questions.csv", "data/ml_ds_bi_questions.csv"]:
        if os.path.exists(name):
            csv_path = name
            break

print(f"📂 Читаем файл: {csv_path}")
df = pd.read_csv(csv_path)
print(f"✅ Загружено {len(df)} вопросов")

# 4. Генерируем эмбеддинги
print("🧠 Генерируем эмбеддинги для вопросов...")
questions = df['question'].tolist()

# ИСПРАВЛЕНИЕ: используем .tolist() для конвертации numpy.float32 в обычные float Python
embeddings = [embedding.tolist() for embedding in model.embed(questions)]
print(f"✅ Размерность эмбеддингов: {len(embeddings[0])} (должно быть 384)")

# 5. Загружаем в Supabase
print("📤 Загружаем данные в Supabase...")
success_count = 0
error_count = 0

for idx, row in df.iterrows():
    try:
        data = {
            "direction": str(row.get("direction", "")),
            "company": str(row.get("company", "")) if pd.notna(row.get("company")) else None,
            "topic": str(row.get("topic", "")) if pd.notna(row.get("topic")) else None,
            "difficulty": str(row.get("difficulty", "")) if pd.notna(row.get("difficulty")) else None,
            "question": str(row.get("question", "")),
            "answer_hints": str(row.get("answer_hints", "")) if pd.notna(row.get("answer_hints")) else None,
            "source": str(row.get("source", "")) if pd.notna(row.get("source")) else None,
            "embedding": embeddings[idx] # Теперь здесь список обычных float
        }
        
        result = supabase.table("interview_questions").insert(data).execute()
        success_count += 1
        
        if (idx + 1) % 20 == 0:
            print(f"  ⏳ Обработано {idx + 1}/{len(df)} вопросов...")
            
    except Exception as e:
        print(f"❌ Ошибка на строке {idx}: {e}")
        error_count += 1

print(f"\n🎉 ГОТОВО!")
print(f"✅ Успешно загружено: {success_count}")
print(f"❌ Ошибок: {error_count}")

# 6. Проверяем, что данные в базе
if success_count > 0:
    print("\n🔍 Проверяем данные в Supabase...")
    result = supabase.table("interview_questions").select("id, direction, question").limit(5).execute()
    print(f"Найдено записей в БД: {len(result.data)}")
    for r in result.data:
        print(f"  - [{r['direction']}] {r['question'][:60]}...")
