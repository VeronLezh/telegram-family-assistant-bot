import json
import logging
import os
from datetime import datetime, timedelta

from config import CALENDAR_PERSONAL_ID, CALENDAR_FAMILY_ID, MOSCOW_TZ


def get_calendar_events(days_ahead=7, calendar_type="personal"):
    """
    Получение событий из Google Calendar.
    Поддерживается:
    - локальный файл service-account.json рядом с bot.py
    - переменная окружения GOOGLE_CALENDAR_JSON (содержит JSON-строку сервис-аккаунта)
    calendar_type: "personal" или "family"
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from datetime import timezone

        if calendar_type == "family":
            calendar_id = CALENDAR_FAMILY_ID
            cal_name = "Семейный"
        else:
            calendar_id = CALENDAR_PERSONAL_ID
            cal_name = "Личный"

        credentials = None
        google_json = os.getenv("GOOGLE_CALENDAR_JSON")
        if google_json:
            try:
                info = json.loads(google_json)
                credentials = service_account.Credentials.from_service_account_info(
                    info, scopes=["https://www.googleapis.com/auth/calendar.readonly"]
                )
            except Exception as e:
                logging.error(f"Ошибка парсинга GOOGLE_CALENDAR_JSON: {e}")
                return "❌ Некорректный формат GOOGLE_CALENDAR_JSON."
        else:
            credentials_path = os.path.join(os.path.dirname(__file__), "..", "service-account.json")
            if not os.path.exists(credentials_path):
                return f"❌ Файл {credentials_path} не найден и GOOGLE_CALENDAR_JSON не задан. Интеграция с календарем недоступна."
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/calendar.readonly"]
            )

        service = build("calendar", "v3", credentials=credentials)

        now_utc = datetime.now(timezone.utc)
        time_min = now_utc.isoformat()
        time_max = (now_utc + timedelta(days=days_ahead)).isoformat()

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return f"📅 В календаре «{cal_name}» на ближайшие {days_ahead} дней событий нет."

        events_list = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "Без названия")

            if "T" in start:
                try:
                    event_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                except Exception:
                    event_time = datetime.fromisoformat(start.split(".")[0].replace("Z", "+00:00"))
                event_time = event_time.astimezone(MOSCOW_TZ)
                time_str = event_time.strftime("%d.%m %H:%M")
            else:
                time_str = datetime.fromisoformat(start).strftime("%d.%m")

            events_list.append(f"• {time_str}: {summary}")

        return f"📅 Ближайшие события в календаре «{cal_name}»:\n\n" + "\n".join(events_list[:10])

    except ImportError:
        return "❌ Библиотеки google-auth и google-api-python-client не установлены."
    except Exception as e:
        logging.error(f"Ошибка Google Calendar: {e}")
        return f"❌ Ошибка доступа к календарю: {str(e)}"
