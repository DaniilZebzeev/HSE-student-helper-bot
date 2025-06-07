FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY Open_Source.py .

# Создаем директорию для данных
RUN mkdir -p data

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1

# Запускаем бота
CMD ["python", "Open_Source.py"] 