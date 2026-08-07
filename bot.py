import logging
import threading
import time

import telegram.error
from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, ChosenInlineResultHandler,
    CommandHandler, InlineQueryHandler, MessageHandler, filters
)

from config import (
    BOT_TOKEN, ADMIN_USERS, CHAT_IDS_ALL, USER_ANNA,
    MEMORY_USERS, MEMORY_CORE_MAX_CHARS, MEMORY_FACT_MAX_CHARS
)
from handlers.admin import (
    admin_help, help_command,
    admin_help_schedule, admin_help_trainings, admin_help_reminder, admin_help_make,
    admin_help_ai, admin_help_broadcast, admin_help_wishlist, admin_help_expenses
)
from handlers.expenses import (
    expenses_menu, expenses_button_handler,
    kids_expenses_menu, kids_expenses_button_handler
)
from handlers.menu import menu, menu_button_handler
from handlers.messages import handle_message, handle_voice_message, handle_photo_message
from handlers.schedule import (
    load_schedule, schedule,
    schedule_button_handler, setschedule_command,
    addlesson_command, removelesson_command
)
from handlers.trainings import (
    load_trainings, trainings, trainings_button_handler,
    addtraining_command, removetraining_command
)
from handlers.inline import inline_query_handler, chosen_inline_result_handler
from reminders.personal import addreminder_command
from reminders.wishlist import wishlist_command
from reminders.jobs import (
    send_training_reminders, send_personal_reminders, send_dynamic_reminder,
    send_birthday_wishes, send_smart_reminders, send_busy_day_alert, send_wishlist_reminder
)
from server import run_flask
from services.ai import ai_answer, reset_history
from services.memory import get_core, append_core_line, clear_core
from services.calendar import get_calendar_events


async def start(update: Update, context):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"Привет, {user_name}! 👋\n"
        "Анна наконец-то решила делегировать мне всю свою рутину!\n"
        "Мои суперсилы:\n"
        "• Напоминаю про тренировки 💪\n"
        "• Знаю всё расписание 🎓\n"
        "• Показываю календарь 📅\n"
        "• Добавляю события в семейный календарь по сообщению в чат 🏠\n"
        "• Отвечаю с прогнозом и советом по одежде на слово Погода\n"
        "• Добавлю события в google календарь\n"
        "• Добавлю траты по детям и пришлю отчет по запросу\n"
        "• Запишу траты по ЖКХ и связи\n"
        "• Добавлю покупки в список\n"
    )
    if update.message:
        await update.message.reply_text(welcome_text)
        await menu(update, context)
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome_text)
        await menu(update, context)


async def ping(update: Update, context):
    await update.message.reply_text("Понг! 🏓")


async def stop(update: Update, context):
    await update.message.reply_text("Бот останавливается... 👋")
    await context.application.stop()



async def status_command(update: Update, context):
    await update.message.reply_text("✅ Бот работает нормально.")


async def id_command(update: Update, context):
    user_id = update.effective_user.id if update.effective_user else "неизвестен"
    await update.message.reply_text(f"Ваш Telegram ID: `{user_id}`", parse_mode="Markdown")


async def reset_command(update: Update, context):
    user_id = update.effective_user.id if update.effective_user else None
    reset_history(user_id)
    await update.message.reply_text("🔄 История разговора сброшена. Начнём с чистого листа!")


async def core_command(update: Update, context):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in MEMORY_USERS:
        await update.message.reply_text("⛔️ Для тебя память отключена.")
        return

    arg = " ".join(context.args) if context.args else ""

    if arg.lower() == "clear":
        clear_core(user_id)
        await update.message.reply_text("🧹 Память очищена.")
        return

    if arg:
        result = append_core_line(user_id, arg)
        if result.duplicate:
            await update.message.reply_text("🧠 Это я уже помню.")
            return
        reply = f"🧠 Запомнил: {result.core.splitlines()[-1].lstrip('- ')}"
        if result.truncated:
            reply += f"\n\n⚠️ Факт длинный, сохранил первые {MEMORY_FACT_MAX_CHARS} символов."
        if result.dropped:
            reply += f"\n\n⚠️ Ядро заполнено, вытеснено самых старых строк: {result.dropped}."
        await update.message.reply_text(reply)
        return

    core = get_core(user_id)
    if not core:
        await update.message.reply_text(
            "🧠 Память пока пустая.\n\n"
            "Добавить: /core я не ем мясо\n"
            "Или просто напиши: запомни, что я не ем мясо"
        )
        return
    await update.message.reply_text(
        f"🧠 Что я о тебе помню ({len(core)}/{MEMORY_CORE_MAX_CHARS} символов):\n\n{core}\n\n"
        "Добавить: /core <факт>\nОчистить: /core clear"
    )


