import logging
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Московское время ---
try:
    import zoneinfo
    MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")
except ImportError:
    from datetime import timezone
    MOSCOW_TZ = timezone(timedelta(hours=3))

# --- Пользователи (пример: демо-данные для портфолио) ---
USER_ANNA = 111111111
USER_BORIS = 222222222
USER_VIKTOR = 333333333
USER_GALYA = 444444444

CHAT_IDS_ALL = [USER_ANNA, USER_BORIS, USER_VIKTOR, USER_GALYA]

# --- Права доступа ---
ADMIN_USERS = [USER_ANNA]
CALENDAR_PERSONAL_USERS = [USER_ANNA]
CALENDAR_FAMILY_USERS = [USER_ANNA, USER_BORIS, USER_GALYA]

# --- Идентификаторы календарей ---
CALENDAR_PERSONAL_ID = "example@gmail.com"
CALENDAR_FAMILY_ID = "family_calendar_id@group.calendar.google.com"

# --- Env vars ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN не найден в переменных окружения")
    exit(1)

if not GROQ_API_KEY:
    logging.error("GROQ_API_KEY не найден в переменных окружения")
    exit(1)

# --- Дни рождения (демо-данные) ---
# (имя, месяц, день, год рождения)
BIRTHDAYS = [
    ("Анна",    3, 15, 1990),
    ("Борис",   6, 21, 1988),
    ("Виктор",  9, 10, 2012),
    ("Галя",    11, 3, 2019),
]

USER_ID_TO_NAME = {
    USER_ANNA: "Анна",
    USER_BORIS: "Борис",
    USER_VIKTOR: "Виктор",
    USER_GALYA: "Галя",
}
NAME_TO_USER_ID = {name: uid for uid, name in USER_ID_TO_NAME.items()}

# Несовершеннолетние — для них AI не шутит на взрослые темы ни при каких обстоятельствах
MINOR_USERS = [USER_VIKTOR, USER_GALYA]

# --- Учебный год ---
# Летние каникулы: в этот период школьное расписание не актуально
# (месяц, день) начала и конца — конец включительно
SCHOOL_SUMMER_BREAK_START = (6, 1)
SCHOOL_SUMMER_BREAK_END = (8, 31)

# --- Список желаний ---
WISHLIST_REMINDER_DAYS = 5  # за сколько дней до ДР слать список остальным

# Интересы для AI-подсказок подарков, если список желаний пуст — заполните по вкусу
WISHLIST_INTERESTS = {
    "Анна": "",
    "Борис": "",
    "Виктор": "",
    "Галя": "",
}

# ID эффекта 🎉 конфетти (Telegram Bot API)
EFFECT_CONFETTI = "5046509860389126442"

# --- Долговременная память (CORE) ---
# Ядро памяти подмешивается в системный промпт при КАЖДОМ обращении к AI,
# поэтому держим его коротким — иначе растут расход токенов и время ответа.
MEMORY_CORE_MAX_CHARS = 1200

# Потолок на один факт. Без него длинное «запомни …» (вставленный кусок переписки)
# вытеснило бы из ядра вообще всё остальное.
MEMORY_FACT_MAX_CHARS = MEMORY_CORE_MAX_CHARS // 2

# Кому бот ведёт ядро памяти. Убери user_id из списка — и про него ничего не хранится.
MEMORY_USERS = [USER_ANNA, USER_BORIS, USER_VIKTOR, USER_GALYA]

# --- AI промпты по пользователям ---
AI_PROMPTS_BY_USER = {
    USER_ANNA: "Ты — личный ассистент Анны, помогай ей с расписанием и ответами. Весело общайся, но по делу. Можно немного пошутить и потролить",
    USER_BORIS: "Ты — личный ассистент Бориса, помогай ему с расписанием. Отвечай по делу, немного шуток и троллинга.",
    USER_VIKTOR: "Ты — личный ассистент Виктора, ему 14 лет, помогай ему с расписанием и ответами. Общайся дружелюбно, можно немного пошутить, но по-доброму и без пошлости — как со своим ребёнком.",
    USER_GALYA: "Ты — личный ассистент Гали, ей 7 лет, помогай ей с расписанием и ответами. Общайся тепло и простыми словами, шути только по-доброму и по-детски.",
}
