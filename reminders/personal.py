import json
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

from config import USER_ANNA, USER_VIKTOR, USER_GALYA

REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "personal_reminders.json")
SMART_REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "smart_reminders.json")

# Статичные напоминания (ежемесячные, с полем "day")
PERSONAL_REMINDERS = [
    {"day": 25, "time": "09:00", "text": "🏦 Платеж по ипотеке", "chat_id": USER_ANNA},
    {"day": 23, "time": "10:00", "text": "📟 Отдать показания по счетчикам", "chat_id": USER_ANNA},
]

# Ежедневные напоминания (без поля "day" — срабатывают каждый день)
DAILY_REMINDERS = [
    {"time": "15:00", "text": "🗑️ Виктор, не забудь вынести мусор!", "chat_id": USER_VIKTOR},
    {"time": "15:10", "text": "💧 Виктор, сходи за водой.", "chat_id": USER_VIKTOR},
    {"time": "12:00", "text": "📖 Галя, почитай книгу!", "chat_id": USER_GALYA},
]


def load_personal_reminders() -> list:
    from services.sheets import read_sheet
    data = read_sheet("personal_reminders")
    if data is not None:
        return data
    try:
        if os.path.exists(REMINDERS_FILE):
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки personal reminders: {e}")
    return []


def save_personal_reminders(reminders: list):
    from services.sheets import write_sheet
    write_sheet("personal_reminders", reminders)
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения personal reminders в файл: {e}")


PERSONAL_REMINDERS_DYNAMIC = load_personal_reminders()


def load_smart_reminders() -> list:
    from services.sheets import read_sheet
    data = read_sheet("smart_reminders")
    if data is not None:
        return data
    try:
        if os.path.exists(SMART_REMINDERS_FILE):
            with open(SMART_REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки smart reminders: {e}")
    return []


def save_smart_reminders(reminders: list):
    from services.sheets import write_sheet
    write_sheet("smart_reminders", reminders)
    try:
        with open(SMART_REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения smart reminders в файл: {e}")


SMART_REMINDERS_DYNAMIC = load_smart_reminders()


def add_smart_reminder(reminder: dict):
    SMART_REMINDERS_DYNAMIC.append(reminder)
    save_smart_reminders(SMART_REMINDERS_DYNAMIC)


def add_personal_reminder(reminder: dict):
    global PERSONAL_REMINDERS_DYNAMIC
    PERSONAL_REMINDERS_DYNAMIC.append(reminder)
    save_personal_reminders(PERSONAL_REMINDERS_DYNAMIC)


# --- Команда /addreminder ---
async def addreminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /addreminder <день_месяца> <HH:MM> <текст>")
        return

    try:
        day = int(context.args[0])
    except ValueError:
        await update.message.reply_text("День должен быть числом (1-31)")
        return

    time_str = context.args[1]
    text = " ".join(context.args[2:])
    if not text:
        await update.message.reply_text("Добавьте текст напоминания")
        return

    reminder = {
        "day": day,
        "time": time_str,
        "text": text,
        "chat_id": USER_ANNA
    }
    add_personal_reminder(reminder)
    await update.message.reply_text(f"✅ Напоминание добавлено: {day} число в {time_str}")
