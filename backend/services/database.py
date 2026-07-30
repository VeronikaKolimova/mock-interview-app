import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные из .env (работает только локально)
load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_ANON_KEY")

if not url or not key:
    raise ValueError("Supabase URL и SUPABASE_ANON_KEY не найдены в переменных окружения!")

# Инициализируем клиент
supabase: Client = create_client(url, key)

def get_supabase_client() -> Client:
    return supabase
