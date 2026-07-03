import logging
import re
from datetime import date, datetime, timedelta

import telegram.error
from telegram.ext import ContextTypes

from config import (
    CHAT_IDS_ALL, MOSCOW_TZ, BIRTHDAYS, EFFECT_CONFETTI,
    WISHLIST_REMINDER_DAYS, WISHLIST_INTERESTS, NAME_TO_USER_ID
)
from handlers import schedule as schedule_module
from handlers import trainings
from reminders.personal import PERSONAL_REMINDERS, PERSONAL_REMINDERS_DYNAMIC, DAILY_REMINDERS, SMART_REMINDERS_DYNAMIC, save_smart_reminders
from reminders.storage import load_sent_reminders, save_sent_reminders
from reminders.wishlist import WISHLISTS
from services.ai import groq_client, _no_think, _strip_think, generate_gift_ideas

BUSY_DAY_LESSON_THRESHOLD = 7
BUSY_DAY_LESSON_WITH_TRAINING_THRESHOLD = 5


def now_moscow():
    return datetime.now(MOSCOW_TZ)


def should_send_notifications() -> bool:
    current_hour = now_moscow().hour
    return 13 <= current_hour < 21


async def safe_send_message(bot, chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except telegram.error.TelegramError as e:
        logging.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Неизвестная ошибка при отправке сообщения в чат {chat_id}: {e}")


async def send_training_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминаний о тренировках и дополнительных занятиях"""
    if not should_send_notifications():
        return

    trainings.load_trainings()

    now = now_moscow()
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    today_ru = days_ru[now.weekday()]
    current_date_str = now.strftime("%Y-%m-%d")
    sent_reminders = {entry for entry in load_sent_reminders() if entry.startswith(current_date_str)}

    special_classes = ["Английский язык", "английский"]

    for child, schedule in trainings.TRAININGS.items():
        if today_ru in schedule:
            for time_range in schedule[today_ru]:
                try:
                    match = re.search(r"\d{1,2}[:.]\d{2}", time_range)
                    if not match:
                        continue

                    start_time_str = match.group().replace('.', ':')
                    hour, minute = map(int, start_time_str.split(":"))

                    start_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    reminder_time = start_time - timedelta(hours=1)
                    time_diff = abs((now - reminder_time).total_seconds())

                    if time_diff > 300:
                        continue

                    if "🎒" in time_range:
                        lesson_name = time_range.split("🎒")[-1].strip()
                    elif "📘" in time_range:
                        lesson_name = time_range.split("📘")[-1].strip()
                    else:
                        lesson_name = "тренировка"

                    if any(s.lower() in lesson_name.lower() for s in special_classes):
                        message = f"⏰ {lesson_name} начнется через 1 час в {start_time_str}."
                    else:
                        message = f"⏰ Напоминание: тренировка {child} начнется через 1 час в {start_time_str}."

                    reminder_id = f"{current_date_str}_{child}_{start_time_str}"
                    if reminder_id not in sent_reminders:
                        for chat_id in CHAT_IDS_ALL:
                            await safe_send_message(context.bot, chat_id, message)
                            logging.info(f"[REMINDER] Отправлено: {message} (child={child})")
                        sent_reminders.add(reminder_id)
                        save_sent_reminders(sent_reminders)

                except Exception as e:
                    logging.error(f"Ошибка обработки напоминания '{time_range}' для {child}: {e}")
                    continue

    for reminder in DAILY_REMINDERS:
        try:
            reminder_time = now.replace(
                hour=int(reminder["time"].split(":")[0]),
                minute=int(reminder["time"].split(":")[1]),
                second=0,
                microsecond=0
            )
            time_diff = abs((now - reminder_time).total_seconds())
            reminder_id = f"{current_date_str}_daily_{reminder['chat_id']}_{reminder['time']}"
            if time_diff <= 30 and reminder_id not in sent_reminders:
                await safe_send_message(context.bot, reminder["chat_id"], reminder["text"])
                logging.info(f"[REMINDER] Ежедневное напоминание: {reminder['text']}")
                sent_reminders.add(reminder_id)
                save_sent_reminders(sent_reminders)
        except Exception as e:
            logging.error(f"Ошибка обработки ежедневного напоминания {reminder}: {e}")
            continue


async def send_personal_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет персональные напоминания с точностью ±5 минут для Анны."""
    if not should_send_notifications():
        return
    now = now_moscow()
    current_date_str = now.strftime("%Y-%m-%d")
    sent_reminders = {entry for entry in load_sent_reminders() if entry.startswith(current_date_str)}

    CHECK_WINDOW_SEC = 300

    for reminder in (PERSONAL_REMINDERS + PERSONAL_REMINDERS_DYNAMIC):
        if "day" in reminder:
            if now.day != reminder["day"]:
                continue
        try:
            hour, minute = map(int, reminder["time"].split(":"))
            reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            time_diff = abs((now - reminder_time).total_seconds())
            reminder_id = f"{current_date_str}_{reminder['time']}_{reminder['text']}"
            if time_diff <= CHECK_WINDOW_SEC and reminder_id not in sent_reminders:
                await safe_send_message(context.bot, reminder["chat_id"], reminder["text"])
                logging.info(f"Отправлено личное напоминание: {reminder}")
                sent_reminders.add(reminder_id)
                save_sent_reminders(sent_reminders)
        except Exception as e:
            logging.error(f"Ошибка обработки личного напоминания {reminder}: {e}")
            continue


async def send_dynamic_reminder(context: ContextTypes.DEFAULT_TYPE):
    if not should_send_notifications():
        return
    now = now_moscow()
    if not (now.hour == 14 and now.minute == 0):
        return

    current_date_str = now.strftime("%Y-%m-%d")
    sent_reminders = {entry for entry in load_sent_reminders() if entry.startswith(current_date_str)}

    for chat_id in CHAT_IDS_ALL:
        reminder_id = f"{current_date_str}_dynamic_{chat_id}"
        if reminder_id in sent_reminders:
            continue
        try:
            if not groq_client:
                text = "⚠️ AI сервис временно недоступен."
            else:
                response = groq_client.chat.completions.create(
                    model="qwen/qwen3-32b",
                    messages=_no_think([
                        {
                            "role": "system",
                            "content": "Ты генерируешь короткие, позитивные, мотивационные сообщения строго на русском языке для семейного чата."
                        },
                        {"role": "user", "content": "/no_think Напиши мотивационное сообщение дня."}
                    ]),
                    temperature=0.7,
                    max_tokens=120
                )
                text = _strip_think(response.choices[0].message.content)
            await safe_send_message(context.bot, chat_id, text)
            logging.info(f"Отправлено динамическое напоминание (Groq) в чат {chat_id}: {text}")
            sent_reminders.add(reminder_id)
            save_sent_reminders(sent_reminders)
        except Exception as e:
            logging.error(f"Ошибка при отправке динамического напоминания в чат {chat_id}: {e}")


async def send_smart_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = now_moscow()
    to_remove = []
    for reminder in list(SMART_REMINDERS_DYNAMIC):
        try:
            reminder_dt = datetime.fromisoformat(reminder["datetime"]).replace(tzinfo=MOSCOW_TZ)
            if abs((now - reminder_dt).total_seconds()) <= 60:
                await safe_send_message(context.bot, reminder["chat_id"], f"⏰ {reminder['text']}")
                logging.info(f"[SMART REMINDER] Отправлено: {reminder['text']}")
                to_remove.append(reminder)
        except Exception as e:
            logging.error(f"Ошибка smart reminder: {e}")
    if to_remove:
        for r in to_remove:
            SMART_REMINDERS_DYNAMIC.remove(r)
        save_smart_reminders(SMART_REMINDERS_DYNAMIC)


def _find_trainings_for_child(child: str, day: str) -> list[str]:
    """Ищет тренировки ребёнка на день, учитывая расхождения в написании имени (Виктор/Виктор)."""
    for name, schedule in trainings.TRAININGS.items():
        if name.replace("ё", "е") == child.replace("ё", "е"):
            return schedule.get(day, [])
    return []


async def send_busy_day_alert(context: ContextTypes.DEFAULT_TYPE):
    """Утреннее предупреждение о загруженном дне: много уроков и/или тренировка вечером."""
    now = now_moscow()
    if not (now.hour == 8 and now.minute == 0):
        return

    schedule_module.load_schedule()
    trainings.load_trainings()

    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    today_ru = days_ru[now.weekday()]
    current_date_str = now.strftime("%Y-%m-%d")
    sent_reminders = {entry for entry in load_sent_reminders() if entry.startswith(current_date_str)}

    for child, week_schedule in schedule_module.SCHEDULES.items():
        try:
            lessons = week_schedule.get(today_ru, [])
            lesson_count = len(lessons)
            training_times = _find_trainings_for_child(child, today_ru)

            is_busy = (
                lesson_count >= BUSY_DAY_LESSON_THRESHOLD
                or (lesson_count >= BUSY_DAY_LESSON_WITH_TRAINING_THRESHOLD and training_times)
            )
            if not is_busy:
                continue

            reminder_id = f"{current_date_str}_busyday_{child}"
            if reminder_id in sent_reminders:
                continue

            message = f"📌 У {child} сегодня плотный день: {lesson_count} уроков"
            if training_times:
                message += f" + тренировка в {', '.join(training_times)}"
            message += ". Не забудьте форму/учебники заранее!"

            for chat_id in CHAT_IDS_ALL:
                await safe_send_message(context.bot, chat_id, message)
            logging.info(f"[BUSY DAY] Отправлено предупреждение: {child}, {lesson_count} уроков")
            sent_reminders.add(reminder_id)
            save_sent_reminders(sent_reminders)
        except Exception as e:
            logging.error(f"Ошибка обработки busy day alert для {child}: {e}")
            continue


async def send_birthday_wishes(context: ContextTypes.DEFAULT_TYPE):
    """Поздравление с днём рождения в 9:00 с эффектом конфетти."""
    now = now_moscow()
    if not (now.hour == 9 and now.minute == 0):
        return

    current_date_str = now.strftime("%Y-%m-%d")
    sent_reminders = {entry for entry in load_sent_reminders() if entry.startswith(current_date_str)}

    for name, month, day, birth_year in BIRTHDAYS:
        if now.month != month or now.day != day:
            continue

        reminder_id = f"{current_date_str}_birthday_{name}"
        if reminder_id in sent_reminders:
            continue

        age = now.year - birth_year
        text = f"🎂 Сегодня день рождения — {name}! Исполняется {age} лет. Поздравляем! 🎉"

        for chat_id in CHAT_IDS_ALL:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    message_effect_id=EFFECT_CONFETTI
                )
                logging.info(f"[BIRTHDAY] Поздравление отправлено: {name}, {age} лет")
            except Exception as e:
                logging.error(f"Ошибка отправки поздравления {name} в чат {chat_id}: {e}")

        sent_reminders.add(reminder_id)
        save_sent_reminders(sent_reminders)


