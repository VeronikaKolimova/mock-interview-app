import os
from supabase import create_client, Client

# Читаем переменные напрямую из окружения сервера
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

# --- ВРЕМЕННАЯ ОТЛАДКА ---
print("=" * 50)
print("DEBUG: Проверка переменных окружения на Render")
print(f"SUPABASE_URL существует: {bool(url)}")
print(f"SUPABASE_ANON_KEY существует: {bool(key)}")
print("Все ключи в os.environ, содержащие 'SUPABASE':")
print([k for k in os.environ.keys() if 'SUPABASE' in k])
print("=" * 50)

if not url or not key:
    raise ValueError("Supabase URL и SUPABASE_ANON_KEY не найдены в переменных окружения!")

# Инициализируем клиент
supabase: Client = create_client(url, key)

def get_supabase_client() -> Client:
    return supabase
