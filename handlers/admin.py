from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_USERS, WISHLIST_REMINDER_DAYS

BACK_TO_HELP = [[InlineKeyboardButton("◀️ Назад к помощи", callback_data="admin_help")]]


def _is_admin(query) -> bool:
    return query.from_user and query.from_user.id in ADMIN_USERS


def _help_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🔗 Команды Make.com", callback_data="admin_help_make")],
        [InlineKeyboardButton("🤖 AI и голос", callback_data="admin_help_ai")],
        [InlineKeyboardButton("🎁 Список желаний", callback_data="admin_help_wishlist")],
        [InlineKeyboardButton("💸 ЖКХ и связь", callback_data="admin_help_expenses")],
    ]
    if is_admin:
        buttons += [
            [InlineKeyboardButton("📚 Редактировать расписание", callback_data="admin_help_schedule")],
            [InlineKeyboardButton("🏋️ Редактировать тренировки", callback_data="admin_help_trainings")],
            [InlineKeyboardButton("⏰ Напоминания", callback_data="admin_help_reminder")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_help_broadcast")],
        ]
    return InlineKeyboardMarkup(buttons)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    is_admin = user_id in ADMIN_USERS
    await update.message.reply_text("🛠 Помощь — выберите раздел:", reply_markup=_help_keyboard(is_admin))


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_admin = _is_admin(query)
    await query.edit_message_text("🛠 Помощь — выберите раздел:", reply_markup=_help_keyboard(is_admin))


async def admin_help_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(query):
        await query.edit_message_text("⛔️ Доступ запрещён")
        return
    text = (
        "📚 Редактирование расписания\n\n"
        "Изменить урок:\n"
        "/setschedule Виктор Понедельник 1 Алгебра (27)\n"
        "/setschedule Галя Понедельник 1 Математика\n\n"
        "Добавить урок в конец дня:\n"
        "/addlesson Виктор Пятница Физкультура\n"
        "/addlesson Галя Среда Рисование\n\n"
        "Удалить урок по номеру:\n"
        "/removelesson Виктор Среда 3\n"
        "/removelesson Галя Четверг 2\n\n"
        "Дети: Виктор, Галя\n"
        "Дни: Понедельник, Вторник, Среда, Четверг, Пятница"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_trainings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(query):
        await query.edit_message_text("⛔️ Доступ запрещён")
        return
    text = (
        "🏋️ Редактирование тренировок\n\n"
        "Добавить тренировку:\n"
        "/addtraining Галя Понедельник 18:00 - 19:00\n\n"
        "Удалить тренировку по номеру:\n"
        "/removetraining Галя Понедельник 1\n\n"
        "Умное удаление (просто напиши в чат):\n"
        "удали тренировку Гали в пятницу в 18:15\n"
        "убери тренировку Виктора в среду\n\n"
        "Дети: Галя, Виктор\n"
        "Дни: Понедельник, Вторник, Среда, Четверг, Пятница"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(query):
        await query.edit_message_text("⛔️ Доступ запрещён")
        return
    text = (
        "⏰ Напоминания\n\n"
        "Умное напоминание (просто напиши в чат):\n"
        "напомни через 2 часа позвонить врачу\n"
        "напомни завтра в 9 утра про собрание\n\n"
        "Ежемесячное напоминание:\n"
        "/addreminder <день_месяца> <HH:MM> <текст>\n"
        "Пример: /addreminder 15 09:00 Оплатить интернет"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🤖 AI и голос\n\n"
        "Чат с AI:\n"
        "Просто напиши сообщение — AI ответит и помнит контекст разговора.\n\n"
        "Голосовые сообщения:\n"
        "Отправь войс — бот распознает речь и ответит.\n\n"
        "Анализ фото:\n"
        "Отправь фото — AI опишет что на нём.\n"
        "С подписью: отправь фото + вопрос в подписи.\n\n"
        "Постоянная память:\n"
        "запомни, что я не ем мясо — бот сохранит факт навсегда\n"
        "/core — посмотреть, что бот о тебе помнит\n"
        "/core <факт> — добавить\n"
        "/core clear — очистить\n\n"
        "Сброс истории разговора (память при этом остаётся):\n"
        "/reset"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🎁 Список желаний\n\n"
        "Добавить пожелание (просто напиши в чат):\n"
        "хочу на день рождения наушники Sony\n"
        "добавь в список желаний велосипед\n\n"
        "Посмотреть списки:\n"
        "/wishlist — все списки\n"
        "/wishlist Виктор — список одного человека\n\n"
        f"За {WISHLIST_REMINDER_DAYS} дн. до дня рождения бот сам пришлёт список остальным "
        "(или идеи от AI, если список пуст)."
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "💸 ЖКХ и связь\n\n"
        "Записать трату:\n"
        "/expenses — открыть меню, выбрать категорию (ЖКХ / Интернет / Телефон-связь) "
        "и написать сумму в ответ.\n"
        "Также доступно из /menu → «💸 ЖКХ и связь».\n\n"
        "Отдельно от трекера трат на детей (см. раздел Make.com) — эти суммы уходят "
        "в отдельную вкладку таблицы."
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(query):
        await query.edit_message_text("⛔️ Доступ запрещён")
        return
    text = (
        "📢 Рассылка всем\n\n"
        "Отправить сообщение Борису, Виктору и Гале сразу:\n"
        "/broadcast <текст>\n\n"
        "Пример:\n"
        "/broadcast Обедаем в 13:00, не опаздывайте!"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))


async def admin_help_make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🔗 Команды Make.com\n\n"
        "💸 Записать трату по детям:\n"
        "Дети <Имя> <на что> <сумма>\n"
        "→ Дети Галя секция 1500\n"
        "→ Дети Виктор учебники 800\n"
        "Также можно через кнопки: /kidsexpenses или /menu → «👧 Траты на детей»\n\n"
        "📊 Получить отчёт по тратам:\n"
        "Отчет\n\n"
        "🌤 Прогноз погоды:\n"
        "Погода\n\n"
        "📅 Добавить событие в семейный календарь:\n"
        "Событие <что> <дата> <время>\n"
        "→ Событие Врач 25.04 14:00\n"
        "→ Событие День рождения Пети 01.05 12:00\n\n"
        "🗳 Создать голосование в семейный чат:\n"
        "Голосование <вариант1> <вариант2> <вариант3>\n"
        "→ Голосование Пицца Суши Бургеры\n\n"
        "🛒 Добавить покупки в Notion:\n"
        "Покупки <товар1> <товар2> <товар3>\n"
        "→ Покупки молоко хлеб яйца\n\n"
        "📋 Показать список покупок:\n"
        "Список"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(BACK_TO_HELP))
