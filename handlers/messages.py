import logging
import os
import tempfile
from datetime import datetime

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from config import MAKE_WEBHOOK_URL, MOSCOW_TZ, USER_ID_TO_NAME
from services.ai import (
    ai_answer, transcribe_voice, analyze_image,
    parse_reminder_request, parse_training_delete, parse_wishlist_add, groq_client
)
from reminders.personal import add_smart_reminder
from reminders.wishlist import add_wishlist_item

REMINDER_TRIGGERS = ["напомни", "напомнить", "поставь напоминание", "remind me"]
TRAINING_DELETE_TRIGGERS = ["удали тренировку", "убери тренировку", "удалить тренировку", "убрать тренировку"]
WISHLIST_TRIGGERS = [
    "хочу на день рождения", "хочу на др", "хочу в подарок", "хочу получить в подарок",
    "добавь в список желаний", "добавь в вишлист", "запиши в список желаний"
]


def _is_reminder_request(text: str) -> bool:
    t = text.lower().strip()
    return any(t.startswith(kw) or f" {kw}" in t for kw in REMINDER_TRIGGERS)


def _is_training_delete_request(text: str) -> bool:
    t = text.lower().strip()
    return any(kw in t for kw in TRAINING_DELETE_TRIGGERS)


def _is_wishlist_request(text: str) -> bool:
    t = text.lower().strip()
    return any(kw in t for kw in WISHLIST_TRIGGERS)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.effective_chat else None
    text = update.message.text if update.message else None
    first_name = update.effective_user.first_name if update.effective_user else None
    user_id = update.effective_user.id if update.effective_user else None

    message_data = {
        "chat_id": chat_id,
        "text": text,
        "first_name": first_name
    }

    try:
        if MAKE_WEBHOOK_URL:
            async with aiohttp.ClientSession() as session:
                async with session.post(MAKE_WEBHOOK_URL, json=message_data) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logging.error(f"Ошибка отправки в Make.com: статус {resp.status}, тело: {body}")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения в Make.com: {e}")

    if text and chat_id:
        await _process_text_intent(update, text, chat_id, user_id)


async def _process_text_intent(update: Update, text: str, chat_id: int, user_id: int):
    """Разбирает распознанный текст (из текстового или голосового сообщения) на намерения:
    напоминание, удаление тренировки, список желаний — либо обычный AI-ответ."""
    if _is_reminder_request(text):
        try:
            now_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M")
            parsed = await parse_reminder_request(text, now_str)
            if parsed and "datetime" in parsed:
                add_smart_reminder({
                    "datetime": parsed["datetime"],
                    "text": parsed["text"],
                    "chat_id": chat_id
                })
                await update.message.reply_text(
                    f"✅ Напоминание поставлено: {parsed['text']}\n🕐 {parsed['datetime']}"
                )
            else:
                await update.message.reply_text("⚠️ Не смог разобрать время напоминания. Попробуй уточнить.")
        except Exception as e:
            logging.error(f"Ошибка создания напоминания: {e}")
            await update.message.reply_text("⚠️ Ошибка при создании напоминания.")
        return

    if _is_training_delete_request(text):
        try:
            from handlers.trainings import TRAININGS, remove_training_by_time
            parsed = await parse_training_delete(text, TRAININGS)
            if parsed and "error" not in parsed:
                removed = remove_training_by_time(parsed["child"], parsed["day"], parsed["time"])
                if removed:
                    await update.message.reply_text(
                        f"✅ Удалено: {parsed['child']} — {parsed['day']}: {removed}"
                    )
                else:
                    await update.message.reply_text("❌ Тренировка не найдена. Проверь имя и день.")
            else:
                await update.message.reply_text("⚠️ Не могу определить какую тренировку удалить. Уточни.")
        except Exception as e:
            logging.error(f"Ошибка удаления тренировки: {e}")
            await update.message.reply_text("⚠️ Ошибка при удалении тренировки.")
        return

    if _is_wishlist_request(text):
        try:
            name = USER_ID_TO_NAME.get(user_id)
            if not name:
                await update.message.reply_text("⚠️ Не могу определить, кому добавить пожелание.")
                return
            parsed = await parse_wishlist_add(text)
            if parsed and "item" in parsed:
                add_wishlist_item(name, parsed["item"])
                await update.message.reply_text(f"✅ Добавлено в список желаний: {parsed['item']}")
            else:
                await update.message.reply_text("⚠️ Не смог понять, что добавить в список желаний. Уточни.")
        except Exception as e:
            logging.error(f"Ошибка добавления в список желаний: {e}")
            await update.message.reply_text("⚠️ Ошибка при добавлении в список желаний.")
        return

    try:
        if not groq_client:
            ai_reply = "⚠️ AI сервис временно недоступен."
        else:
            await update.message.reply_text("⏳ Думаю...")
            ai_reply = await ai_answer(text, user_id)
        await update.message.reply_text(ai_reply)
    except Exception as e:
        logging.error(f"Ошибка при обработке AI ответа: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при обращении к AI.")


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    prompt = update.message.caption or "Опиши что на фото."

    await update.message.reply_text("🔍 Анализирую фото...")

    tmp_path = None
    try:
        photo = update.message.photo[-1]  # наибольшее разрешение
        photo_file = await photo.get_file()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        await photo_file.download_to_drive(tmp_path)

        reply = await analyze_image(tmp_path, prompt, user_id)
        await update.message.reply_text(reply)

    except Exception as e:
        logging.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text("⚠️ Ошибка при анализе фото.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None

    await update.message.reply_text("🎙️ Слушаю...")

    tmp_path = None
    try:
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await voice_file.download_to_drive(tmp_path)

        text = await transcribe_voice(tmp_path)
        if not text:
            await update.message.reply_text("⚠️ Не удалось распознать голосовое сообщение.")
            return

        await update.message.reply_text(f"📝 *Ты сказал:* {text}", parse_mode="Markdown")

        await _process_text_intent(update, text, chat_id, user_id)

    except Exception as e:
        logging.error(f"Ошибка обработки голосового сообщения: {e}")
        await update.message.reply_text("⚠️ Ошибка при обработке голосового сообщения.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
