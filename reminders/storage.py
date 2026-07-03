import json
import logging
import os

SENT_REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "sent_reminders.json")


def load_sent_reminders() -> set:
    try:
        with open(SENT_REMINDERS_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_sent_reminders(reminders: set):
    """Мержит reminders с уже сохранёнными на диске и записывает результат.
    Так как это синхронная функция без await, asyncio не может прервать её
    между чтением и записью — гонка данных исключена."""
    try:
        existing = load_sent_reminders()
        merged = existing | reminders
        with open(SENT_REMINDERS_FILE, "w") as f:
            json.dump(list(merged), f)
    except Exception as e:
        logging.error(f"Ошибка сохранения sent_reminders: {e}")
