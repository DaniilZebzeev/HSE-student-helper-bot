"""
Student Helper Bot - Telegram-бот для студентов

Основной функционал:
- Управление дедлайнами (личные и общие)
- Автоматические напоминания о дедлайнах
- Расчет среднего балла
- Поздравления с днями рождения
- Социальные функции (приглашения)

Автор: Student Helper Bot Team
Лицензия: MIT
Версия: 1.0.0
"""

import logging
import json
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Set

from apscheduler.schedulers.background import BackgroundScheduler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    BotCommand,
    Chat,
    Bot
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()

################################################################################
#                            CONFIG                                            #
################################################################################

class Config:
    """Конфигурация бота"""
    
    # Получаем настройки из переменных окружения
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHAT_ID = int(os.getenv("CHAT_ID", "0"))
    ALLOWED_GROUP_ID = int(os.getenv("ALLOWED_GROUP_ID", "0"))

    # Пути к файлам
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / 'data'

    USERS_FILE = DATA_DIR / 'users.json'
    ACTIONS_FILE = DATA_DIR / 'user_actions.json'
    BIRTHDAYS_FILE = DATA_DIR / 'happy.json'

    # Настройки логирования
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls):
        """Проверяет наличие обязательных переменных окружения"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в переменных окружения")
        if cls.CHAT_ID == 0:
            raise ValueError("CHAT_ID не установлен в переменных окружения")
        if cls.ALLOWED_GROUP_ID == 0:
            raise ValueError("ALLOWED_GROUP_ID не установлен в переменных окружения")


################################################################################
#                       GLOBAL VARIABLES FOR DEADLINES                         #
################################################################################

# Изначально у нас был STICKER_ID, но мы убираем отправку стикеров.
STICKER_ID = "(NoSticker)"  # Не используем.
DEADLINES_FILE = "deadlines_data.json"

# Глобальный список дедлайнов
deadlines = []

# Группа для уведомлений общих дедлайнов
group_chat_id = None

# Список всех пользователей, которых мы знаем
known_users = set()


################################################################################
#                          DATABASE                                            #
################################################################################

class Database:
    @staticmethod
    def load_json(file_path: Path, default: Any = None) -> Any:
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Ошибка чтения {file_path}: {e}")
        return default

    @staticmethod
    def save_json(file_path: Path, data: Any) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка записи {file_path}: {e}")


################################################################################
#                          USER MANAGER                                        #
################################################################################

class UserManager:
    def __init__(self, users_file: Path):
        self.users_file = users_file
        self.users: Set[str] = set(Database.load_json(users_file, default=[]))

    def add_user(self, user_id: str):
        self.users.add(user_id)
        Database.save_json(self.users_file, list(self.users))

    def get_users(self) -> Set[str]:
        return self.users


################################################################################
#                ACTION MANAGER                                               #
################################################################################

class ActionManager:
    """ Управляет сообщениями вида "Позвать пить пиво" и т.п. """

    def __init__(self, actions_file: Path):
        self.actions_file = actions_file
        self.user_actions = Database.load_json(actions_file, default={})

    def can_perform_action(self, user_id: str, action_type: str) -> bool:
        now = datetime.now()
        last_str = self.user_actions.get(user_id, {}).get(action_type)
        if last_str:
            last_dt = datetime.fromisoformat(last_str)
            if now - last_dt < timedelta(days=7):
                return False
        return True

    def update_action_time(self, user_id: str, action_type: str):
        now_str = datetime.now().isoformat()
        if user_id not in self.user_actions:
            self.user_actions[user_id] = {}
        self.user_actions[user_id][action_type] = now_str
        Database.save_json(self.actions_file, self.user_actions)


################################################################################
#                       DEADLINES: LOAD/SAVE + FUNCTIONS                       #
################################################################################

def remove_duplicate_deadlines():
    global deadlines
    unique_deadlines = []
    seen = set()

    for d in deadlines:
        # Создаем уникальный ключ для каждого дедлайна
        key = f"{d['subject']}_{d['title']}_{d['due_date'].isoformat()}_{d['description']}"
        if key not in seen:
            seen.add(key)
            unique_deadlines.append(d)

    deadlines = unique_deadlines
    save_deadlines()
    logging.info(f"Удалено {len(deadlines) - len(unique_deadlines)} дубликатов дедлайнов")


def load_deadlines():
    global deadlines
    try:
        if os.path.exists(DEADLINES_FILE):
            with open(DEADLINES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for d in data:
                    d["due_date"] = datetime.fromisoformat(d["due_date"])
                deadlines = data
                remove_duplicate_deadlines()  # Удаляем дубликаты после загрузки
                logging.info(f"Загружено {len(deadlines)} дедлайнов из файла")
        else:
            deadlines = []
            save_deadlines()
            logging.info("Создан новый файл дедлайнов")
    except Exception as e:
        logging.error(f"Ошибка чтения файла с дедлайнами: {e}")
        deadlines = []


def save_deadlines():
    global deadlines
    data_to_save = []
    for d in deadlines:
        d_copy = dict(d)
        d_copy["due_date"] = d["due_date"].isoformat()
        data_to_save.append(d_copy)

    with open(DEADLINES_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)


################################################################################
#                      DEADLINE REMINDER JOBS (APScheduler)                   #
################################################################################

# Глобальный планировщик для дедлайнов
deadline_scheduler = BackgroundScheduler(timezone="Asia/Yekaterinburg")
deadline_scheduler.start()

async def send_deadline_notification(chat_id, due_time, days_before, deadline_data):
    """Отправляет уведомление о дедлайне"""
    try:
        from telegram import Bot
        bot = Bot(token=Config.BOT_TOKEN)
        
        # Формируем текст напоминания в зависимости от количества дней
        if days_before == 0:
            urgency_text = "📌 <b>ВНИМАНИЕ! Дедлайн наступает СЕГОДНЯ!</b>"
        elif days_before == 1:
            urgency_text = "⏰ <b>Напоминание: До дедлайна остался 1 день!</b>"
        elif days_before == 3:
            urgency_text = "⏰ <b>Напоминание: До дедлайна осталось 3 дня!</b>"
        elif days_before == 5:
            urgency_text = "⏰ <b>Напоминание: До дедлайна осталось 5 дней!</b>"
        else:
            urgency_text = f"⏰ <b>Напоминание: До дедлайна осталось {days_before} дней!</b>"
        
        msg_text = (
            f"{urgency_text}\n\n"
            f"📕 Предмет: {deadline_data['subject']}\n"
            f"📝 Задание: {deadline_data['title']}\n"
            f"📅 Дата дедлайна: {due_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"💬 Описание: {deadline_data['description']}\n"
        )
        
        # Если дедлайн личный, отправляем только создателю
        if deadline_data["is_private"]:
            try:
                await bot.send_message(
                    chat_id=deadline_data["created_by_id"],
                    text=f"🔒 <b>Личный дедлайн</b>\n{msg_text}",
                    parse_mode='HTML'
                )
                logging.info(f"Отправлено личное напоминание пользователю {deadline_data['created_by_id']} о дедлайне ID={deadline_data['deadline_id']}")
            except Exception as e:
                logging.error(f"Ошибка отправки личного напоминания пользователю {deadline_data['created_by_id']}: {e}")
        
        # Если дедлайн общий, отправляем в группу и всем пользователям
        else:
            # Добавляем информацию об авторе для общих дедлайнов
            author_mention = f"<a href=\"tg://user?id={deadline_data['created_by_id']}\">{deadline_data['author_name']}</a>"
            msg_text += f"👤 Автор: {author_mention}"
            
            # Отправляем в основную группу
            global group_chat_id
            target_chat_id = group_chat_id if group_chat_id else Config.CHAT_ID
            
            try:
                await bot.send_message(
                    chat_id=target_chat_id,
                    text=msg_text,
                    parse_mode='HTML'
                )
                logging.info(f"Отправлено напоминание в группу о дедлайне ID={deadline_data['deadline_id']} (за {days_before} дней)")
            except Exception as e:
                logging.error(f"Ошибка отправки напоминания в группу: {e}")
            
            # Отправляем всем пользователям в личку
            for user_id in known_users:
                try:
                    personal_msg = f"📢 <b>Общий дедлайн</b>\n{msg_text}"
                    await bot.send_message(
                        chat_id=user_id,
                        text=personal_msg,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить напоминание пользователю {user_id}: {e}")
        
    except Exception as e:
        logging.error(f"Ошибка в send_deadline_notification: {e}")


def schedule_deadline_reminders(deadline_data: dict, context=None) -> None:
    """Создает отложенные задачи для напоминаний о дедлайне за 0, 1, 3, 5 дней"""
    try:
        due_time = deadline_data["due_date"]
        deadline_id = deadline_data["deadline_id"]
        chat_id = deadline_data.get("created_in_chat", Config.CHAT_ID)
        
        # Список смещений: 0, 1, 3, 5 дней до дедлайна
        offsets = [0, 1, 3, 5]
        now = datetime.now()
        
        for days_before in offsets:
            run_time = due_time - timedelta(days=days_before)
            
            # Создаем задачу только если время еще не прошло
            if run_time > now:
                job_id = f"deadline_{deadline_id}_{days_before}days"
                
                # Добавляем задачу в планировщик
                deadline_scheduler.add_job(
                    func=lambda c=chat_id, dt=due_time, db=days_before, dd=deadline_data: asyncio.run(
                        send_deadline_notification(c, dt, db, dd)
                    ),
                    trigger='date',
                    run_date=run_time,
                    id=job_id,
                    replace_existing=True  # Заменяем если уже существует
                )
                
                logging.info(f"Запланировано напоминание для дедлайна ID={deadline_id} за {days_before} дней на {run_time}")
        
    except Exception as e:
        logging.error(f"Ошибка при планировании напоминаний для дедлайна: {e}")


def cancel_deadline_reminders(deadline_id: int, context=None) -> None:
    """Отменяет все запланированные напоминания для дедлайна"""
    try:
        # Получаем список всех задач
        jobs = deadline_scheduler.get_jobs()
        
        # Ищем и отменяем все задачи для данного дедлайна
        jobs_to_remove = []
        for job in jobs:
            if job.id and job.id.startswith(f"deadline_{deadline_id}_"):
                jobs_to_remove.append(job.id)
        
        for job_id in jobs_to_remove:
            try:
                deadline_scheduler.remove_job(job_id)
                logging.info(f"Отменено напоминание: {job_id}")
            except Exception as e:
                logging.warning(f"Ошибка при отмене задачи {job_id}: {e}")
        
        logging.info(f"Отменены все напоминания для дедлайна ID={deadline_id}")
        
    except Exception as e:
        logging.error(f"Ошибка при отмене напоминаний для дедлайна {deadline_id}: {e}")


def restore_deadline_reminders(context=None) -> None:
    """Восстанавливает запланированные напоминания для всех активных дедлайнов при запуске бота"""
    try:
        now = datetime.now()
        restored_count = 0
        
        for deadline in deadlines:
            # Проверяем только будущие дедлайны
            if deadline["due_date"] > now:
                schedule_deadline_reminders(deadline)
                restored_count += 1
        
        logging.info(f"Восстановлено напоминаний для {restored_count} активных дедлайнов")
        
    except Exception as e:
        logging.error(f"Ошибка при восстановлении напоминаний дедлайнов: {e}")


# Функция для совместимости с предыдущими тестами
async def callback_deadline_reminder(context) -> None:
    """Callback функция для совместимости с тестами"""
    try:
        data = context.job.context
        chat_id = data.get("chat_id", Config.CHAT_ID)
        due_time = datetime.fromisoformat(data["due_date_str"]) if isinstance(data["due_date_str"], str) else data.get("due_time", datetime.now())
        days_before = data["days_before"]
        
        await send_deadline_notification(chat_id, due_time, days_before, data)
        
    except Exception as e:
        logging.error(f"Ошибка в callback_deadline_reminder: {e}")


################################################################################
#                         BIRTHDAYS FUNCTIONS                                  #
################################################################################

def convert_excel_to_json(excel_path, json_path):
    """Конвертирует файл Excel с днями рождения в JSON формат"""
    logging.error("Функция конвертации Excel в JSON недоступна. Pandas не установлен.")
    logging.info("Используйте готовый JSON-файл с данными о днях рождения.")
    return False

def load_birthdays():
    """Загружает данные о днях рождения из JSON-файла"""
    try:
        if os.path.exists(Config.BIRTHDAYS_FILE):
            # Читаем JSON-файл
            with open(Config.BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
                birthdays_data = json.load(f)
            
            # Преобразуем даты в формат datetime
            birthdays = []
            for person in birthdays_data:
                try:
                    # Проверяем, что дата рождения задана корректно
                    if 'дата рождения' in person and person['дата рождения']:
                        # Пока храним дату как есть, преобразование будет в check_birthdays
                        birthdays.append(person)
                    else:
                        logging.warning(f"Пропущена запись без даты рождения: {person}")
                except Exception as e:
                    logging.error(f"Ошибка обработки записи дня рождения: {e}")
            
            logging.info(f"Загружено {len(birthdays)} записей о днях рождения из JSON")
            return birthdays
        else:
            # Попробуем конвертировать из Excel, если существует файл Excel
            excel_path = str(Config.BIRTHDAYS_FILE).replace('.json', '.xlsx')
            if os.path.exists(excel_path):
                logging.info(f"Пытаемся конвертировать данные из Excel в JSON: {excel_path}")
                if convert_excel_to_json(excel_path, Config.BIRTHDAYS_FILE):
                    # Если конвертация успешна, рекурсивно вызываем функцию для загрузки данных
                    return load_birthdays()
            
            logging.warning(f"Файл с днями рождения не найден: {Config.BIRTHDAYS_FILE}")
            return []
    except Exception as e:
        logging.error(f"Ошибка загрузки данных о днях рождения: {e}")
        return []

async def check_birthdays(bot):
    """Проверяет, есть ли сегодня дни рождения, и отправляет поздравления"""
    try:
        birthdays = load_birthdays()
        today = datetime.now().date()
        
        logging.info(f"Проверка дней рождения на {today.strftime('%Y-%m-%d')}, загружено {len(birthdays)} записей")
        birthdays_today = []
        
        for person in birthdays:
            try:
                # Получаем дату рождения из записи
                birthday_date = person.get('дата рождения')
                
                # Проверяем, можно ли определить день и месяц
                day = None
                month = None
                
                # Если это строка, пытаемся разобрать по разным форматам
                if isinstance(birthday_date, str):
                    # Стандартные форматы дат
                    date_formats = [
                        '%Y-%m-%dT%H:%M:%S.%f', 
                        '%Y-%m-%d', 
                        '%d.%m.%Y'
                    ]
                    parsed_date = None
                    
                    # Пробуем стандартные форматы
                    for date_format in date_formats:
                        try:
                            parsed_date = datetime.strptime(birthday_date, date_format)
                            day = parsed_date.day
                            month = parsed_date.month
                            break
                        except ValueError:
                            continue
                    
                    # Если стандартные форматы не сработали, проверяем специальные форматы
                    if not parsed_date:
                        # Проверяем формат "DD месяц" (например, "27 октября")
                        import re
                        month_names = {
                            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
                        }
                        
                        match = re.match(r'(\d+)\s+(\w+)', birthday_date)
                        if match:
                            day_str, month_str = match.groups()
                            month_str = month_str.lower()
                            
                            if month_str in month_names:
                                day = int(day_str)
                                month = month_names[month_str]
                                logging.info(f"Разобрана дата в формате 'день месяц': {day_str} {month_str} -> {day}.{month}")
                
                # Если это объект с методом date()
                elif hasattr(birthday_date, 'date'):
                    date_obj = birthday_date.date()
                    day = date_obj.day
                    month = date_obj.month
                # Если это datetime
                elif isinstance(birthday_date, datetime):
                    day = birthday_date.day
                    month = birthday_date.month
                
                # Если удалось определить день и месяц
                if day and month:
                    # Проверяем, совпадает ли день и месяц с сегодняшним днем
                    if today.month == month and today.day == day:
                        # Формируем имя и фамилию
                        first_name = person.get('имя', '')
                        last_name = person.get('фамилия', '')
                        full_name = f"{last_name} {first_name}".strip()
                        
                        if full_name:
                            birthdays_today.append(full_name)
                            logging.info(f"Сегодня день рождения у {full_name}")
                else:
                    logging.debug(f"Не удалось определить день и месяц для записи: {person}")
            except Exception as e:
                logging.error(f"Ошибка при проверке дня рождения для записи {person}: {e}")
                import traceback
                logging.error(traceback.format_exc())
        
        # Отправляем поздравления, если есть именинники
        if birthdays_today:
            # Если много именинников, формируем список
            if len(birthdays_today) > 1:
                names_list = "\n- ".join(birthdays_today)
                message = (
                    f"🎂 <b>Поздравляем с Днем Рождения!</b> 🎉\n\n"
                    f"Сегодня свой день рождения празднуют:\n- {names_list}\n\n"
                    f"Желаем крепкого здоровья, успехов в учебе и всего самого наилучшего! 🎁🥳"
                )
            else:
                # Один именинник
                message = (
                    f"🎂 <b>Поздравляем с Днем Рождения!</b> 🎉\n\n"
                    f"Сегодня свой день рождения празднует <b>{birthdays_today[0]}</b>!\n\n"
                    f"Желаем крепкого здоровья, успехов в учебе и всего самого наилучшего! 🎁🥳"
                )
            
            global group_chat_id
            target_chat_id = group_chat_id if group_chat_id else Config.CHAT_ID
            
            try:
                await bot.send_message(
                    chat_id=target_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
                logging.info(f"Отправлено поздравление с днем рождения {len(birthdays_today)} людям")
            except Exception as e:
                logging.error(f"Ошибка при отправке поздравления: {e}")
        else:
            logging.info("Сегодня нет дней рождения")
                
    except Exception as e:
        logging.error(f"Ошибка в модуле проверки дней рождения: {e}")


################################################################################
#               CALLBACK HANDLERS (CONTACTS)                                  #
################################################################################

class CallbackHandlers:
    @staticmethod
    async def contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data

        contacts = {
            'contact_1': (
                "📌 <b>Учебная часть</b>:\n"
                "👩‍💼 Ответственная: <b>[Имя администратора]</b>\n"
                "📞 Тел: +7 XXX XXX-XX-XX доб. XXXX\n"
                "💬 Telegram: @your_admin_username\n"
                "📍 [Ваш город], [адрес], каб.[номер]\n"
                "⏰ 09:30 - 18:00"
            ),
            'contact_2': (
                "👩‍💼 <b>Руководитель программы</b>:\n"
                "👩‍🏫 <b>[Имя руководителя]</b>\n"
                "📞 +7 XXX XXX-XX-XX доб.XXXX\n"
                "💬 Telegram: @your_manager_username\n"
                "📱 +7 XXX XXX XX XX"
            )
        }

        if data in contacts:
            text = contacts[data]
            # Добавляем кнопку "Назад" для обоих типов контактов
            kb = [[InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]]
            await query.edit_message_text(
                text=text, 
                parse_mode='HTML', 
                reply_markup=InlineKeyboardMarkup(kb)
            )
        elif data == 'main_menu':
            await query.edit_message_text("Выберите нужный раздел внизу экрана.")

    @staticmethod
    async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data

        # Обработка кнопок вызова действий
        action_mapping = {
            'call_beer': 'beer',
            'call_board_games': 'board_games',
            'call_cinema': 'cinema',
            'call_walk': 'walk'
        }

        if data in action_mapping:
            action_type = action_mapping[data]
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=query.message.message_id
            )
            
            # Получаем экземпляр CommandHandlers из bot_data
            cmd_handlers = context.application.bot_data['command_handlers']
            
            # Вызываем метод у экземпляра
            await cmd_handlers._call_action(update, context, action_type)
            return

        # Обработка кнопки оплаты обучения
        if data == "pay_education":
            payment_url = "https://your-payment-system.com/payment"
            await query.edit_message_text(
                f"💳 <b>Оплата обучения</b>\n\n"
                f"Для оплаты обучения перейдите по ссылке:\n"
                f"<a href='{payment_url}'>Оплатить обучение</a>",
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            return

        # Остальные обработчики без изменений
        if data == "calc_diploma":
            context.user_data['state'] = 'diploma_average'
            if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
                await query.message.reply_text(
                    "📊 <b>Расчет среднего балла диплома</b>\n"
                    "Введите оценки через пробел (от 1 до 10).\n"
                    "Пример: 8 9 7.5 8.5 9",
                    parse_mode='HTML'
                )
            else:
                await query.message.reply_text(
                    "Введите оценки для <b>диплома</b> (через пробел).",
                    parse_mode='HTML'
                )

        elif data == "calc_subject":
            context.user_data['state'] = 'subject_average'
            if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
                await query.message.reply_text(
                    "📊 <b>Расчет среднего балла предмета</b>\n"
                    "Введите оценки через пробел (от 1 до 10).\n"
                    "Пример: 8 9 7.5 8.5 9",
                    parse_mode='HTML'
                )
            else:
                await query.message.reply_text(
                    "Введите оценки для <b>предмета</b> (через пробел).",
                    parse_mode='HTML'
                )

        elif data == "contacts":
            kb = [
                [InlineKeyboardButton("Учебная часть", callback_data='contact_1'),
                 InlineKeyboardButton("Руководитель", callback_data='contact_2')],
                [InlineKeyboardButton("Назад", callback_data='main_menu')]
            ]
            await query.edit_message_text(
                "Выберите контакт:",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data == "deadlines":
            kb = [
                [InlineKeyboardButton("➕ Добавить", callback_data="deadline_add"),
                 InlineKeyboardButton("📋 Актуальные", callback_data="deadline_list_actual")],
                [InlineKeyboardButton("📋 Устаревшие", callback_data="deadline_list_expired"),
                 InlineKeyboardButton("❌ Удалить", callback_data="deadline_remove")],
                [InlineKeyboardButton("📢 Установить группу", callback_data="deadline_group"),
                 InlineKeyboardButton("❓ Помощь", callback_data="deadline_help")]
            ]
            await query.edit_message_text(
                "🗓 <b>Меню дедлайнов</b>\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='HTML'
            )


################################################################################
#                KEYBOARDS                                                    #
################################################################################

class Keyboards:
    @staticmethod
    def get_main_keyboard() -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("🎓 Средний балл диплома")],
            [KeyboardButton("📞 Контакты администрации")],
            [KeyboardButton("📚 Балл по предмету")],
            [KeyboardButton("🍺 Позвать пить пиво"), KeyboardButton("🎲 Позвать в настолки")],
            [KeyboardButton("🎥 Позвать в кино"), KeyboardButton("🚶 Позвать гулять")],
            [KeyboardButton("🗓 Дедлайны"), KeyboardButton("💳 Оплатить учебу")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


################################################################################
#        STATES FOR ADDING OR REMOVING DEADLINE (STEP-BY-STEP)                #
################################################################################

ADD_DEADLINE_FLOW = {
    'IS_PRIVATE': 1,
    'SUBJECT': 2,
    'TITLE': 3,
    'DATE': 4,
    'COMMENT': 5,
    'DONE': 6
}

REMOVE_DEADLINE_FLOW = {
    'ASK_ID': 1,
    'DONE': 2
}


################################################################################
#                 INLINE CALLBACK FOR DEADLINE MENU                           #
################################################################################

async def deadline_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "deadline_add":
        context.user_data['deadline_flow'] = {}
        context.user_data['deadline_flow_step'] = ADD_DEADLINE_FLOW['IS_PRIVATE']
        await query.edit_message_text("Хотите добавить ЛИЧНЫЙ (введите 'Личный') или ОБЩИЙ (введите 'Общий') дедлайн?")

    elif data in ["deadline_list", "deadline_list_actual", "deadline_list_expired"]:
        user_id = query.from_user.id
        if not deadlines:
            msg = "Пока нет ни одного дедлайна!"
            await query.edit_message_text(msg, parse_mode='HTML')
            return
            
        # Определяем текущую дату для сравнения
        current_date = datetime.now()
        
        # Фильтруем дедлайны в зависимости от типа запроса
        filtered_deadlines = []
        is_expired_list = (data == "deadline_list_expired")
        list_title = "устаревших" if is_expired_list else "актуальных"
        
        for d in deadlines:
            # Пропускаем личные дедлайны других пользователей
            if d["is_private"] and d["created_by_id"] != user_id:
                continue
                
            # Определяем, истек ли срок дедлайна
            is_expired = d["due_date"] < current_date
            
            # Добавляем дедлайн в список, если он соответствует запрошенному типу
            if (is_expired and is_expired_list) or (not is_expired and not is_expired_list):
                filtered_deadlines.append(d)
        
        if not filtered_deadlines:
            msg = f"Нет {list_title} дедлайнов для просмотра."
            await query.edit_message_text(msg, parse_mode='HTML')
            return
            
        # Формируем сообщение с заголовком
        msg = f"📋 <b>Список {list_title} дедлайнов</b>:\n\n"
        
        # Добавляем кнопку Назад
        kb = [[InlineKeyboardButton("🔙 Назад", callback_data="deadlines")]]
        
        # Отправляем первое сообщение с заголовком
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))
        
        # Отправляем каждый дедлайн отдельным сообщением
        for d in filtered_deadlines:
            try:
                date_str = d["due_date"].strftime("%Y-%m-%d %H:%M")
                try:
                    author_name = d.get('author_name', 'Неизвестный')
                    author_mention = f"<a href=\"tg://user?id={d['created_by_id']}\">{author_name}</a>"
                except:
                    author_mention = "Неизвестный"
                
                deadline_msg = (
                    f"📌 <b>ID: {d['deadline_id']}</b>\n"
                    f"📕 Предмет: {d['subject']}\n"
                    f"📝 Задание: {d['title']}\n"
                    f"📅 Дата: {date_str}\n"
                    f"💬 Описание: {d['description']}\n"
                    f"🔒 Личный: {'Да' if d['is_private'] else 'Нет'}\n"
                    f"👤 Автор: {author_mention}"
                )
                
                # Отправляем отдельное сообщение для каждого дедлайна
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=deadline_msg,
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке дедлайна: {e}")
                # Продолжаем с другими дедлайнами в случае ошибки

    elif data == "deadline_group":
        await query.edit_message_text("Установить группу: /set_group (в группе)")

    elif data == "deadline_help":
        await query.edit_message_text("Воспользуйтесь командой /help")

    elif data == "deadline_remove":
        context.user_data['remove_flow_step'] = REMOVE_DEADLINE_FLOW['ASK_ID']
        await query.edit_message_text("Введите ID дедлайна, который хотите удалить.")

    else:
        await query.edit_message_text("Неизвестная команда")


################################################################################
#          MAIN COMMAND HANDLERS CLASS (START / MENU / ETC.)                  #
################################################################################

class CommandHandlers:
    def __init__(self, user_manager, action_manager):
        self.user_manager = user_manager
        self.action_manager = action_manager

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)
        self.user_manager.add_user(user_id)
        known_users.add(update.effective_user.id)

        txt = (
            "👋 <b>Привет!</b> Я бот с функционалом дедлайнов и кнопок!\n\n"
            "📝 <b>Основные команды</b>:\n"
            "/menu - Открыть главное меню с кнопками\n"
            "/help - Справка по всем командам\n"
            "/add_deadline - Добавить дедлайн\n"
            "/list_deadlines - Список дедлайнов\n\n"
            "❗️ Нажмите /menu чтобы открыть меню с кнопками"
        )

        # Отправляем приветственное сообщение без inline-кнопок
        await update.message.reply_text(
            txt,
            parse_mode='HTML',
            reply_markup=None  # Убираем любую клавиатуру
        )

    async def handle_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        txt = update.message.text.strip()

        # Если это первое открытие меню, показываем базовые кнопки
        if txt == "/menu":
            kb = [
                [InlineKeyboardButton("🎓 Средний балл диплома", callback_data="calc_diploma"),
                 InlineKeyboardButton("📚 Балл по предмету", callback_data="calc_subject")],
                [InlineKeyboardButton("📞 Контакты", callback_data="contacts"),
                 InlineKeyboardButton("🗓 Дедлайны", callback_data="deadlines")],
                [InlineKeyboardButton("🍺 Позвать пить пиво", callback_data="call_beer"),
                 InlineKeyboardButton("🎲 Позвать в настолки", callback_data="call_board_games")],
                [InlineKeyboardButton("🎥 Позвать в кино", callback_data="call_cinema"),
                 InlineKeyboardButton("🚶 Позвать гулять", callback_data="call_walk")],
                [InlineKeyboardButton("💳 Оплатить учебу", callback_data="pay_education")]
            ]
            await update.message.reply_text(
                "🔸 <b>Главное меню</b>\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='HTML'
            )
            return

        # Проверяем, что сообщение из разрешенной группы или личных сообщений
        if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            if update.effective_chat.id != Config.ALLOWED_GROUP_ID:
                await update.message.reply_text("❌ Бот работает только в определенной группе!")
                return

        # Остальная логика обработки меню...
        if txt == "🎓 Средний балл диплома":
            context.user_data['state'] = 'diploma_average'  # Устанавливаем состояние
            if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
                await update.message.reply_text(
                    "📊 <b>Расчет среднего балла диплома</b>\n"
                    "Введите оценки через пробел (от 1 до 10).\n"
                    "Пример: 8 9 7.5 8.5 9",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    "Введите оценки для <b>диплома</b> (через пробел).",
                    parse_mode='HTML'
                )
        elif txt == "📚 Балл по предмету":
            context.user_data['state'] = 'subject_average'  # Устанавливаем состояние
            if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
                await update.message.reply_text(
                    "📊 <b>Расчет среднего балла предмета</b>\n"
                    "Введите оценки через пробел (от 1 до 10).\n"
                    "Пример: 8 9 7.5 8.5 9",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    "Введите оценки для <b>предмета</b> (через пробел).",
                    parse_mode='HTML'
                )
        elif txt == "📞 Контакты администрации":
            kb = [
                [InlineKeyboardButton("Учебная часть", callback_data='contact_1'),
                 InlineKeyboardButton("Руководитель", callback_data='contact_2')],
                [InlineKeyboardButton("Назад", callback_data='main_menu')]
            ]
            await update.message.reply_text("Выберите контакт:", reply_markup=InlineKeyboardMarkup(kb))
        elif txt in ["🍺 Позвать пить пиво", "🎲 Позвать в настолки", "🎥 Позвать в кино", "🚶 Позвать гулять"]:
            mapping = {
                "🍺 Позвать пить пиво": "beer",
                "🎲 Позвать в настолки": "board_games",
                "🎥 Позвать в кино": "cinema",
                "🚶 Позвать гулять": "walk"
            }
            action_type = mapping.get(txt)
            await self._call_action(update, context, action_type)
        elif txt == "🗓 Дедлайны":
            kb = [
                [InlineKeyboardButton("➕ Добавить", callback_data="deadline_add"),
                 InlineKeyboardButton("📋 Актуальные", callback_data="deadline_list_actual")],
                [InlineKeyboardButton("📋 Устаревшие", callback_data="deadline_list_expired"),
                 InlineKeyboardButton("❌ Удалить", callback_data="deadline_remove")],
                [InlineKeyboardButton("📢 Установить группу", callback_data="deadline_group"),
                 InlineKeyboardButton("❓ Помощь", callback_data="deadline_help")]
            ]
            await update.message.reply_text(
                "🗓 <b>Меню дедлайнов</b>\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='HTML'
            )
        elif txt == "💳 Оплатить учебу":
            payment_url = "https://your-payment-system.com/payment"
            await update.message.reply_text(
                f"💳 <b>Оплата обучения</b>\n\n"
                f"Для оплаты обучения перейдите по ссылке:\n"
                f"<a href='{payment_url}'>Оплатить обучение</a>",
                parse_mode='HTML',
                disable_web_page_preview=False
            )

    async def diploma_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data['state'] = 'diploma_average'
        if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            await update.message.reply_text(
                "📊 <b>Расчет среднего балла диплома</b>\n"
                "Введите оценки через пробел (от 1 до 10).\n"
                "Пример: 8 9 7.5 8.5 9",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "Введите оценки для <b>диплома</b> (через пробел).",
                parse_mode='HTML'
            )

    async def subject_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data['state'] = 'subject_average'
        if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            await update.message.reply_text(
                "📊 <b>Расчет среднего балла предмета</b>\n"
                "Введите оценки через пробел (от 1 до 10).\n"
                "Пример: 8 9 7.5 8.5 9",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "Введите оценки для <b>предмета</b> (через пробел).",
                parse_mode='HTML'
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = context.user_data.get('state')
        
        # Проверяем, что update.message не None перед доступом к text
        if not update.message:
            return
            
        txt = update.message.text.strip()

        if update.effective_user:
            known_users.add(update.effective_user.id)

        flow_step = context.user_data.get('deadline_flow_step')
        remove_flow_step = context.user_data.get('remove_flow_step')

        # Проверяем, что сообщение из разрешенной группы или личных сообщений
        if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            if update.effective_chat.id != Config.ALLOWED_GROUP_ID:
                await update.message.reply_text("❌ Бот работает только в определенной группе!")
                return

        if flow_step:
            await self._deadline_flow_handler(update, context, txt)
            return
        elif remove_flow_step:
            await self._deadline_remove_handler(update, context, txt)
            return
        elif state == 'diploma_average':
            await self._calc_average(update, context, txt, is_diploma=True)
        elif state == 'subject_average':
            await self._calc_average(update, context, txt, is_diploma=False)
        elif update.message and update.message.text:  # Добавляем проверку на текстовое сообщение
            # Проверяем, является ли сообщение командой меню
            menu_commands = {
                "🎓 Средний балл диплома",
                "📚 Балл по предмету",
                "📞 Контакты администрации",
                "🗓 Дедлайны",
                "🍺 Позвать пить пиво",
                "🎲 Позвать в настолки",
                "🎥 Позвать в кино",
                "🚶 Позвать гулять"
            }
            if txt in menu_commands:
                await self.handle_menu(update, context)
            elif update.effective_chat.type == Chat.PRIVATE:
                # Отвечаем на непонятные сообщения только в личке
                await update.message.reply_text("❓ Не понял команду. Воспользуйтесь меню.")

    async def _deadline_flow_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, txt: str) -> None:
        step = context.user_data['deadline_flow_step']
        flow_data = context.user_data.setdefault('deadline_flow', {})

        if step == ADD_DEADLINE_FLOW['IS_PRIVATE']:
            txt_lower = txt.lower()
            if 'личн' in txt_lower:
                flow_data['is_private'] = True
                await update.message.reply_text("Ок, создаём ЛИЧНЫЙ дедлайн. Введите <b>предмет</b>.",
                                                parse_mode='HTML')
                context.user_data['deadline_flow_step'] = ADD_DEADLINE_FLOW['SUBJECT']
            elif 'общ' in txt_lower:
                flow_data['is_private'] = False
                await update.message.reply_text("Ок, создаём ОБЩИЙ дедлайн. Введите <b>предмет</b>.", parse_mode='HTML')
                context.user_data['deadline_flow_step'] = ADD_DEADLINE_FLOW['SUBJECT']
            else:
                await update.message.reply_text("Не понял. Введите 'Личный' или 'Общий'.")

        elif step == ADD_DEADLINE_FLOW['SUBJECT']:
            flow_data['subject'] = txt
            await update.message.reply_text("Отлично! Теперь введите <b>название задания</b>.", parse_mode='HTML')
            context.user_data['deadline_flow_step'] = ADD_DEADLINE_FLOW['TITLE']

        elif step == ADD_DEADLINE_FLOW['TITLE']:
            flow_data['title'] = txt
            await update.message.reply_text("Отлично! Теперь введите <b>дату дедлайна</b> (формат YYYY-MM-DD HH:mm).",
                                            parse_mode='HTML')
            context.user_data['deadline_flow_step'] = ADD_DEADLINE_FLOW['DATE']

        elif step == ADD_DEADLINE_FLOW['DATE']:
            try:
                date_test = datetime.strptime(txt, "%Y-%m-%d %H:%M")
                if date_test.date() < datetime.now().date():
                    await update.message.reply_text("❌ Дата уже прошла! Введите будущую дату (YYYY-MM-DD HH:mm).")
                else:
                    flow_data['due_date_str'] = txt
                    await update.message.reply_text("Хорошо! Теперь введите <b>комментарий/описание</b>.",
                                                    parse_mode='HTML')
                    context.user_data['deadline_flow_step'] = ADD_DEADLINE_FLOW['COMMENT']
            except ValueError:
                await update.message.reply_text("Неверный формат даты. Попробуйте ещё раз (YYYY-MM-DD HH:mm).")

        elif step == ADD_DEADLINE_FLOW['COMMENT']:
            flow_data['description'] = txt

            global deadlines
            is_private = flow_data['is_private']
            subject = flow_data['subject']
            title = flow_data['title']
            due_date_str = flow_data['due_date_str']
            description = flow_data['description']

            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
                new_deadline_id = len(deadlines) + 1
                created_by_id = update.effective_user.id
                created_in_chat = update.effective_chat.id
                author_mention = f'<a href="tg://user?id={created_by_id}">{update.effective_user.full_name}</a>'

                new_deadline = {
                    "deadline_id": new_deadline_id,
                    "title": title,
                    "subject": subject,
                    "description": description,
                    "due_date": due_date,
                    "is_private": is_private,
                    "created_by_id": created_by_id,
                    "created_in_chat": created_in_chat,
                    "author_name": update.effective_user.full_name  # Сохраняем имя автора
                }

                deadlines.append(new_deadline)
                save_deadlines()

                # Планируем напоминания для нового дедлайна
                schedule_deadline_reminders(new_deadline)

                visibility_emo = "(Личный)" if is_private else "(Общий)"
                msg = (
                    f"✅ <b>Дедлайн добавлен!</b>\n"
                    f"ID: {new_deadline_id}\n"
                    f"Предмет: {subject}\n"
                    f"Задание: {title}\n"
                    f"Дата: {due_date_str}\n"
                    f"Тип: {visibility_emo}\n"
                    f"Описание: {description}\n"
                    f"Автор: {author_mention}"
                )
                await update.message.reply_text(msg, parse_mode='HTML')

                if not is_private:
                    global group_chat_id
                    target_chat_id = group_chat_id if group_chat_id else created_in_chat
                    msg_text = (
                        f"⚠️ <b>Новый ОБЩИЙ дедлайн!</b>\n"
                        f"Предмет: {subject}\n"
                        f"Задание: {title}\n"
                        f"Дата: {due_date_str}\n"
                        f"Описание: {description}\n"
                        f"Автор: {author_mention}"
                    )
                    try:
                        # Отправляем уведомление в группу только если дедлайн был создан не в ней
                        if update.effective_chat.type == Chat.PRIVATE:
                            await context.bot.send_message(chat_id=target_chat_id, text=msg_text, parse_mode='HTML')
                            logging.info(f"Отправлено уведомление в группу о новом дедлайне из личного чата")
                    except Exception as e:
                        logging.warning(f"Не удалось отправить уведомление в группу: {e}")

                    # Отправляем уведомления другим пользователям в личку
                    for uid in known_users:
                        if uid != created_by_id:
                            try:
                                # Не отправляем уведомление тому, кто создал дедлайн
                                await context.bot.send_message(
                                    chat_id=uid,
                                    text=f"(Общий дедлайн) {msg_text}",
                                    parse_mode='HTML'
                                )
                            except Exception as e:
                                logging.warning(f"Не удалось отправить ЛС user_id={uid}: {e}")

            except Exception as e:
                logging.error(f"Ошибка финализации дедлайна: {e}")
                await update.message.reply_text("❌ Произошла ошибка при добавлении дедлайна.")

            context.user_data['deadline_flow_step'] = None
            context.user_data['deadline_flow'] = {}

    async def _deadline_remove_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, txt: str) -> None:
        step = context.user_data['remove_flow_step']
        if step == REMOVE_DEADLINE_FLOW['ASK_ID']:
            try:
                deadline_id = int(txt)
                found_index = None
                global deadlines, group_chat_id
                removed = None

                for i, dl in enumerate(deadlines):
                    if dl['deadline_id'] == deadline_id:
                        found_index = i
                        removed = dl
                        break

                if found_index is not None:
                    # Отменяем все запланированные напоминания для удаляемого дедлайна
                    cancel_deadline_reminders(deadline_id)
                    
                    deadlines.pop(found_index)
                    save_deadlines()

                    remover_mention = f'<a href="tg://user?id={update.effective_user.id}">{update.effective_user.full_name}</a>'

                    # Сообщение в том же чате, где была вызвана команда
                    await update.message.reply_text(
                        f"❌ Дедлайн ID={deadline_id} удалён!\n"
                        f"Предмет: {removed['subject']} / Задание: {removed['title']}\n"
                        f"Удалил(а): {remover_mention}",
                        parse_mode='HTML'
                    )

                    # Если дедлайн был общий, уведомим группу НЕЗАВИСИМО от места удаления
                    if not removed['is_private']:
                        target_chat_id = group_chat_id if group_chat_id else Config.CHAT_ID
                        text_for_group = (
                            f"⚠️ <b>Общий дедлайн удалён!</b>\n"
                            f"ID: {deadline_id}\n"
                            f"Предмет: {removed['subject']}\n"
                            f"Задание: {removed['title']}\n"
                            f"Дата: {removed['due_date'].strftime('%Y-%m-%d %H:%M')}\n"
                            f"Удалил(а): {remover_mention}"
                        )

                        try:
                            # Отправляем в группу
                            await context.bot.send_message(
                                chat_id=target_chat_id,
                                text=text_for_group,
                                parse_mode='HTML'
                            )

                            # Отправляем уведомление всем пользователям в личку
                            for user_id in known_users:
                                if user_id != update.effective_user.id:  # Не отправляем тому, кто удалил
                                    try:
                                        personal_msg = (
                                                           f"❌ <b>Уведомление об удалении дедлайна</b>\n"
                                                           f"{'➖' * 20}\n\n"
                                                       ) + text_for_group

                                        await context.bot.send_message(
                                            chat_id=user_id,
                                            text=personal_msg,
                                            parse_mode='HTML'
                                        )
                                    except Exception as e:
                                        logging.warning(f"Не удалось отправить ЛС об удалении user_id={user_id}: {e}")

                        except Exception as e:
                            logging.warning(f"Не удалось отправить сообщение об удалении в группу: {e}")
                else:
                    await update.message.reply_text(
                        f"Нет дедлайна с таким ID: {deadline_id}"
                    )
            except ValueError:
                await update.message.reply_text("Введите число (ID дедлайна).")

            context.user_data['remove_flow_step'] = None

    async def _calc_average(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str,
                            is_diploma: bool) -> None:
        try:
            # Разделяем строку на числа, игнорируя все нечисловые символы
            raw = [x.strip() for x in text.replace(',', ' ').split()]
            if not raw:
                await update.message.reply_text("❌ Нет оценок. Введите числа через пробел.")
                return

            # Преобразуем строки в числа
            arr = []
            for num in raw:
                try:
                    n = float(num)
                    if 1 <= n <= 10:  # Изменено для 10-балльной системы
                        arr.append(n)
                    else:
                        await update.message.reply_text(f"❌ Оценка {n} вне диапазона 1-10!")
                        return
                except ValueError:
                    continue  # Пропускаем нечисловые значения

            if not arr:
                await update.message.reply_text("❌ Не найдено допустимых оценок (1-10)!")
                return

            avg = sum(arr) / len(arr)

            # Добавляем оценку словами
            def get_grade_word(avg):
                if avg >= 9.5:
                    return "Отлично с отличием"
                elif avg >= 8.5:
                    return "Отлично"
                elif avg >= 7.0:
                    return "Очень хорошо"
                elif avg >= 6.0:
                    return "Хорошо"
                elif avg >= 4.0:
                    return "Удовлетворительно"
                else:
                    return "Неудовлетворительно"

            grade_word = get_grade_word(avg)

            if is_diploma:
                response = (
                    f"📊 <b>Расчёт среднего балла диплома</b>\n\n"
                    f"Введённые оценки: {', '.join(map(str, arr))}\n"
                    f"Количество оценок: {len(arr)}\n"
                    f"✨ Средний балл: <b>{avg:.2f}</b>\n"
                    f"📝 Оценка: <b>{grade_word}</b>"
                )
            else:
                response = (
                    f"📚 <b>Расчёт среднего балла предмета</b>\n\n"
                    f"Введённые оценки: {', '.join(map(str, arr))}\n"
                    f"Количество оценок: {len(arr)}\n"
                    f"✨ Средний балл: <b>{avg:.2f}</b>\n"
                    f"📝 Оценка: <b>{grade_word}</b>"
                )

            await update.message.reply_text(response, parse_mode='HTML')
        except Exception as e:
            logging.error(f"Ошибка при расчете среднего балла: {e}")
            await update.message.reply_text("❌ Произошла ошибка при расчете.")
        finally:
            context.user_data['state'] = None  # Сбрасываем состояние

    async def _call_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action_type: str) -> None:
        user_id = str(update.effective_user.id)
        
        # Определяем метод отправки сообщения в зависимости от типа обновления
        if update.callback_query:
            send_message = context.bot.send_message
            chat_id = update.effective_chat.id
        else:
            send_message = update.message.reply_text
            chat_id = update.effective_chat.id

        if not self.action_manager.can_perform_action(user_id, action_type):
            if update.callback_query:
                await send_message(chat_id=chat_id, text="❗️ Нельзя так часто, подождите неделю.")
            else:
                await send_message("❗️ Нельзя так часто, подождите неделю.")
            return
            
        desc_map = {
            'beer': "пойти пить пиво",
            'board_games': "поиграть в настолки",
            'cinema': "сходить в кино",
            'walk': "пойти гулять"
        }
        desc = desc_map.get(action_type, "что-то сделать")
        text = f"{update.effective_user.first_name} предлагает {desc}! Кто присоединится?"

        sent_count = 0
        for uid in self.user_manager.get_users():
            if uid != user_id:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Ошибка рассылки user_id={uid}: {e}")

        self.action_manager.update_action_time(user_id, action_type)
        activity_name = desc_map.get(action_type, "действие").split(" ")[-1]
        
        if update.callback_query:
            await send_message(chat_id=chat_id, text=f"✅ Приглашение на {activity_name} отправлено всем! ({sent_count} получателей)")
        else:
            await send_message(f"✅ Приглашение на {activity_name} отправлено всем! ({sent_count} получателей)")

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Используем inline-кнопки везде (и в личке, и в группе)
        kb = [
            [InlineKeyboardButton("🎓 Средний балл диплома", callback_data="calc_diploma"),
             InlineKeyboardButton("📚 Балл по предмету", callback_data="calc_subject")],
            [InlineKeyboardButton("📞 Контакты", callback_data="contacts"),
             InlineKeyboardButton("🗓 Дедлайны", callback_data="deadlines")],
            [InlineKeyboardButton("🍺 Позвать пить пиво", callback_data="call_beer"),
             InlineKeyboardButton("🎲 Позвать в настолки", callback_data="call_board_games")],
            [InlineKeyboardButton("🎥 Позвать в кино", callback_data="call_cinema"),
             InlineKeyboardButton("🚶 Позвать гулять", callback_data="call_walk")],
            [InlineKeyboardButton("💳 Оплатить учебу", callback_data="pay_education")]
        ]
        await update.message.reply_text(
            "🔸 <b>Главное меню</b>\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )


################################################################################
#           /help, /set_group, /add_deadline, /list_deadlines COMMANDS        #
################################################################################

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "ℹ️ <b>Помощь по командам</b>\n\n"
        "🔸 <b>Основные команды</b>:\n"
        "/start - Запуск бота\n"
        "/help - Это сообщение\n"
        "/set_group - Установить группу для уведомлений\n\n"

        "🔸 <b>Работа с дедлайнами</b>:\n"
        "1️⃣ Через команды:\n"
        "/add_deadline false Математика 'Лаб1' 2025-03-10 'Решить 10 задач'\n"
        "Параметры: private subject title date description\n\n"

        "2️⃣ Через меню (рекомендуется):\n"
        "🗓 Дедлайны ➡️ ➕ Добавить\n\n"

        "🔸 <b>Просмотр и удаление</b>:\n"
        "/list_deadlines - Показать все доступные дедлайны\n"
        "/remove_deadline ID - Удалить дедлайн по ID\n\n"

        "🔸 <b>Дополнительно</b>:\n"
        "/diploma - Расчет среднего балла диплома\n"
        "/subject - Расчет среднего балла предмета\n\n"

        "❗️ <b>Важно</b>: Личные дедлайны видны только создателю"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def set_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global group_chat_id
    chat = update.effective_chat
    if chat.type not in (Chat.GROUP, Chat.SUPERGROUP):
        await update.message.reply_text("Команду /set_group нужно вызывать внутри группы, где бот является админом!")
        return

    group_chat_id = chat.id
    await update.message.reply_text(
        f"🔧 Установлен group_chat_id = {group_chat_id}.\n"
        "Теперь ОБЩИЕ дедлайны будут отправляться в этот чат."
    )


def check_allowed_group(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.id != Config.ALLOWED_GROUP_ID and update.effective_chat.type != Chat.PRIVATE:
            await update.message.reply_text("❌ Бот работает только в определенной группе!")
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


@check_allowed_group
async def add_deadline_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global deadlines
    try:
        args = context.args
        if len(args) < 5:
            await update.message.reply_text(
                "Неправильный формат!\n"
                "Используй: /add_deadline <is_private> <subject> <title> <YYYY-MM-DD HH:mm> <desc...>\n"
                "Или /help для примера."
            )
            return

        is_private_str = args[0].lower()
        subject = args[1]
        title = args[2]
        due_date_str = args[3]
        description = " ".join(args[4:])

        is_private = (is_private_str == "true")
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            # Если не указано время, используем конец дня
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").replace(hour=23, minute=59)

        if due_date < datetime.now():
            await update.message.reply_text("❌ Дата уже прошла! Выберите будущее время.")
            return

        new_deadline_id = len(deadlines) + 1
        created_by_id = update.effective_user.id
        created_in_chat = update.effective_chat.id
        author_mention = f'<a href="tg://user?id={created_by_id}">{update.effective_user.full_name}</a>'

        new_deadline = {
            "deadline_id": new_deadline_id,
            "title": title,
            "subject": subject,
            "description": description,
            "due_date": due_date,
            "is_private": is_private,
            "created_by_id": created_by_id,
            "created_in_chat": created_in_chat,
            "author_name": update.effective_user.full_name  # Сохраняем имя автора
        }
        deadlines.append(new_deadline)
        save_deadlines()

        # Планируем напоминания для нового дедлайна
        schedule_deadline_reminders(new_deadline)

        msg = (
            f"✅ <b>Дедлайн добавлен!</b>\n"
            f"ID: {new_deadline_id}\n"
            f"Предмет: {subject}\n"
            f"Задание: {title}\n"
            f"Дата: {due_date_str}\n"
            f"Тип: {'(Личный)' if is_private else '(Общий)'}\n"
            f"Описание: {description}\n"
            f"Автор: {author_mention}"
        )
        await update.message.reply_text(msg, parse_mode='HTML')

        if not is_private:
            global group_chat_id
            target_chat_id = group_chat_id if group_chat_id else created_in_chat
            msg_text = (
                f"⚠️ <b>Новый ОБЩИЙ дедлайн!</b>\n"
                f"Предмет: {subject}\n"
                f"Задание: {title}\n"
                f"Дата: {due_date_str}\n"
                f"Описание: {description}\n"
                f"Автор: {author_mention}"
            )
            try:
                # Отправляем уведомление в группу только если дедлайн был создан не в ней
                if update.effective_chat.type == Chat.PRIVATE:
                    await context.bot.send_message(chat_id=target_chat_id, text=msg_text, parse_mode='HTML')
                    logging.info(f"Отправлено уведомление в группу о новом дедлайне из личного чата")
            except Exception as e:
                logging.warning(f"Не удалось отправить уведомление в группу: {e}")

            # Отправляем уведомления другим пользователям в личку
            for uid in known_users:
                if uid != created_by_id:
                    try:
                        # Не отправляем уведомление тому, кто создал дедлайн
                        await context.bot.send_message(
                            chat_id=uid,
                            text=f"(Общий дедлайн) {msg_text}",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logging.warning(f"Не удалось отправить ЛС user_id={uid}: {e}")

    except Exception as e:
        logging.error(f"Ошибка при добавлении дедлайна: {e}")
        await update.message.reply_text("❌ Произошла ошибка при добавлении дедлайна.")


@check_allowed_group
async def list_deadlines_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        global deadlines
        user_id = update.effective_user.id

        if not deadlines:
            await update.message.reply_text("Пока нет ни одного дедлайна!")
            return
            
        # Определяем текущую дату для сравнения
        current_date = datetime.now()
        
        # Фильтруем только актуальные дедлайны
        filtered_deadlines = []
        
        for d in deadlines:
            # Пропускаем личные дедлайны других пользователей
            if d["is_private"] and d["created_by_id"] != user_id:
                continue
                
            # Определяем, истек ли срок дедлайна
            is_expired = d["due_date"] < current_date
            
            # Добавляем только неистекшие дедлайны
            if not is_expired:
                filtered_deadlines.append(d)
        
        if not filtered_deadlines:
            await update.message.reply_text("Нет актуальных дедлайнов для просмотра.")
            return
            
        # Формируем сообщение с заголовком
        msg = f"📋 <b>Список актуальных дедлайнов</b>:\n\n"
        
        # Отправляем первое сообщение с заголовком
        await update.message.reply_text(msg, parse_mode='HTML')
        
        # Отправляем каждый дедлайн отдельным сообщением
        for d in filtered_deadlines:
            try:
                date_str = d["due_date"].strftime("%Y-%m-%d %H:%M")
                try:
                    author_name = d.get('author_name', 'Неизвестный')
                    author_mention = f"<a href=\"tg://user?id={d['created_by_id']}\">{author_name}</a>"
                except:
                    author_mention = "Неизвестный"
                
                deadline_msg = (
                    f"📌 <b>ID: {d['deadline_id']}</b>\n"
                    f"📕 Предмет: {d['subject']}\n"
                    f"📝 Задание: {d['title']}\n"
                    f"📅 Дата: {date_str}\n"
                    f"💬 Описание: {d['description']}\n"
                    f"🔒 Личный: {'Да' if d['is_private'] else 'Нет'}\n"
                    f"👤 Автор: {author_mention}"
                )
                
                # Отправляем отдельное сообщение для каждого дедлайна
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=deadline_msg,
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке дедлайна: {e}")
                # Продолжаем с другими дедлайнами в случае ошибки
    except Exception as e:
        logging.error(f"Ошибка в list_deadlines_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при отображении дедлайнов.")


################################################################################
#                    APScheduler: check_deadlines JOB                          #
################################################################################

scheduler = BackgroundScheduler(timezone="Asia/Yekaterinburg")


def check_deadlines():
    """Проверяет дни рождения и отправляет поздравления"""
    logging.info(f"Запущена плановая проверка дней рождения...")
    
    try:
        async def send_notifications():
            # Проверяем дни рождения
            try:
                bot = Bot(token=Config.BOT_TOKEN)
                await check_birthdays(bot)
            except Exception as e:
                logging.error(f"Ошибка при проверке дней рождения: {e}")
                import traceback
                logging.error(traceback.format_exc())
        
        # Запускаем асинхронную функцию из неасинхронного кода
        asyncio.run(send_notifications())
        return "Проверка дней рождения завершена"
    except Exception as e:
        logging.error(f"Общая ошибка в проверке дней рождения: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return f"Ошибка: {e}"


################################################################################
#                   STUDENT BOT with Deadlines                                #
################################################################################

class StudentBot:
    def __init__(self, token: str):
        try:
            self.token = token
            
            # Инициализация файловой системы
            Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            
            # Инициализация менеджеров
            self.user_manager = UserManager(Config.USERS_FILE)
            self.action_manager = ActionManager(Config.ACTIONS_FILE)
            self.cmd_handlers = CommandHandlers(
                self.user_manager,
                self.action_manager
            )
            
            logging.info("StudentBot успешно инициализирован")
        except Exception as e:
            logging.critical(f"Ошибка при инициализации StudentBot: {e}")
            import traceback
            logging.critical(traceback.format_exc())
            raise

    async def _set_commands(self, app):
        try:
            await app.bot.set_my_commands([
                BotCommand("start", "Запуск бота"),
                BotCommand("menu", "Открыть меню с кнопками"),
                BotCommand("help", "Подсказка по дедлайнам"),
                BotCommand("set_group", "Установить групповой чат"),
                BotCommand("add_deadline", "Добавить дедлайн"),
                BotCommand("list_deadlines", "Список дедлайнов"),
                BotCommand("diploma", "Средний балл диплома"),
                BotCommand("subject", "Средний балл по предмету"),
                BotCommand("remove_deadline", "Удалить дедлайн")
            ])
            logging.info("Команды бота успешно настроены")
        except Exception as e:
            logging.error(f"Ошибка при настройке команд бота: {e}")
            raise
        
    # Обработчик ошибок для бота
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает ошибки, возникающие в хендлерах"""
        logging.error("Произошла ошибка при обработке обновления:")
        logging.error(f"Ошибка: {context.error}")
        
        # Добавляем полную информацию об ошибке
        import traceback
        traceback_str = ''.join(traceback.format_tb(context.error.__traceback__))
        logging.error(f"Стек вызовов:\n{traceback_str}")
        
        # Если произошла ошибка в обработчике callback_query
        if update and update.callback_query:
            try:
                await update.callback_query.answer("Произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова.")
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение об ошибке через callback_query: {e}")
        
        # Если произошла ошибка при обработке сообщения
        elif update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова."
                )
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение об ошибке: {e}")

    def run(self):
        # Настраиваем логирование
        logging.basicConfig(format=Config.LOG_FORMAT, level=Config.LOG_LEVEL,
                            handlers=[
                                logging.StreamHandler(),
                                logging.FileHandler("bot.log", encoding="utf-8")
                            ])
        
        try:
            # Загружаем данные
            load_deadlines()
            
            # Планируем задачу проверки дедлайнов и дней рождения каждый день в 8:00
            scheduler.add_job(check_deadlines, "cron", hour=8, minute=0, 
                             misfire_grace_time=3600, coalesce=True,
                             name="Проверка дней рождения")

            scheduler.start()

            application = (
                ApplicationBuilder()
                .token(self.token)
                .post_init(self._set_commands)
                .build()
            )

            application.bot_data['user_manager'] = self.user_manager
            application.bot_data['action_manager'] = self.action_manager
            # Добавляем CommandHandlers в bot_data для доступа из callback-функций
            application.bot_data['command_handlers'] = self.cmd_handlers
            
            # Восстанавливаем напоминания для существующих дедлайнов
            restore_deadline_reminders()
            
            # Добавляем обработчик ошибок
            application.add_error_handler(self.error_handler)
            
            # Основные команды.
            application.add_handler(CommandHandler("start", self.cmd_handlers.start))
            application.add_handler(CommandHandler("menu", self.cmd_handlers.menu_command))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("set_group", set_group_command))
            application.add_handler(CommandHandler("add_deadline", add_deadline_command))
            application.add_handler(CommandHandler("list_deadlines", list_deadlines_command))
            application.add_handler(CommandHandler("diploma", self.cmd_handlers.diploma_cmd))
            application.add_handler(CommandHandler("subject", self.cmd_handlers.subject_cmd))
            application.add_handler(CommandHandler("remove_deadline", self._remove_deadline_cmd))
            
            # Обработчики callback-кнопок (важно: размещаем их ПЕРЕД обработчиками текста)
            application.add_handler(CallbackQueryHandler(
                CallbackHandlers.menu_callback,
                pattern='^(calc_diploma|calc_subject|contacts|deadlines|call_beer|call_board_games|call_cinema|call_walk|pay_education)$'
            ))

            application.add_handler(CallbackQueryHandler(
                CallbackHandlers.contact_callback,
                pattern='^(contact_1|contact_2|main_menu)$'
            ))

            application.add_handler(CallbackQueryHandler(
                deadline_menu_callback,
                pattern='^(deadline_add|deadline_list|deadline_list_actual|deadline_list_expired|deadline_group|deadline_help|deadline_remove)$'
            ))

            # Обработчик для текста (и в личке, и в группе)
            application.add_handler(MessageHandler(
                filters.TEXT & (~filters.COMMAND),
                self.cmd_handlers.handle_text
            ))
            
            # Обработчик меню-кнопок
            application.add_handler(MessageHandler(
                filters.TEXT & (filters.COMMAND | filters.Regex(
                    r'^(🎓 Средний балл диплома|📞 Контакты администрации|📚 Балл по предмету|🍺 Позвать пить пиво|🎲 Позвать в настолки|🎥 Позвать в кино|🚶 Позвать гулять|🗓 Дедлайны)$'
                )) & (filters.ChatType.PRIVATE | filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
                self.cmd_handlers.handle_menu
            ))

            logging.info("Бот запущен и готов к работе!")
            application.run_polling(allowed_updates=Update.ALL_TYPES,
                                  drop_pending_updates=True,
                                  close_loop=False)
            
        except Exception as e:
            logging.critical(f"Критическая ошибка при запуске бота: {e}")
            import traceback
            logging.critical(traceback.format_exc())
            # Пытаемся перезапустить бот при критических ошибках
            logging.info("Перезапуск бота через 5 секунд...")
            import time
            time.sleep(5)
            self.run()

    async def _remove_deadline_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Использование: /remove_deadline <ID>")
            return
        
        try:
            deadline_id = int(context.args[0])
            found_index = None
            global deadlines, group_chat_id
            removed = None

            for i, dl in enumerate(deadlines):
                if dl['deadline_id'] == deadline_id:
                    found_index = i
                    removed = dl
                    break

            if found_index is not None:
                # Отменяем все запланированные напоминания для удаляемого дедлайна
                cancel_deadline_reminders(deadline_id)
                
                deadlines.pop(found_index)
                save_deadlines()

                remover_mention = f'<a href="tg://user?id={update.effective_user.id}">{update.effective_user.full_name}</a>'

                # Сообщение в том же чате, где была вызвана команда
                await update.message.reply_text(
                    f"❌ Дедлайн ID={deadline_id} удалён!\n"
                    f"Предмет: {removed['subject']} / Задание: {removed['title']}\n"
                    f"Удалил(а): {remover_mention}",
                    parse_mode='HTML'
                )

                # Если дедлайн был общий, уведомим группу НЕЗАВИСИМО от места удаления
                if not removed['is_private']:
                    target_chat_id = group_chat_id if group_chat_id else Config.CHAT_ID
                    text_for_group = (
                        f"⚠️ <b>Общий дедлайн удалён!</b>\n"
                        f"ID: {deadline_id}\n"
                        f"Предмет: {removed['subject']}\n"
                        f"Задание: {removed['title']}\n"
                        f"Дата: {removed['due_date'].strftime('%Y-%m-%d %H:%M')}\n"
                        f"Удалил(а): {remover_mention}"
                    )

                    try:
                        # Отправляем в группу
                        await context.bot.send_message(
                            chat_id=target_chat_id,
                            text=text_for_group,
                            parse_mode='HTML'
                        )

                        # Отправляем уведомление всем пользователям в личку
                        for user_id in known_users:
                            if user_id != update.effective_user.id:  # Не отправляем тому, кто удалил
                                try:
                                    personal_msg = (
                                                       f"❌ <b>Уведомление об удалении дедлайна</b>\n"
                                                       f"{'➖' * 20}\n\n"
                                                   ) + text_for_group

                                    await context.bot.send_message(
                                        chat_id=user_id,
                                        text=personal_msg,
                                        parse_mode='HTML'
                                    )
                                except Exception as e:
                                    logging.warning(f"Не удалось отправить ЛС об удалении user_id={user_id}: {e}")

                    except Exception as e:
                        logging.warning(f"Не удалось отправить сообщение об удалении в группу: {e}")
            else:
                await update.message.reply_text(
                    f"Нет дедлайна с таким ID: {deadline_id}"
                )
        except ValueError:
            await update.message.reply_text("Нужно ввести число (ID).")

        context.user_data['remove_flow_step'] = None


################################################################################
#                                  MAIN                                        #
################################################################################

def main():
    # Проверяем конфигурацию
    try:
        Config.validate()
    except ValueError as e:
        logging.critical(f"Ошибка конфигурации: {e}")
        print(f"❌ Ошибка конфигурации: {e}")
        print("📝 Создайте файл .env на основе .env.example")
        return
    
    # Настраиваем логирование
    logging.basicConfig(format=Config.LOG_FORMAT, level=Config.LOG_LEVEL)
    
    # Создаем необходимые директории
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        # Проверяем наличие JSON-файла с днями рождения и при необходимости конвертируем из Excel
        json_path = Config.BIRTHDAYS_FILE
        excel_path = str(json_path).replace('.json', '.xlsx')
        
        if not os.path.exists(json_path) and os.path.exists(excel_path):
            logging.info(f"Конвертируем данные о днях рождения из Excel в JSON...")
            if convert_excel_to_json(excel_path, json_path):
                logging.info(f"Конвертация успешно завершена")
            else:
                logging.error(f"Не удалось конвертировать данные о днях рождения")
        
        # Загружаем дедлайны
        load_deadlines()
        
        # Создаем и запускаем бота
        bot = StudentBot(Config.BOT_TOKEN)
        bot.run()
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске приложения: {e}")
        import traceback
        logging.critical(traceback.format_exc())


if __name__ == "__main__":
    main()
