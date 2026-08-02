import os
import sys

print("📥 Предварительная загрузка RAG модели для кэширования в образе Render...")
os.environ["ORT_DISABLE_GPU_MEM_PATTERN"] = "1"

from fastembed import TextEmbedding

# Эта команда скачает модель и сохранит её в кэш ~/.cache/fastembed/
# При запуске приложения модель будет браться отсюда мгновенно!
model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

print("✅ Модель успешно загружена и закэширована в образ!")
