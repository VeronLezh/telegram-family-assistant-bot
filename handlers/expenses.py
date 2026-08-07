import logging
import re
from datetime import datetime

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import MAKE_WEBHOOK_URL, MOSCOW_TZ

EXPENSE_CATEGORIES = ["ЖКХ", "Интернет", "Телефон/связь"]
CHILDREN = ["Виктор", "Галя"]

# Кого из пользователей ждём сумму: user_id -> категория. In-memory, сбрасывается при рестарте —
# это нормально, диалог короткий и переживать рестарт ему не нужно.
PENDING_EXPENSE: dict[int, str] = {}

# Кого из пользователей ждём "на что и сколько" по ребёнку: user_id -> имя ребёнка.
PENDING_KIDS_EXPENSE: dict[int, str] = {}


async def _post_to_make(update: Update, message_data: dict, fallback_text: str) -> None:
    """Отправляет сообщение в Make.com. Подтверждение об успехе шлёт сам сценарий Make —
    здесь бот отвечает только если вебхук не настроен или запрос не прошёл."""
    try:
        if not MAKE_WEBHOOK_URL:
            logging.warning("[EXPENSES] MAKE_WEBHOOK_URL не задан")
            await update.message.reply_text(fallback_text)
            return

        async with aiohttp.ClientSession() as session:
            async with session.post(MAKE_WEBHOOK_URL, json=message_data) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logging.error(f"[EXPENSES] Ошибка Make.com: {resp.status}, {body}")
                    await update.message.reply_text("⚠️ Не удалось записать трату, попробуйте позже.")
    except Exception as e:
        logging.error(f"[EXPENSES] Ошибка при отправке в Make.com: {e}")
        await update.message.reply_text("⚠️ Не удалось записать трату, попробуйте позже.")


async def expenses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"💸 {category}", callback_data=f"expense_{category}")]
        for category in EXPENSE_CATEGORIES
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Выберите категорию расхода:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def expenses_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.removeprefix("expense_")
    user_id = query.from_user.id if query.from_user else None
    if category not in EXPENSE_CATEGORIES or user_id is None:
        return
    PENDING_EXPENSE[user_id] = category
    await query.edit_message_text(f"💸 {category}: введите сумму в рублях (например, 8500)")


async def try_handle_expense_amount(update: Update, text: str, user_id: int) -> bool:
    """Если для пользователя ждём сумму расхода — парсит её и отправляет в Make.com.
    Возвращает True, если сообщение обработано в рамках этого диалога (и его не нужно
    отдавать дальше в общий AI-обработчик)."""
    category = PENDING_EXPENSE.get(user_id)
    if not category:
        return False

    if text.strip().lower() in ("отмена", "cancel"):
        del PENDING_EXPENSE[user_id]
        await update.message.reply_text("Отменено.")
        return True

    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        await update.message.reply_text("⚠️ Не нашёл сумму. Введите число, например: 8500 (или «отмена»)")
        return True

    amount = match.group(0).replace(",", ".")
    del PENDING_EXPENSE[user_id]

    first_name = update.effective_user.first_name if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    message_data = {
        "chat_id": chat_id,
        "text": f"{category} {amount}",
        "first_name": first_name,
        "type": "expense_utility",
        "category": category,
        "amount": amount,
        "date": datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d"),
        "who": first_name,
    }
    await _post_to_make(update, message_data, f"✅ Записал: {category} — {amount} ₽")
    return True


async def kids_expenses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"👧 {child}", callback_data=f"kidsexpense_{child}")]
        for child in CHILDREN
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Выберите ребёнка:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def kids_expenses_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child = query.data.removeprefix("kidsexpense_")
    user_id = query.from_user.id if query.from_user else None
    if child not in CHILDREN or user_id is None:
        return
    PENDING_KIDS_EXPENSE[user_id] = child
    await query.edit_message_text(f"👧 {child}: на что и сколько? Например: секция 1500")


async def try_handle_kids_expense_amount(update: Update, text: str, user_id: int) -> bool:
    """Если для пользователя ждём «на что и сколько» по ребёнку — собирает сообщение
    в том же формате, что и ручной ввод («Дети <Имя> <на что> <сумма>»), и отправляет
    в Make.com — там уже есть готовая ветка, разбирающая именно такой текст."""
    child = PENDING_KIDS_EXPENSE.get(user_id)
    if not child:
        return False

    if text.strip().lower() in ("отмена", "cancel"):
        del PENDING_KIDS_EXPENSE[user_id]
        await update.message.reply_text("Отменено.")
        return True

    match = re.match(r"^(?P<activity>.+?)\s+(?P<amount>\d+(?:[.,]\d+)?)$", text.strip())
    if not match:
        await update.message.reply_text(
            "⚠️ Не понял. Напишите на что и сумму, например: секция 1500 (или «отмена»)"
        )
        return True

    activity = match.group("activity")
    amount = match.group("amount").replace(",", ".")
    del PENDING_KIDS_EXPENSE[user_id]

    first_name = update.effective_user.first_name if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    message_data = {
        "chat_id": chat_id,
        "text": f"Дети {child} {activity} {amount}",
        "first_name": first_name,
    }
    await _post_to_make(update, message_data, f"✅ Записал: {child} — {activity} — {amount} ₽")
    return True
