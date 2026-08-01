import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# 1. Получаем значения и убираем все пробелы по краям
url = os.getenv("SUPABASE_URL", "").strip()
key = (os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY") or "").strip()

# 2. Жесткая проверка URL: оставляем только ASCII-символы (защита от русской 'с' вместо 'c')
url = url.encode('ascii', 'ignore').decode('ascii')

if not url or not key:
    raise ValueError(f"Supabase URL или Key не найдены или пусты! Проверь файл: {env_path}")

print(f"✅ База данных инициализирована. URL: {url[:20]}...")

supabase: Client = create_client(url, key)

def get_supabase_client() -> Client:
    return supabase
