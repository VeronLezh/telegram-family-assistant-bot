# Telegram Family Assistant Bot (Portfolio Demo)

> Демо-версия проекта для портфолио — личные данные анонимизированы (имена, Telegram ID, email и ID календарей — вымышленные). Оригинальный бот работает в семье автора.

Семейный Telegram-бот на python-telegram-bot (v21+) с AI-ассистентом, расписаниями, напоминаниями и интеграцией с Google Calendar.

## Stack

- **Python 3.11+**, async
- **python-telegram-bot** v21+ (async API)
- **Groq** (LLM: qwen/qwen3-32b, STT: whisper-large-v3-turbo)
- **Google Calendar API** (OAuth service account)
- **Flask** — healthcheck-сервер (запускается в daemon-потоке)
- **Make.com** — webhook для обработки сообщений
- **Heroku** — деплой (worker dyno, `Procfile`)

## Возможности

- AI-чат с контекстом разговора (голос, текст, фото)
- Расписание занятий и тренировок по дням/детям, с редактированием командами и на естественном языке
- Умные и периодические напоминания (разовые, ежедневные, ежемесячные)
- Уведомление о загруженном дне
- Список подарочных пожеланий с AI-парсингом и напоминанием перед днём рождения
- Интеграция с Google Calendar (личный и семейный календарь)
- Рассылка сообщений всем пользователям (админ)

## Run

```bash
python bot.py
```

Бот запускается в режиме polling. Flask healthcheck стартует автоматически в фоновом потоке.

## Env vars

Скопируйте `.env.example` в `.env` и заполните своими значениями:

- `BOT_TOKEN` — Telegram Bot API token
- `GROQ_API_KEY` — ключ Groq API
- `MAKE_WEBHOOK_URL` — URL вебхука Make.com (опционально)
- `PORT` — порт Flask (по умолчанию 5000)

Для работы с Google Calendar также нужен файл сервисного аккаунта Google (см. `services/calendar.py`) — положите его в корень проекта и укажите путь в коде/переменной окружения по своему усмотрению. В этом демо-репозитории файл с реальными credentials не публикуется.

## Project structure

```
bot.py              — точка входа, регистрация хендлеров и job queue
config.py           — конфиг: пользователи, права, календари, промпты (демо-данные)
server.py           — Flask healthcheck
handlers/
  messages.py       — обработка текстовых и голосовых сообщений
  schedule.py       — расписание занятий (по дням/детям)
  trainings.py      — расписание тренировок
  menu.py           — главное меню (inline-кнопки)
  admin.py          — admin help-команды
  inline.py         — inline-режим бота
services/
  ai.py             — Groq LLM (чат, парсинг напоминаний, транскрипция)
  calendar.py       — Google Calendar API
  sheets.py         — синхронизация данных с Google Sheets
reminders/
  jobs.py           — периодические задачи (тренировки, напоминания, ДР)
  storage.py        — хранение напоминаний
  personal.py       — персональные напоминания
  wishlist.py       — список подарочных пожеланий
```

## Conventions

- Язык кода: Python. Комментарии и строки — на русском
- Все времена — московские (`Europe/Moscow`), см. `config.MOSCOW_TZ`
- Пользователи определяются по Telegram user ID (см. `config.py`)
- Права доступа: `ADMIN_USERS`, `CALENDAR_PERSONAL_USERS`, `CALENDAR_FAMILY_USERS`
- AI-промпты привязаны к пользователям через `AI_PROMPTS_BY_USER`
- История чата AI хранится in-memory (до 10 сообщений на пользователя)

## License

MIT
