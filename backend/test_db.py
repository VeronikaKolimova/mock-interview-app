from services.database import get_supabase_client

try:
    client = get_supabase_client()
    print("✅ Успешно подключено к Supabase!")
    print("URL:", client.supabase_url)
except Exception as e:
    print("❌ Ошибка подключения:", e)
