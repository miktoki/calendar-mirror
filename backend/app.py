from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import asyncio
import json
import os
import sqlite3
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pydantic import BaseModel

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "")
CALENDAR_IDS = [
    cid.strip()
    for cid in os.environ.get(
        "CALENDAR_IDS",
        "en.norwegian#holiday@group.v.calendar.google.com",
    ).split(",")
    if cid.strip()
]
FOREGROUND_COLOR =  "#ffffff"
BACKGROUND_COLOR = "#4285f4"

# Distinct palette for assigning per-calendar colours when the API can't provide them
_CALENDAR_PALETTE = [
    ("#4285f4", "#ffffff"),  # Google blue
    ("#0f9d58", "#ffffff"),  # Google green
    ("#db4437", "#ffffff"),  # Google red
    ("#f4b400", "#1a1a2e"),  # Google yellow
    ("#ab47bc", "#ffffff"),  # purple
    ("#00acc1", "#ffffff"),  # cyan
    ("#ff7043", "#ffffff"),  # deep orange
    ("#5c6bc0", "#ffffff"),  # indigo
]

def _calendar_color(cal_id: str) -> tuple[str, str]:
    """Assign a colour by position in CALENDAR_IDS for maximum distinctiveness."""
    idx = CALENDAR_IDS.index(cal_id) if cal_id in CALENDAR_IDS else (
        int(__import__('hashlib').md5(cal_id.encode()).hexdigest(), 16)
    )
    return _CALENDAR_PALETTE[idx % len(_CALENDAR_PALETTE)]

MET_NO_LAT = os.environ.get("MET_NO_LAT", "59.9139")
MET_NO_LON = os.environ.get("MET_NO_LON", "10.7522")
MET_NO_USER_AGENT = os.environ.get("MET_NO_USER_AGENT", "rpi-calendar/1.0 contact@example.com")

DB_PATH = os.environ.get("DB_PATH", "weather.db")
WEATHER_TTL_SECONDS = 3600


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _default_event_time_min(now: datetime) -> str:
    now_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (now_month - timedelta(days=1)).replace(day=1)
    return prev_month_start.isoformat()


def db_init():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                fetched_at TEXT NOT NULL,
                forecast   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calendars (
                id               TEXT PRIMARY KEY,
                summary          TEXT NOT NULL DEFAULT '',
                background_color TEXT NOT NULL DEFAULT '#4285f4',
                foreground_color TEXT NOT NULL DEFAULT '#ffffff',
                updated_at       TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todo_lists (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todo_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id    INTEGER NOT NULL REFERENCES todo_lists(id) ON DELETE CASCADE,
                text       TEXT NOT NULL,
                done       INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                fetched_at TEXT NOT NULL,
                data       TEXT NOT NULL
            )
        """)
        conn.execute("PRAGMA foreign_keys = ON")


async def fetch_events_from_google(
    time_min_override: Optional[str] = None,
    time_max_override: Optional[str] = None,
) -> list:

    loop = asyncio.get_event_loop()

    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        service = await loop.run_in_executor(
            None,
            lambda: build("calendar", "v3", credentials=credentials),
        )
    else:
        service = await loop.run_in_executor(
            None,
            lambda: build("calendar", "v3", developerKey=GOOGLE_API_KEY),
        )

    now = datetime.now(timezone.utc)
    time_min = time_min_override or _default_event_time_min(now)
    time_max = time_max_override or (now + timedelta(days=150)).isoformat()
    is_default_range = time_min_override is None

    async def fetch_calendar_meta(cal_id: str) -> dict:
        bg, fg = _calendar_color(cal_id)
        try:
            result = await loop.run_in_executor(
                None,
                lambda: service.calendars().get(calendarId=cal_id).execute()
            )
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

    async def fetch_one(cal_id: str) -> tuple[str, list]:
        try:
            result = await loop.run_in_executor(
                None,
                lambda: service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=250,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
            )
            return cal_id, result.get("items", [])
        except Exception as e:
            print(f"Error fetching events for {cal_id}: {e}")
            return cal_id, []

    event_results, meta_results = await asyncio.gather(
        asyncio.gather(*[fetch_one(cid) for cid in CALENDAR_IDS]),
        asyncio.gather(*[fetch_calendar_meta(cid) for cid in CALENDAR_IDS]),
    )

    updated_at = now.isoformat()
    with db_connect() as conn:
        for meta in meta_results:
            conn.execute("""
                INSERT INTO calendars (id, summary, background_color, foreground_color, updated_at)
                VALUES (:id, :summary, :backgroundColor, :foregroundColor, :updated_at)
                ON CONFLICT(id) DO UPDATE SET
                    summary          = excluded.summary,
                    background_color = excluded.background_color,
                    foreground_color = excluded.foreground_color,
                    updated_at       = excluded.updated_at
            """, {**meta, "updated_at": updated_at})

    color_map = {m["id"]: m for m in meta_results}

    merged = []
    for cal_id, items in event_results:
        meta = color_map.get(cal_id, {})
        for event in items:
            event["calendarId"] = cal_id
            event["calendarColor"] = meta.get("backgroundColor", BACKGROUND_COLOR)
            event["calendarForeground"] = meta.get("foregroundColor", FOREGROUND_COLOR)
            event["calendarSummary"] = meta.get("summary", "")
            merged.append(event)

    def sort_key(ev):
        s = ev.get("start", {})
        return s.get("dateTime") or s.get("date") or ""

    merged.sort(key=sort_key)
    if is_default_range:
        with db_connect() as conn:
            conn.execute("""
                INSERT INTO events (id, fetched_at, data)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET fetched_at = excluded.fetched_at,
                                              data       = excluded.data
            """, (now.isoformat(), json.dumps(merged)))
    return merged


def _load_events_from_db() -> tuple[list, datetime | None]:
    with db_connect() as conn:
        row = conn.execute("SELECT fetched_at, data FROM events WHERE id = 1").fetchone()
    if not row:
        return [], None
    return json.loads(row["data"]), datetime.fromisoformat(row["fetched_at"])


def _filter_events(events: list, time_min: str, time_max: str) -> list:
    result = []
    for ev in events:
        s = ev.get("start", {})
        t = s.get("dateTime") or s.get("date") or ""
        e = ev.get("end", {})
        end_t = e.get("dateTime") or e.get("date") or ""
        if end_t >= time_min and t <= time_max:
            result.append(ev)
    return result


async def fetch_and_store_weather():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.met.no/weatherapi/locationforecast/2.0/compact"
            f"?lat={MET_NO_LAT}&lon={MET_NO_LON}",
            headers={"User-Agent": MET_NO_USER_AGENT},
            timeout=15,
            follow_redirects=True,
        )
    resp.raise_for_status()
    fetched_at = datetime.now(timezone.utc).isoformat()
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO weather (id, fetched_at, forecast)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET fetched_at = excluded.fetched_at,
                                          forecast   = excluded.forecast
        """, (fetched_at, json.dumps(resp.json())))
    return fetched_at


