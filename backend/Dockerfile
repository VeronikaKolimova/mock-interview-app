FROM python:3.11-slim

WORKDIR /app

# Сначала обновляем pip
RUN pip install --upgrade pip

# Копируем требования
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Запускаем приложение
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
