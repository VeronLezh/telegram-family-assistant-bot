import json
import logging
import os

SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")


def _get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    google_json = os.getenv("GOOGLE_CALENDAR_JSON")
    if google_json:
        info = json.loads(google_json)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    else:
        credentials_path = os.path.join(
            os.path.dirname(__file__), "..", "service-account.json"
        )
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    return build("sheets", "v4", credentials=credentials)


def read_sheet(tab: str) -> any:
    if not SHEETS_ID:
        return None
    try:
        service = _get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEETS_ID,
            range=f"{tab}!A1"
        ).execute()
        values = result.get("values", [])
        if values and values[0]:
            return json.loads(values[0][0])
    except Exception as e:
        logging.error(f"Ошибка чтения Google Sheets ({tab}): {e}")
    return None


def write_sheet(tab: str, data: any):
    if not SHEETS_ID:
        return
    try:
        service = _get_service()
        service.spreadsheets().values().update(
            spreadsheetId=SHEETS_ID,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [[json.dumps(data, ensure_ascii=False)]]}
        ).execute()
    except Exception as e:
        logging.error(f"Ошибка записи Google Sheets ({tab}): {e}")