async def send_wishlist_reminder(context: ContextTypes.DEFAULT_TYPE):
    """За WISHLIST_REMINDER_DAYS дней до ДР шлёт остальным список желаний именинника
    (или AI-идеи подарков, если список пуст). Самому имениннику не отправляется."""
    now = now_moscow()
    if not (now.hour == 10 and now.minute == 0):
        return

    today = now.date()
    current_date_str = now.strftime("%Y-%m-%d")
    sent_reminders = {entry for entry in load_sent_reminders() if entry.startswith(current_date_str)}

    for name, month, day, birth_year in BIRTHDAYS:
        try:
            target_year = today.year
            target = date(target_year, month, day)
            if target < today:
                target = date(target_year + 1, month, day)
            days_left = (target - today).days

            if days_left != WISHLIST_REMINDER_DAYS:
                continue

            reminder_id = f"{current_date_str}_wishlist_{name}"
            if reminder_id in sent_reminders:
                continue

            items = WISHLISTS.get(name, [])
            if items:
                lines = "\n".join(f"• {it}" for it in items)
                message = f"🎁 Через {WISHLIST_REMINDER_DAYS} дн. день рождения у {name}. Список желаний:\n\n{lines}"
            else:
                age = target.year - birth_year
                interests = WISHLIST_INTERESTS.get(name, "")
                ideas = await generate_gift_ideas(name, age, interests)
                if ideas:
                    message = (
                        f"🎁 Через {WISHLIST_REMINDER_DAYS} дн. день рождения у {name}. "
                        f"Список желаний пуст, вот идеи от AI:\n\n{ideas}"
                    )
                else:
                    message = (
                        f"🎁 Через {WISHLIST_REMINDER_DAYS} дн. день рождения у {name}, "
                        "а список желаний пуст — можно подсказать что подарить!"
                    )

            birthday_person_id = NAME_TO_USER_ID.get(name)
            recipients = [cid for cid in CHAT_IDS_ALL if cid != birthday_person_id]
            for chat_id in recipients:
                await safe_send_message(context.bot, chat_id, message)
            logging.info(f"[WISHLIST] Отправлено напоминание о списке желаний: {name}")
            sent_reminders.add(reminder_id)
            save_sent_reminders(sent_reminders)
        except Exception as e:
            logging.error(f"Ошибка обработки wishlist reminder для {name}: {e}")
            continue
