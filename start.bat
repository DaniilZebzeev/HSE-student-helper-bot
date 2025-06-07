@echo off
title Student Helper Bot

echo 🎓 Запуск Student Helper Bot...

REM Проверяем наличие Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден! Установите Python 3.8+
    pause
    exit /b 1
)

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ❌ Файл .env не найден!
    echo 📝 Скопируйте .env.example в .env и настройте переменные:
    echo    copy .env.example .env
    pause
    exit /b 1
)

REM Создаем папку data если не существует
if not exist "data" (
    echo 📁 Создаем папку data...
    mkdir data
)

REM Устанавливаем зависимости
echo 📦 Устанавливаем зависимости...
pip install -r requirements.txt

REM Запускаем бота
echo 🚀 Запускаем бота...
python Open_Source.py

pause 