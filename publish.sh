#!/bin/bash

# 🚀 Автоматическая публикация Student Helper Bot на GitHub
# 
# ИНСТРУКЦИЯ ПЕРЕД ЗАПУСКОМ:
# 1. Замените YOUR_GITHUB_USERNAME на ваш реальный username
# 2. Создайте репозиторий на GitHub: https://github.com/new
#    - Repository name: student-helper-bot
#    - Description: 🎓 Telegram-бот для студентов с управлением дедлайнами
#    - Public
#    - НЕ добавляйте README, .gitignore, license (у нас уже есть)
# 3. Запустите: chmod +x publish.sh && ./publish.sh

echo "🎓 Публикация Student Helper Bot на GitHub..."

# ⚠️ ЗАМЕНИТЕ НА ВАШ GITHUB USERNAME!
GITHUB_USERNAME="DaniilZebzeev"

# Проверяем, что username заменен
if [ "$GITHUB_USERNAME" = "YOUR_GITHUB_USERNAME" ]; then
    echo "❌ Ошибка: Замените YOUR_GITHUB_USERNAME на ваш реальный GitHub username в скрипте!"
    echo "📝 Откройте файл publish.sh и измените строку 13"
    exit 1
fi

# Проверяем Git
if ! command -v git &> /dev/null; then
    echo "❌ Git не установлен! Установите Git: https://git-scm.com/"
    exit 1
fi

# Настраиваем Git (если не настроен)
if ! git config user.name > /dev/null 2>&1; then
    echo "📝 Настройка Git..."
    read -p "Введите ваше имя для Git: " GIT_NAME
    read -p "Введите ваш email для Git: " GIT_EMAIL
    git config --global user.name "$GIT_NAME"
    git config --global user.email "$GIT_EMAIL"
fi

# Инициализируем Git репозиторий
echo "🔧 Инициализация Git репозитория..."
git init

# Добавляем все файлы
echo "📁 Добавление файлов..."
git add .

# Проверяем, что .env не добавлен
if git status --porcelain | grep -q "\.env$"; then
    echo "⚠️  Внимание: файл .env будет добавлен в репозиторий!"
    echo "❌ Это небезопасно! Удалите .env файл или добавьте его в .gitignore"
    echo "Продолжить? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "❌ Отменено пользователем"
        exit 1
    fi
fi

# Создаем коммит
echo "💾 Создание первого коммита..."
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

# Переименовываем ветку в main
echo "🌿 Настройка главной ветки..."
git branch -M main

# Добавляем remote origin
echo "🔗 Подключение к GitHub..."
git remote add origin "https://github.com/${GITHUB_USERNAME}/student-helper-bot.git"

# Пушим в GitHub
echo "🚀 Отправка кода на GitHub..."
echo "📝 Если запросит логин - введите ваш GitHub username"
echo "🔑 Если запросит пароль - используйте Personal Access Token!"
echo "   Создать токен: https://github.com/settings/tokens"

if git push -u origin main; then
    echo ""
    echo "🎉 УСПЕШНО! Проект опубликован на GitHub!"
    echo ""
    echo "🔗 Ваш репозиторий: https://github.com/${GITHUB_USERNAME}/student-helper-bot"
    echo ""
    echo "📋 Следующие шаги:"
    echo "1. Перейдите в репозиторий и проверьте все файлы"
    echo "2. Создайте релиз v1.0.0 в разделе Releases"
    echo "3. Добавьте topics: telegram-bot, python, student-helper"
    echo "4. Настройте описание проекта в About"
    echo "5. Поделитесь ссылкой с друзьями! 🎯"
else
    echo ""
    echo "❌ Ошибка при отправке на GitHub!"
    echo ""
    echo "🔧 Возможные решения:"
    echo "1. Проверьте, что репозиторий создан на GitHub"
    echo "2. Убедитесь, что username правильный: ${GITHUB_USERNAME}"
    echo "3. Используйте Personal Access Token вместо пароля"
    echo "4. Проверьте интернет-соединение"
    echo ""
    echo "📖 Подробные инструкции в файле DEPLOY.md"
fi 