async def weather_refresh_loop():
    while True:
        try:
            with db_connect() as conn:
                row = conn.execute("SELECT fetched_at FROM weather WHERE id = 1").fetchone()
            if row:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
                remaining = WEATHER_TTL_SECONDS - age.total_seconds()
                if remaining > 0:
                    await asyncio.sleep(remaining)
                    continue
            await fetch_and_store_weather()
            await asyncio.sleep(WEATHER_TTL_SECONDS)
        except Exception:
            await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_init()
    task = asyncio.create_task(weather_refresh_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/events")
async def events(
    min: Optional[str] = Query(None, description="ISO8601 start of range"),
    max: Optional[str] = Query(None, description="ISO8601 end of range"),
):
    db_events, db_fetched_at = _load_events_from_db()

    if min or max:
        now = datetime.now(timezone.utc)
        time_min = min or _default_event_time_min(now)
        time_max = max or (now + timedelta(days=150)).isoformat()
        cached = _filter_events(db_events, time_min, time_max)
        asyncio.create_task(fetch_events_from_google(
            time_min_override=min,
            time_max_override=max,
        ))
        return cached

    if db_events:
        asyncio.create_task(fetch_events_from_google())
        return db_events

    try:
        return await fetch_events_from_google()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch events: {e}")


@app.get("/api/calendars")
async def get_calendars():
    with db_connect() as conn:
        rows = conn.execute("SELECT * FROM calendars ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/weather/refresh")
async def weather_refresh():
    fetched_at = await fetch_and_store_weather()
    return {"status": "ok", "fetched_at": fetched_at}


@app.get("/api/weather")
async def weather():
    with db_connect() as conn:
        row = conn.execute("SELECT fetched_at, forecast FROM weather WHERE id = 1").fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="no weather data yet")
    return {"fetched_at": row["fetched_at"], "forecast": json.loads(row["forecast"])}


# --- Todo lists ---

class ListCreate(BaseModel):
    name: str

class ItemCreate(BaseModel):
    text: str

class ItemPatch(BaseModel):
    text: str | None = None
    done: bool | None = None
    sort_order: int | None = None


@app.get("/api/lists")
async def get_lists():
    with db_connect() as conn:
        rows = conn.execute("SELECT * FROM todo_lists ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/lists", status_code=201)
async def create_list(body: ListCreate):
    with db_connect() as conn:
        cur = conn.execute(
            "INSERT INTO todo_lists (name) VALUES (?) RETURNING *", (body.name,)
        )
        row = cur.fetchone()
    return dict(row)


@app.delete("/api/lists/{list_id}", status_code=204)
async def delete_list(list_id: int):
    with db_connect() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM todo_lists WHERE id = ?", (list_id,))


@app.get("/api/lists/{list_id}/items")
async def get_items(list_id: int):
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM todo_items WHERE list_id = ? ORDER BY sort_order, created_at",
            (list_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/lists/{list_id}/items", status_code=201)
async def create_item(list_id: int, body: ItemCreate):
    with db_connect() as conn:
        cur = conn.execute(
            "INSERT INTO todo_items (list_id, text) VALUES (?, ?) RETURNING *",
            (list_id, body.text),
        )
        row = cur.fetchone()
    return dict(row)


@app.patch("/api/items/{item_id}")
async def patch_item(item_id: int, body: ItemPatch):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="nothing to update")
    if "done" in fields:
        fields["done"] = int(fields["done"])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with db_connect() as conn:
        conn.execute(
            f"UPDATE todo_items SET {set_clause} WHERE id = ?",
            (*fields.values(), item_id),
        )
    return {"ok": True}


@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(item_id: int):
    with db_connect() as conn:
        conn.execute("DELETE FROM todo_items WHERE id = ?", (item_id,))