async def broadcast_command(update: Update, context):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in ADMIN_USERS:
        await update.message.reply_text("⛔️ Только Анна может отправлять рассылку.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return
    text = " ".join(context.args)
    recipients = [uid for uid in CHAT_IDS_ALL if uid != USER_ANNA]
    sent = 0
    for uid in recipients:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
            sent += 1
        except Exception as e:
            logging.error(f"Ошибка broadcast для {uid}: {e}")
    await update.message.reply_text(f"✅ Отправлено {sent} из {len(recipients)} получателей.")


async def ai_command(update: Update, context):
    if not context.args:
        await update.message.reply_text("Использование: /ai <текст>")
        return
    user_id = update.effective_user.id if update.effective_user else None
    text = " ".join(context.args)
    reply = await ai_answer(text, user_id)
    await update.message.reply_text(reply)


async def calendar_command(update: Update, context):
    from config import CALENDAR_PERSONAL_USERS
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in CALENDAR_PERSONAL_USERS:
        await update.message.reply_text("⛔️ Доступ к календарю разрешён только Анне.")
        return
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
            if days > 30:
                await update.message.reply_text("⚠️ Можно запросить максимум 30 дней.")
                days = 30
        except ValueError:
            await update.message.reply_text("⚠️ Используйте: /calendar [количество_дней]\nНапример: /calendar 7")
            return
    events_text = get_calendar_events(days)
    await update.message.reply_text(events_text)


def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    application = Application.builder().token(BOT_TOKEN).build()
    load_schedule()
    load_trainings()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("trainings", trainings))
    application.add_handler(CommandHandler("calendar", calendar_command))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("setschedule", setschedule_command))
    application.add_handler(CommandHandler("addlesson", addlesson_command))
    application.add_handler(CommandHandler("removelesson", removelesson_command))
    application.add_handler(CommandHandler("addreminder", addreminder_command))
    application.add_handler(CommandHandler("wishlist", wishlist_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("core", core_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("addtraining", addtraining_command))
    application.add_handler(CommandHandler("removetraining", removetraining_command))
    application.add_handler(CommandHandler("expenses", expenses_menu))
    application.add_handler(CommandHandler("kidsexpenses", kids_expenses_menu))

    application.add_handler(CallbackQueryHandler(menu_button_handler, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(schedule_button_handler, pattern="^schedule_"))
    application.add_handler(CallbackQueryHandler(trainings_button_handler, pattern="^trainings_"))
    application.add_handler(CallbackQueryHandler(expenses_button_handler, pattern="^expense_"))
    application.add_handler(CallbackQueryHandler(kids_expenses_button_handler, pattern="^kidsexpense_"))
    application.add_handler(CallbackQueryHandler(admin_help, pattern="^admin_help$"))
    application.add_handler(CallbackQueryHandler(admin_help_schedule, pattern="^admin_help_schedule$"))
    application.add_handler(CallbackQueryHandler(admin_help_trainings, pattern="^admin_help_trainings$"))
    application.add_handler(CallbackQueryHandler(admin_help_reminder, pattern="^admin_help_reminder$"))
    application.add_handler(CallbackQueryHandler(admin_help_make, pattern="^admin_help_make$"))
    application.add_handler(CallbackQueryHandler(admin_help_ai, pattern="^admin_help_ai$"))
    application.add_handler(CallbackQueryHandler(admin_help_broadcast, pattern="^admin_help_broadcast$"))
    application.add_handler(CallbackQueryHandler(admin_help_wishlist, pattern="^admin_help_wishlist$"))
    application.add_handler(CallbackQueryHandler(admin_help_expenses, pattern="^admin_help_expenses$"))

    application.add_handler(InlineQueryHandler(inline_query_handler))
    application.add_handler(ChosenInlineResultHandler(chosen_inline_result_handler))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    application.job_queue.run_repeating(send_training_reminders, interval=60, first=5)
    application.job_queue.run_repeating(send_personal_reminders, interval=60, first=10)
    application.job_queue.run_repeating(send_dynamic_reminder, interval=60, first=0)
    application.job_queue.run_repeating(send_birthday_wishes, interval=60, first=15)
    application.job_queue.run_repeating(send_smart_reminders, interval=60, first=20)
    application.job_queue.run_repeating(send_busy_day_alert, interval=60, first=25)
    application.job_queue.run_repeating(send_wishlist_reminder, interval=60, first=30)

    while True:
        try:
            logging.info("Запуск в режиме Polling")
            application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            break
        except telegram.error.Conflict:
            logging.warning("Конфликт: другой экземпляр бота ещё работает. Повтор через 30 секунд...")
            time.sleep(30)


if __name__ == "__main__":
    main()
