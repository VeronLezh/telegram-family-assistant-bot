from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CHAT_IDS_ALL, CALENDAR_PERSONAL_USERS, CALENDAR_FAMILY_USERS
from handlers.expenses import expenses_menu, kids_expenses_menu
from services.calendar import get_calendar_events


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_keyboard = [
        [InlineKeyboardButton("📚 Расписание уроков", callback_data="menu_schedule")],
        [InlineKeyboardButton("🏋️ Тренировки и доп.занятия детей", callback_data="menu_trainings")],
        [InlineKeyboardButton("💸 ЖКХ и связь", callback_data="menu_expenses")],
        [InlineKeyboardButton("👧 Траты на детей", callback_data="menu_kids_expenses")],
    ]
    if update.effective_user and update.effective_user.id in CHAT_IDS_ALL:
        inline_keyboard.append([InlineKeyboardButton("📅 Личный календарь", callback_data="menu_calendar_personal")])
        inline_keyboard.append([InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный календарь", callback_data="menu_calendar_family")])
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

    if update.message:
        await update.message.reply_text("Выберите действие:", reply_markup=inline_reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Выберите действие:", reply_markup=inline_reply_markup)


async def calendar_callback(query, context: ContextTypes.DEFAULT_TYPE, calendar_type="personal"):
    user_id = query.from_user.id if query.from_user else None

    allowed_personal_users = CALENDAR_PERSONAL_USERS
    allowed_family_users = CALENDAR_FAMILY_USERS

    if calendar_type == "personal" and user_id not in allowed_personal_users:
        await query.edit_message_text("⛔️ Доступ к личному календарю разрешён только Анне.")
        return

    if calendar_type == "family" and user_id not in allowed_family_users:
        await query.edit_message_text("⛔️ Доступ к семейному календарю разрешён только для семьи.")
        return

    events_text = get_calendar_events(7, calendar_type=calendar_type)
    keyboard = [[InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=events_text, reply_markup=reply_markup)


async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import logging
    from handlers.schedule import schedule
    from handlers.trainings import trainings

    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        if data == "menu_schedule":
            await schedule(update, context)
        elif data == "menu_trainings":
            await trainings(update, context)
        elif data == "menu_calendar_personal":
            await calendar_callback(query, context, calendar_type="personal")
        elif data == "menu_calendar_family":
            await calendar_callback(query, context, calendar_type="family")
        elif data == "menu_expenses":
            await expenses_menu(update, context)
        elif data == "menu_kids_expenses":
            await kids_expenses_menu(update, context)
        elif data == "menu_back":
            await menu(update, context)
    except Exception as e:
        logging.error(f"Ошибка в menu_button_handler (data={data}): {e}", exc_info=True)
        await query.edit_message_text(f"⚠️ Ошибка: {e}")
