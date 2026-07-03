import json
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "..", "schedule.json")

CHILDREN = ["Виктор", "Галя"]

SCHEDULES: dict[str, dict[str, list]] = {
    "Виктор": {
        "Понедельник": ["Алгебра", "Рус. яз.", "Физика", "Физ-ра"],
        "Вторник": ["Англ. яз.", "Рус. яз.", "История", "Геометрия"],
        "Среда": ["География", "Биология", "Физ-ра", "Алгебра"],
        "Четверг": ["Рус. яз.", "История", "Алгебра", "Музыка"],
        "Пятница": ["Информатика", "Рус. яз.", "География", "Геометрия"]
    },
    "Галя": {
        "Понедельник": [],
        "Вторник": [],
        "Среда": [],
        "Четверг": [],
        "Пятница": []
    }
}

DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]


def load_schedule():
    global SCHEDULES
    from services.sheets import read_sheet
    data = read_sheet("schedules")
    if data:
        SCHEDULES = data
        return
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if DAYS[0] in data and not any(c in data for c in CHILDREN):
                SCHEDULES["Виктор"] = data
            else:
                SCHEDULES = data
    except Exception as e:
        logging.error(f"Ошибка загрузки расписания: {e}")


def save_schedule():
    from services.sheets import write_sheet
    write_sheet("schedules", SCHEDULES)
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(SCHEDULES, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения расписания в файл: {e}")


def set_lesson(child: str, day: str, index: int, text: str):
    SCHEDULES.setdefault(child, {}).setdefault(day, [])
    schedule = SCHEDULES[child][day]
    while len(schedule) < index:
        schedule.append("")
    schedule[index - 1] = text
    save_schedule()


def add_lesson(child: str, day: str, text: str):
    SCHEDULES.setdefault(child, {}).setdefault(day, []).append(text)
    save_schedule()


def remove_lesson(child: str, day: str, index: int):
    day_schedule = SCHEDULES.get(child, {}).get(day, [])
    if 0 < index <= len(day_schedule):
        day_schedule.pop(index - 1)
        save_schedule()


def get_schedule(child: str, day: str) -> str:
    lessons = SCHEDULES.get(child, {}).get(day, [])
    if lessons:
        lines = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lessons))
        return f"📚 Расписание {child} на {day}:\n\n{lines}"
    return f"❌ Нет расписания для {child} на {day}."


# --- Handlers ---

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👦 Виктор", callback_data="schedule_child_Виктор"),
         InlineKeyboardButton("👧 Галя", callback_data="schedule_child_Галя")],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
    ]
    text = "Чьё расписание показать?"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def schedule_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("schedule_child_"):
        child = data.replace("schedule_child_", "")
        keyboard = [[InlineKeyboardButton(day, callback_data=f"schedule_{child}_{day}")] for day in DAYS]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_schedule")])
        await query.edit_message_text(
            f"Расписание {child} — выберите день:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("schedule_"):
        # format: schedule_<child>_<day>
        parts = data[len("schedule_"):].split("_", 1)
        if len(parts) == 2:
            child, day = parts
            text = get_schedule(child, day)
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"schedule_child_{child}")]]
            await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))


async def setschedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /setschedule <Виктор|Галя> <день> <номер> <текст>
    if not context.args or len(context.args) < 4:
        await update.message.reply_text("Использование: /setschedule <Виктор|Галя> <день> <номер> <текст>")
        return
    child, day = context.args[0], context.args[1]
    try:
        index = int(context.args[2])
    except ValueError:
        await update.message.reply_text("Номер урока должен быть числом")
        return
    text = " ".join(context.args[3:])
    set_lesson(child, day, index, text)
    from utils import send_and_pin
    await send_and_pin(context.bot, f"📢 Расписание {child} обновлено: {day}, урок {index} → {text}")


async def addlesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /addlesson <Виктор|Галя> <день> <текст>
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Использование: /addlesson <Виктор|Галя> <день> <текст>")
        return
    child, day = context.args[0], context.args[1]
    text = " ".join(context.args[2:])
    add_lesson(child, day, text)
    from utils import send_and_pin
    await send_and_pin(context.bot, f"📢 Расписание {child} обновлено: {day} добавлен урок {text}")


async def removelesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /removelesson <Виктор|Галя> <день> <номер>
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Использование: /removelesson <Виктор|Галя> <день> <номер>")
        return
    child, day = context.args[0], context.args[1]
    try:
        index = int(context.args[2])
    except ValueError:
        await update.message.reply_text("Номер должен быть числом")
        return
    remove_lesson(child, day, index)
    from utils import send_and_pin
    await send_and_pin(context.bot, f"📢 Расписание {child} обновлено: {day}, урок {index} удалён")
