from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
_SERVICE_ACCOUNT_FILE_RAW = os.environ.get("SERVICE_ACCOUNT_FILE", "")
SERVICE_ACCOUNT_FILE = (
    str((Path.cwd() / _SERVICE_ACCOUNT_FILE_RAW).resolve())
    if _SERVICE_ACCOUNT_FILE_RAW and not os.path.isabs(_SERVICE_ACCOUNT_FILE_RAW)
    else _SERVICE_ACCOUNT_FILE_RAW
)
CALENDAR_IDS = [
    cid.strip()
    for cid in os.environ.get(
        "CALENDAR_IDS",
        "en.norwegian#holiday@group.v.calendar.google.com",
    ).split(",")
    if cid.strip()
]
FOREGROUND_COLOR = "#ffffff"
BACKGROUND_COLOR = "#4285f4"
_CALENDAR_PALETTE = [
    ("#ab47bc", "#ffffff"),
    ("#0f9d58", "#ffffff"),
    ("#ff7043", "#ffffff"),
    ("#5c6bc0", "#ffffff"),
    ("#00acc1", "#ffffff"),
    ("#4285f4", "#ffffff"),
    ("#db4437", "#ffffff"),
    ("#f4b400", "#1a1a2e"),
]


def _calendar_color(cal_id: str) -> tuple[str, str]:
    idx = CALENDAR_IDS.index(cal_id) if cal_id in CALENDAR_IDS else (
        int(__import__("hashlib").md5(cal_id.encode()).hexdigest(), 16)
    )
    return _CALENDAR_PALETTE[idx % len(_CALENDAR_PALETTE)]


def _build_service(use_service_account: bool):
    if use_service_account:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        return build("calendar", "v3", credentials=credentials)
    return build("calendar", "v3", developerKey=GOOGLE_API_KEY)


def _fetch_calendar_meta(service, cal_id: str) -> dict:
    bg, fg = _calendar_color(cal_id)
    try:
        result = service.calendars().get(calendarId=cal_id).execute()
        return {
            "id": cal_id,
            "summary": result.get("summary", ""),
            "backgroundColor": bg,
            "foregroundColor": fg,
        }
    except Exception:
        return {
            "id": cal_id,
            "summary": "",
            "backgroundColor": bg,
            "foregroundColor": fg,
        }


def _fetch_events(service, cal_id: str, time_min: str, time_max: str) -> list:
    result = service.events().list(
        calendarId=cal_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=250,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def _default_event_time_min(now: datetime) -> str:
    now_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (now_month - timedelta(days=1)).replace(day=1)
    return prev_month_start.isoformat()


def main() -> int:
    now = datetime.now(timezone.utc)
    now_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    time_min = sys.argv[1] if len(sys.argv) > 1 else _default_event_time_min(now)
    time_max = sys.argv[2] if len(sys.argv) > 2 else (now_month + timedelta(days=150)).isoformat()

    has_sa = bool(SERVICE_ACCOUNT_FILE) and os.path.exists(SERVICE_ACCOUNT_FILE)
    prefer_sa = has_sa
    service = _build_service(prefer_sa)

    meta_results = [_fetch_calendar_meta(service, cal_id) for cal_id in CALENDAR_IDS]
    color_map = {m["id"]: m for m in meta_results}

    merged = []
    for cal_id in CALENDAR_IDS:
        try:
            items = _fetch_events(service, cal_id, time_min, time_max)
        except Exception as exc:
            if not has_sa or prefer_sa:
                print(f"Error fetching events for {cal_id}: {exc}", file=sys.stderr)
                items = []
            else:
                try:
                    items = _fetch_events(_build_service(True), cal_id, time_min, time_max)
                except Exception as exc2:
                    print(
                        f"Error fetching events for {cal_id}: {exc} (retry with service account failed: {exc2})",
                        file=sys.stderr,
                    )
                    items = []

        meta = color_map.get(cal_id, {})
        for event in items:
            event["calendarId"] = cal_id
            event["calendarColor"] = meta.get("backgroundColor", BACKGROUND_COLOR)
            event["calendarForeground"] = meta.get("foregroundColor", FOREGROUND_COLOR)
            event["calendarSummary"] = meta.get("summary", "")
            merged.append(event)

    merged.sort(key=lambda ev: ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "")
    print(json.dumps({"events": merged, "calendars": meta_results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())