import json
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

WISHLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "wishlist.json")


def load_wishlist() -> dict:
    from services.sheets import read_sheet
    data = read_sheet("wishlist")
    if data is not None:
        return data
    try:
        if os.path.exists(WISHLIST_FILE):
            with open(WISHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки списка желаний: {e}")
    return {}


def save_wishlist(wishlist: dict):
    from services.sheets import write_sheet
    write_sheet("wishlist", wishlist)
    try:
        with open(WISHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(wishlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения списка желаний: {e}")


WISHLISTS: dict[str, list] = load_wishlist()


def add_wishlist_item(name: str, item: str):
    WISHLISTS.setdefault(name, []).append(item)
    save_wishlist(WISHLISTS)


def get_wishlist_text(name: str) -> str:
    items = WISHLISTS.get(name, [])
    if not items:
        return f"📭 У {name} пока нет списка желаний."
    lines = "\n".join(f"{i + 1}. {it}" for i, it in enumerate(items))
    return f"🎁 Список желаний {name}:\n\n{lines}"


def get_all_wishlists_text() -> str:
    if not WISHLISTS:
        return "📭 Пока никто не добавил список желаний."
    return "\n\n".join(get_wishlist_text(name) for name in WISHLISTS)


async def wishlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        name = " ".join(context.args)
        await update.message.reply_text(get_wishlist_text(name))
    else:
        await update.message.reply_text(get_all_wishlists_text())
