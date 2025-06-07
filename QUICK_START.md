# ⚡ Быстрый старт - Публикация на GitHub

## 🚀 Автоматическая публикация (рекомендуется)

### Шаг 1: Создайте репозиторий на GitHub
1. Перейдите на [github.com/new](https://github.com/new)
2. Заполните:
   - **Repository name**: `student-helper-bot`
   - **Description**: `🎓 Telegram-бот для студентов с управлением дедлайнами`
   - **Public** ✅
   - **Add README** ❌ (у нас уже есть)
   - **Add .gitignore** ❌ (у нас уже есть)
   - **Add license** ❌ (у нас уже есть)
3. Нажмите **"Create repository"**

### Шаг 2: Настройте скрипт
Откройте файл `publish.sh` (Linux/macOS) или `publish.bat` (Windows) и замените:
```bash
GITHUB_USERNAME="YOUR_GITHUB_USERNAME"
```
на ваш реальный GitHub username:
```bash
GITHUB_USERNAME="your_real_username"
```

### Шаг 3: Запустите публикацию

**Linux/macOS:**
```bash
chmod +x publish.sh
./publish.sh
```

**Windows:**
```cmd
publish.bat
```

### Шаг 4: Введите данные
- **Git имя и email** (если не настроено)
- **GitHub логин** = ваш username
- **GitHub пароль** = Personal Access Token ([создать](https://github.com/settings/tokens))

---

## 🔧 Ручная публикация

Если предпочитаете ручное управление:

```bash
# 1. Инициализация
git init
git add .
git commit -m "feat: initial release of Student Helper Bot v1.0.0"

# 2. Подключение к GitHub (замените username!)
git remote add origin https://github.com/YOUR_USERNAME/student-helper-bot.git
git branch -M main

# 3. Отправка
git push -u origin main
```

---

## 🎯 После публикации

1. **Проверьте репозиторий**: все файлы загружены?
2. **Создайте релиз v1.0.0** в разделе Releases
3. **Добавьте topics**: `telegram-bot`, `python`, `student-helper`
4. **Настройте About**: описание проекта
5. **Поделитесь** ссылкой! 🚀

---

## ❓ Проблемы?

- **401 Unauthorized**: используйте Personal Access Token вместо пароля
- **404 Not Found**: проверьте правильность username в URL
- **Empty repository**: убедитесь, что репозиторий создан на GitHub
- **Git not found**: установите Git с [git-scm.com](https://git-scm.com/)

**Подробные инструкции**: [DEPLOY.md](DEPLOY.md) 