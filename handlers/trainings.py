import json
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

TRAININGS_FILE = os.path.join(os.path.dirname(__file__), "..", "trainings.json")

TRAININGS = {
    "Галя": {
        "Понедельник": ["19:00 - 20:00"],
        "Среда": ["19:00 - 20:00"],
        "Пятница": ["18:15 - 19:00", "19:00 - 20:00"]
    },
    "Виктор": {
        "Понедельник": ["19:00 - 20:30"],
        "Среда": ["19:00 - 20:30"],
        "Вторник": ["17:30 - 18:00 📘 Английский язык"]
    }
}


def load_trainings():
    global TRAININGS
    from services.sheets import read_sheet
    data = read_sheet("trainings")
    if data:
        TRAININGS = data
        return
    try:
        if os.path.exists(TRAININGS_FILE):
            with open(TRAININGS_FILE, "r", encoding="utf-8") as f:
                TRAININGS = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки тренировок: {e}")


def save_trainings():
    from services.sheets import write_sheet
    write_sheet("trainings", TRAININGS)
    try:
        with open(TRAININGS_FILE, "w", encoding="utf-8") as f:
            json.dump(TRAININGS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения тренировок в файл: {e}")


def get_trainings(day: str) -> str:
    result = []
    for child, schedule in TRAININGS.items():
        if day in schedule:
            lessons = "\n".join([f"⏰ {t}" for t in schedule[day]])
            result.append(f"👤 {child}:\n{lessons}")
    if result:
        return f"🏋️ Тренировки на {day}:\n\n" + "\n\n".join(result)
    return f"❌ Нет тренировок в {day}."


async def trainings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    training_days = set()
    for child_schedule in TRAININGS.values():
        training_days.update(child_schedule.keys())
    week_days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    sorted_days = [day for day in week_days_order if day in training_days]

    keyboard = []
    for day in sorted_days:
        keyboard.append([InlineKeyboardButton(day, callback_data=f"trainings_{day}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("Выберите день недели для просмотра тренировок:", reply_markup=reply_markup)
    else:
        query = update.callback_query
        await query.edit_message_text("Выберите день недели для просмотра тренировок:", reply_markup=reply_markup)


async def trainings_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("trainings_"):
        day = query.data.replace("trainings_", "")
        trainings_text = get_trainings(day)
        keyboard = [[InlineKeyboardButton("◀️ Назад к тренировкам", callback_data="menu_trainings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=trainings_text, reply_markup=reply_markup)


def remove_training_by_time(child: str, day: str, time_pattern: str) -> str | None:
    if child not in TRAININGS or day not in TRAININGS[child]:
        return None
    for i, t in enumerate(TRAININGS[child][day]):
        if time_pattern in t:
            removed = TRAININGS[child][day].pop(i)
            if not TRAININGS[child][day]:
                del TRAININGS[child][day]
            save_trainings()
            return removed
    return None


async def addtraining_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /addtraining Галя Понедельник 19:00 - 20:00
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Использование: /addtraining <ребёнок> <день> <время>\nПример: /addtraining Галя Понедельник 19:00 - 20:00")
        return
    child = context.args[0]
    day = context.args[1]
    time_text = " ".join(context.args[2:])
    if child not in TRAININGS:
        TRAININGS[child] = {}
    if day not in TRAININGS[child]:
        TRAININGS[child][day] = []
    TRAININGS[child][day].append(time_text)
    save_trainings()
    from utils import send_and_pin
    await send_and_pin(context.bot, f"📢 Расписание обновлено: {child} — {day} добавлено {time_text}")


async def removetraining_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /removetraining Галя Понедельник 1
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Использование: /removetraining <ребёнок> <день> <номер>\nПример: /removetraining Галя Понедельник 1")
        return
    child = context.args[0]
    day = context.args[1]
    try:
        index = int(context.args[2])
    except ValueError:
        await update.message.reply_text("Номер должен быть числом")
        return
    if child not in TRAININGS or day not in TRAININGS[child] or not (0 < index <= len(TRAININGS[child][day])):
        await update.message.reply_text("❌ Не найдено. Проверьте имя, день и номер.")
        return
    removed = TRAININGS[child][day].pop(index - 1)
    if not TRAININGS[child][day]:
        del TRAININGS[child][day]
    save_trainings()
    from utils import send_and_pin
    await send_and_pin(context.bot, f"📢 Расписание обновлено: {child} — {day} удалено {removed}")
