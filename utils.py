import logging

from config import CHAT_IDS_ALL


async def send_and_pin(bot, text: str):
    """Отправляет сообщение всем в CHAT_IDS_ALL и закрепляет его."""
    for chat_id in CHAT_IDS_ALL:
        try:
            msg = await bot.send_message(chat_id=chat_id, text=text)
            await bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
        except Exception as e:
            logging.error(f"Ошибка send_and_pin в чат {chat_id}: {e}")
