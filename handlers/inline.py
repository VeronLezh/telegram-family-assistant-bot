import logging

import aiohttp
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes

from config import MAKE_WEBHOOK_URL


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает превью события при вводе @botname <текст>"""
    query = update.inline_query.query.strip()
    if not query:
        await update.inline_query.answer(
            results=[],
            switch_pm_text="Введи: название дата время",
            switch_pm_parameter="inline_help",
            cache_time=0
        )
        return

    result_id = query[:64]

    results = [
        InlineQueryResultArticle(
            id=result_id,
            title=f"📅 Добавить в семейный календарь",
            description=query,
            input_message_content=InputTextMessageContent(
                message_text=f"📅 Добавляю событие в семейный календарь:\n{query}"
            ),
            thumbnail_url="https://www.gstatic.com/images/branding/product/1x/calendar_48dp.png"
        ),
    ]
    await update.inline_query.answer(results, cache_time=0)


async def chosen_inline_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет событие на Make.com когда пользователь выбрал результат."""
    result = update.chosen_inline_result
    event_text = result.result_id
    user = result.from_user

    message_data = {
        "chat_id": user.id,
        "text": f"Событие {event_text}",
        "first_name": user.first_name,
    }

    try:
        if MAKE_WEBHOOK_URL:
            async with aiohttp.ClientSession() as session:
                async with session.post(MAKE_WEBHOOK_URL, json=message_data) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logging.error(f"[INLINE] Ошибка Make.com: {resp.status}, {body}")
                    else:
                        logging.info(f"[INLINE] Событие отправлено в Make.com: {event_text}")
        else:
            logging.warning("[INLINE] MAKE_WEBHOOK_URL не задан")
    except Exception as e:
        logging.error(f"[INLINE] Ошибка при отправке в Make.com: {e}")
