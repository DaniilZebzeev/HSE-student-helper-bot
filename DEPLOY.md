# 🚀 Публикация на GitHub

Пошаговая инструкция по публикации Student Helper Bot на GitHub.

## 📋 Подготовка к публикации

### 1. Проверьте структуру проекта

Убедитесь, что у вас есть все необходимые файлы:

```
student-helper-bot/
├── Open_Source.py          # ✅ Основной файл бота
├── requirements.txt        # ✅ Зависимости
├── .env.example           # ✅ Пример переменных окружения
├── .gitignore            # ✅ Исключения для Git
├── README.md             # ✅ Документация
├── LICENSE               # ✅ Лицензия MIT
├── CONTRIBUTING.md       # ✅ Руководство для участников
├── CHANGELOG.md          # ✅ История изменений
├── DEPLOY.md             # ✅ Инструкция по деплою
├── Dockerfile            # ✅ Docker конфигурация
├── docker-compose.yml    # ✅ Docker Compose
├── start.sh              # ✅ Скрипт запуска (Linux/macOS)
├── start.bat             # ✅ Скрипт запуска (Windows)
└── data/
    └── happy.json.example # ✅ Пример файла дней рождения
```

### 2. Проверьте .gitignore

Убедитесь, что чувствительные данные не попадут в репозиторий:
- `.env` файлы
- Файлы с реальными данными (`data/`)
- Логи (`bot.log`)

### 3. Настройте персональные данные

⚠️ **ОБЯЗАТЕЛЬНО** перед публикацией:

1. **Удалите реальные данные** из кода:
   - Имена и контакты администрации в `Open_Source.py`
   - Реальные номера телефонов и Telegram username
   - Специфичные ссылки на системы оплаты

2. **Обновите README.md**:
   - `your-username` → ваш GitHub username
   - `[Your Name]` → ваше имя

3. **Создайте CUSTOMIZATION.md** с инструкциями по настройке персональных данных

## 🔧 Создание репозитория

### 1. Создайте репозиторий на GitHub

1. Перейдите на [GitHub](https://github.com)
2. Нажмите "New repository"
3. Заполните данные:
   - **Repository name**: `student-helper-bot`
   - **Description**: `🎓 Telegram-бот для студентов с управлением дедлайнами`
   - **Visibility**: Public
   - **Add README**: ❌ НЕ отмечайте (у нас уже есть README)
   - **Add .gitignore**: ❌ НЕ отмечайте (у нас уже есть)
   - **Add license**: ❌ НЕ отмечайте (у нас уже есть MIT)

### 2. Инициализируйте Git репозиторий

```bash
# Инициализируем Git (если еще не сделано)
git init

# Добавляем все файлы
git add .

# Делаем первый коммит
git commit -m "feat: initial release of Student Helper Bot v1.0.0

- ✨ Add deadline management system
- 📊 Add grade calculation features  
- 🎉 Add social invitation functions
- 🎂 Add birthday notification system
- 📞 Add administration contacts
- 🐳 Add Docker support
- 📝 Add comprehensive documentation"

# Добавляем remote origin
git remote add origin https://github.com/your-username/student-helper-bot.git

# Отправляем код
git branch -M main
git push -u origin main
```

## 🏷️ Создание релиза

### 1. Создайте тег версии

```bash
git tag -a v1.0.0 -m "Release v1.0.0

🎯 Первый стабильный релиз Student Helper Bot

Основные возможности:
- 📅 Управление дедлайнами с напоминаниями
- 📊 Расчет среднего балла диплома и предметов
- 🎉 Социальные функции и приглашения
- 🎂 Автоматические поздравления с ДР
- 📞 Контакты администрации
- 🐳 Docker поддержка"

git push origin v1.0.0
```

### 2. Создайте GitHub Release

1. Перейдите в раздел "Releases" вашего репозитория
2. Нажмите "Create a new release"
3. Выберите тег `v1.0.0`
4. Заполните информацию:
   - **Release title**: `🎓 Student Helper Bot v1.0.0`
   - **Description**: Скопируйте из CHANGELOG.md

## 🎨 Настройка репозитория

### 1. Добавьте Topics

В настройках репозитория добавьте topics:
- `telegram-bot`
- `python`
- `student-helper`
- `deadline-management`
- `education`
- `scheduler`
- `telegram-api`

### 2. Настройте About

- **Description**: Telegram-бот для студентов с управлением дедлайнами, расчетом оценок и социальными функциями
- **Website**: Ссылка на демо или документацию (если есть)

### 3. Настройте ветки

- Защитите `main` ветку от прямых push'ей
- Требуйте Pull Request для изменений
- Включите автоматическое удаление веток после merge

## 📈 После публикации

### 1. Создайте GitHub Pages (опционально)

Для документации проекта можете создать GitHub Pages:

```bash
# Создайте ветку gh-pages
git checkout --orphan gh-pages
git rm -rf .
echo "# Student Helper Bot Documentation" > index.md
git add index.md
git commit -m "docs: initial GitHub Pages"
git push origin gh-pages
```

### 2. Настройте GitHub Actions (опционально)

Создайте `.github/workflows/ci.yml` для автоматической проверки кода:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Check syntax
      run: python -m py_compile Open_Source.py
```

### 3. Добавьте badges в README

Добавьте в начало README.md:

```markdown
![GitHub release](https://img.shields.io/github/v/release/your-username/student-helper-bot)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![GitHub stars](https://img.shields.io/github/stars/your-username/student-helper-bot)
```

## ✅ Чек-лист публикации

- [ ] Проверены все файлы проекта
- [ ] Обновлены персональные данные в README
- [ ] Создан GitHub репозиторий
- [ ] Отправлен код с правильными коммитами
- [ ] Создан тег и релиз v1.0.0
- [ ] Настроены topics и описание
- [ ] Добавлены badges (опционально)
- [ ] Настроены GitHub Actions (опционально)

## 🎉 Готово!

Ваш проект теперь доступен по ссылке:
`https://github.com/your-username/student-helper-bot`

Поделитесь ссылкой с друзьями и коллегами! 🚀 