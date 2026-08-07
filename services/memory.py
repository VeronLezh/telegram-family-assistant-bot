"""Долговременная память бота — ядро (CORE).

Ядро — короткий текст на пользователя, который подмешивается в системный промпт при
каждом обращении к AI. В нём постоянные факты и предпочтения, а не история разговора:
история живёт в памяти процесса и стирается при рестарте сервиса, ядро — нет.

Хранение как у остальных данных проекта: Google Sheets (вкладка memory_core) с
подстраховкой локальным JSON-файлом.
"""
import json
import logging
import os
from typing import NamedTuple

from config import MEMORY_CORE_MAX_CHARS, MEMORY_FACT_MAX_CHARS, MEMORY_USERS

CORE_FILE = os.path.join(os.path.dirname(__file__), "..", "memory_core.json")


class CoreUpdate(NamedTuple):
    """Итог записи факта в ядро."""
    core: str          # ядро после записи
    dropped: int       # сколько старых строк вытеснено по лимиту
    truncated: bool    # сам факт пришлось обрезать
    duplicate: bool    # такой факт уже был, запись не делалась


def load_cores() -> dict:
    from services.sheets import read_sheet
    # Ячейку таблицы правят руками, поэтому в ней может оказаться что угодно.
    # Не-словарь тут положил бы бота целиком: CORES.get() упал бы на каждом сообщении.
    data = read_sheet("memory_core")
    if isinstance(data, dict):
        return data
    if data is not None:
        logging.error(f"Ядро памяти в таблице не словарь, а {type(data).__name__} — игнорирую")
    try:
        if os.path.exists(CORE_FILE):
            with open(CORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                logging.error(f"Ядро памяти в файле не словарь, а {type(data).__name__}")
    except Exception as e:
        logging.error(f"Ошибка загрузки ядра памяти: {e}")
    return {}


_tab_checked = False


def save_cores(cores: dict):
    from services.sheets import ensure_tab, write_sheet
    global _tab_checked
    # Флаг взводим только при успехе: иначе разовый сбой сети навсегда оставил бы
    # вкладку несозданной, и все записи молча уходили бы в лог до перезапуска.
    if not _tab_checked:
        _tab_checked = ensure_tab("memory_core")
    write_sheet("memory_core", cores)
    try:
        with open(CORE_FILE, "w", encoding="utf-8") as f:
            json.dump(cores, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения ядра памяти: {e}")


# Ключи — строки: JSON не умеет int-ключи, после сохранения они всё равно станут строками.
CORES: dict[str, str] = load_cores()


def _fit(lines: list[str]) -> tuple[list[str], int]:
    """Ужимает ядро до лимита, вытесняя самые старые строки сверху.
    Последнюю строку не трогает никогда: ради неё вызов и происходит, а вытеснив
    её, мы бы стёрли всё ядро в ответ на одно длинное «запомни …».
    Возвращает (оставшиеся строки, сколько вытеснено)."""
    dropped = 0
    while len(lines) > 1 and len("\n".join(lines)) > MEMORY_CORE_MAX_CHARS:
        lines.pop(0)
        dropped += 1
    return lines, dropped


def get_core(user_id: int) -> str:
    if user_id not in MEMORY_USERS:
        return ""
    return CORES.get(str(user_id), "")


def set_core(user_id: int, text: str) -> str:
    """Полностью перезаписывает ядро. Возвращает то, что реально сохранилось."""
    if user_id not in MEMORY_USERS:
        return ""
    lines = [ln.rstrip() for ln in text.strip().split("\n") if ln.strip()]
    lines, _ = _fit(lines)
    # _fit бережёт последнюю строку, поэтому она могла остаться длиннее лимита — режем.
    core = "\n".join(lines)[:MEMORY_CORE_MAX_CHARS].rstrip()
    CORES[str(user_id)] = core
    save_cores(CORES)
    return core


def _clean_fact(fact: str) -> str:
    """Факт — ровно одна строка. Переносы и невидимые символы схлопываем: ядро уезжает
    в системный промпт, и многострочный текст позволил бы подделать его структуру —
    дописать свой заголовок или роль. Портить можно только собственное ядро, но
    защита стоит одной строки."""
    fact = " ".join(fact.split())
    return "".join(ch for ch in fact if ch.isprintable())


def append_core_line(user_id: int, fact: str) -> CoreUpdate:
    """Дописывает факт в конец ядра. Повторный факт не пишется заново."""
    if user_id not in MEMORY_USERS:
        return CoreUpdate("", 0, False, False)
    fact = _clean_fact(fact)
    truncated = len(fact) > MEMORY_FACT_MAX_CHARS
    if truncated:
        fact = fact[:MEMORY_FACT_MAX_CHARS].rstrip() + "…"
    existing = CORES.get(str(user_id), "")
    lines = [ln.rstrip() for ln in existing.split("\n") if ln.strip()]

    new_line = f"- {fact}"
    if any(ln.casefold() == new_line.casefold() for ln in lines):
        # Уже знаем — не плодим строки и не тратим вызов к Sheets.
        return CoreUpdate("\n".join(lines), 0, truncated, True)

    lines.append(new_line)
    lines, dropped = _fit(lines)
    core = "\n".join(lines)
    CORES[str(user_id)] = core
    save_cores(CORES)
    return CoreUpdate(core, dropped, truncated, False)


def clear_core(user_id: int):
    if user_id not in MEMORY_USERS:
        return
    CORES.pop(str(user_id), None)
    save_cores(CORES)
