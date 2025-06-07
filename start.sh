#!/bin/bash

# Student Helper Bot - Скрипт запуска
# Используйте: ./start.sh

echo "🎓 Запуск Student Helper Bot..."

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден! Установите Python 3.8+"
    exit 1
fi

# Проверяем наличие pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 не найден! Установите pip"
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "📝 Скопируйте .env.example в .env и настройте переменные:"
    echo "   cp .env.example .env"
    exit 1
fi

# Создаем папку data если не существует
if [ ! -d "data" ]; then
    echo "📁 Создаем папку data..."
    mkdir -p data
fi

# Устанавливаем зависимости
echo "📦 Устанавливаем зависимости..."
pip3 install -r requirements.txt

# Запускаем бота
echo "🚀 Запускаем бота..."
python3 Open_Source.py 