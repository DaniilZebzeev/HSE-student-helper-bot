@echo off
setlocal enabledelayedexpansion
title Student Helper Bot - GitHub Publisher

echo 🎓 Публикация Student Helper Bot на GitHub...
echo.

REM ⚠️ ЗАМЕНИТЕ НА ВАШ GITHUB USERNAME!
set "GITHUB_USERNAME=DaniilZebzeev"

REM Проверяем, что username заменен
if "%GITHUB_USERNAME%" == "YOUR_GITHUB_USERNAME" (
    echo ❌ Ошибка: Замените YOUR_GITHUB_USERNAME на ваш реальный GitHub username в скрипте!
    echo 📝 Откройте файл publish.bat и измените строку 8
    pause
    exit /b 1
)

REM Проверяем Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Git не установлен! Скачайте с https://git-scm.com/
    pause
    exit /b 1
)

REM Настраиваем Git (если не настроен)
git config user.name >nul 2>&1
if %errorlevel% neq 0 (
    echo 📝 Настройка Git...
    set /p GIT_NAME="Введите ваше имя для Git: "
    set /p GIT_EMAIL="Введите ваш email для Git: "
    git config --global user.name "!GIT_NAME!"
    git config --global user.email "!GIT_EMAIL!"
)

echo 🔧 Инициализация Git репозитория...
git init

echo 📁 Добавление файлов...
git add .

REM Проверяем, что .env не добавлен
git status --porcelain | findstr "\.env$" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  Внимание: файл .env будет добавлен в репозиторий!
    echo ❌ Это небезопасно! Удалите .env файл или добавьте его в .gitignore
    set /p response="Продолжить? (y/N): "
    if /i not "!response!" == "y" (
        echo ❌ Отменено пользователем
        pause
        exit /b 1
    )
)

echo 💾 Создание первого коммита...
git commit -m "feat: initial release of Student Helper Bot v1.0.0

✨ Основные возможности:
- 📅 Управление дедлайнами с автонапоминаниями
- 📊 Расчет среднего балла диплома и предметов
- 🎉 Социальные функции и приглашения
- 🎂 Автоматические поздравления с ДР
- 📞 Контакты администрации
- 🐳 Docker поддержка
- 📝 Полная документация

🔧 Техническое:
- Python 3.8+ с python-telegram-bot
- APScheduler для задач по расписанию
- Система управления пользователями
- Защита от спама действий
- MIT лицензия"

echo 🌿 Настройка главной ветки...
git branch -M main

echo 🔗 Подключение к GitHub...
git remote add origin "https://github.com/%GITHUB_USERNAME%/student-helper-bot.git"

echo 🚀 Отправка кода на GitHub...
echo 📝 Если запросит логин - введите ваш GitHub username
echo 🔑 Если запросит пароль - используйте Personal Access Token!
echo    Создать токен: https://github.com/settings/tokens
echo.

git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo 🎉 УСПЕШНО! Проект опубликован на GitHub!
    echo.
    echo 🔗 Ваш репозиторий: https://github.com/%GITHUB_USERNAME%/student-helper-bot
    echo.
    echo 📋 Следующие шаги:
    echo 1. Перейдите в репозиторий и проверьте все файлы
    echo 2. Создайте релиз v1.0.0 в разделе Releases
    echo 3. Добавьте topics: telegram-bot, python, student-helper
    echo 4. Настройте описание проекта в About
    echo 5. Поделитесь ссылкой с друзьями! 🎯
) else (
    echo.
    echo ❌ Ошибка при отправке на GitHub!
    echo.
    echo 🔧 Возможные решения:
    echo 1. Проверьте, что репозиторий создан на GitHub
    echo 2. Убедитесь, что username правильный: %GITHUB_USERNAME%
    echo 3. Используйте Personal Access Token вместо пароля
    echo 4. Проверьте интернет-соединение
    echo.
    echo 📖 Подробные инструкции в файле DEPLOY.md
)

echo.
pause 