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
    ("#ab47bc", "#ffffff"),  # purple
    ("#0f9d58", "#ffffff"),  # Google green
    ("#ff7043", "#ffffff"),  # deep orange
    ("#5c6bc0", "#ffffff"),  # indigo
    ("#00acc1", "#ffffff"),  # cyan
    ("#4285f4", "#ffffff"),  # Google blue
    ("#db4437", "#ffffff"),  # Google red
    ("#f4b400", "#1a1a2e"),  # Google yellow
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

DB_PATH = os.environ.get("DB_PATH", "rpi-calendar.db")
WEATHER_TTL_SECONDS = 3600


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
                list_type  TEXT NOT NULL DEFAULT 'todo',
                reset_kind TEXT NOT NULL DEFAULT 'none',
                week_ends_on INTEGER NOT NULL DEFAULT 0,
                counter_mode TEXT NOT NULL DEFAULT 'normal',
                counter_initial INTEGER NOT NULL DEFAULT 0,
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
    time_min = time_min_override or (now - timedelta(days=30)).isoformat()
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
        time_min = min or (now - timedelta(days=30)).isoformat()
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


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Accept both naive and tz-aware ISO strings
        dt = datetime.fromisoformat(s)
        return dt
    except Exception:
        return None


def _last_reset_at(reset_kind: str, week_ends_on: int, now: datetime) -> datetime:
    """Compute the most recent reset moment in local server time.

    Weekly: reset at local midnight starting the day AFTER `week_ends_on`.
    week_ends_on follows Python's getDay style: 0=Sunday, 6=Saturday.
    """
    local_now = now.replace(tzinfo=None)
    start_today = datetime(local_now.year, local_now.month, local_now.day)

    if reset_kind == "daily":
        return start_today
    if reset_kind == "weekly":
        # Map Python weekday (Mon=0..Sun=6) to desired numbering (Sun=0..Sat=6)
        # desired = (python + 1) % 7
        desired_today = (start_today.weekday() + 1) % 7
        # We reset on the day after `week_ends_on`.
        reset_day = (week_ends_on + 1) % 7
        days_since_reset = (desired_today - reset_day) % 7
        return start_today - timedelta(days=days_since_reset)
    if reset_kind == "monthly":
        return datetime(local_now.year, local_now.month, 1)
    if reset_kind == "yearly":
        return datetime(local_now.year, 1, 1)
    # none
    return datetime.min


def _local_day_str(now: datetime) -> str:
    n = now.replace(tzinfo=None)
    return f"{n.year:04d}-{n.month:02d}-{n.day:02d}"


def _counter_sum_since_reset(conn: sqlite3.Connection, counter_id: int, reset_at: datetime) -> int:
    # We only have per-day rows, so sum days >= reset date.
    reset_day = f"{reset_at.year:04d}-{reset_at.month:02d}-{reset_at.day:02d}"
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM counter_daily WHERE counter_id = ? AND day >= ?",
        (counter_id, reset_day),
    ).fetchone()
    return int(row["s"] or 0)


def _counter_today_amount(conn: sqlite3.Connection, counter_id: int, today: str) -> int:
    row = conn.execute(
        "SELECT amount FROM counter_daily WHERE counter_id = ? AND day = ?",
        (counter_id, today),
    ).fetchone()
    return int(row["amount"]) if row else 0


# --- Todo lists ---

class ListCreate(BaseModel):
    name: str
    list_type: str | None = None  # todo | counter
    reset_kind: str | None = None  # none | daily | weekly | monthly | yearly
    week_ends_on: int | None = None  # 0=Sun..6=Sat
    counter_mode: str | None = None  # normal | negative
    counter_initial: int | None = None

class ItemCreate(BaseModel):
    text: str

class ItemPatch(BaseModel):
    text: str | None = None
    done: bool | None = None
    sort_order: int | None = None


class CounterDelta(BaseModel):
    delta: int


@app.get("/api/lists")
async def get_lists():
    with db_connect() as conn:
        rows = conn.execute("SELECT * FROM todo_lists ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/lists", status_code=201)
async def create_list(body: ListCreate):
    list_type = body.list_type or "todo"
    reset_kind = body.reset_kind or "none"
    week_ends_on = 0 if body.week_ends_on is None else int(body.week_ends_on)
    counter_mode = body.counter_mode or "normal"
    counter_initial = 0 if body.counter_initial is None else int(body.counter_initial)
    with db_connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO todo_lists (name, list_type, reset_kind, week_ends_on, counter_mode, counter_initial)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (body.name, list_type, reset_kind, week_ends_on, counter_mode, counter_initial),
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
    now = datetime.now()
    with db_connect() as conn:
        list_row = conn.execute(
            "SELECT reset_kind, week_ends_on FROM todo_lists WHERE id = ?",
            (list_id,),
        ).fetchone()
        if not list_row:
            raise HTTPException(status_code=404, detail="list not found")
        reset_at = _last_reset_at(list_row["reset_kind"], int(list_row["week_ends_on"]), now)
        rows = conn.execute(
            "SELECT * FROM todo_items WHERE list_id = ? ORDER BY sort_order, created_at",
            (list_id,)
        ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        checked = _parse_dt(d.get("checked_at"))
        d["done"] = 1 if (checked and checked >= reset_at) else 0
        out.append(d)
    return out


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

    # If `done` is patched, store a timestamp instead of a sticky boolean.
    if "done" in fields:
        done_bool = bool(fields.pop("done"))
        fields.pop("done", None)
        fields["checked_at"] = datetime.now(timezone.utc).isoformat() if done_bool else None

    # Keep legacy `done` column in sync for older clients (best effort)
    if "checked_at" in fields:
        fields["done"] = 1 if fields["checked_at"] else 0

    # SQLite needs explicit NULL binding when checked_at is None.
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with db_connect() as conn:
        conn.execute(
            f"UPDATE todo_items SET {set_clause} WHERE id = ?",
            (*fields.values(), item_id),
        )
    return {"ok": True}


# --- Counters ---

@app.get("/api/counters/{counter_id}")
async def get_counter(counter_id: int):
    now = datetime.now()
    today = _local_day_str(now)
    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM todo_lists WHERE id = ?",
            (counter_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="counter not found")
        if row["list_type"] != "counter":
            raise HTTPException(status_code=400, detail="not a counter")
        reset_at = _last_reset_at(row["reset_kind"], int(row["week_ends_on"]), now)
        total = _counter_sum_since_reset(conn, counter_id, reset_at)
        today_amt = _counter_today_amount(conn, counter_id, today)

    mode = row["counter_mode"]
    initial = int(row["counter_initial"] or 0)
    value = (initial - total) if mode == "negative" else total
    return {
        "counter_id": counter_id,
        "reset_kind": row["reset_kind"],
        "week_ends_on": row["week_ends_on"],
        "mode": mode,
        "initial": initial,
        "value": value,
        "today": today_amt,
    }


@app.post("/api/counters/{counter_id}/inc")
async def counter_inc(counter_id: int, body: CounterDelta):
    now = datetime.now()
    today = _local_day_str(now)
    delta = int(body.delta)
    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM todo_lists WHERE id = ?",
            (counter_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="counter not found")
        if row["list_type"] != "counter":
            raise HTTPException(status_code=400, detail="not a counter")

        existing = _counter_today_amount(conn, counter_id, today)
        new_val = existing + delta
        if new_val < 0:
            # Enforce monotonic per day (can't go below 0 for the day)
            new_val = 0

        conn.execute(
            """
            INSERT INTO counter_daily (counter_id, day, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(counter_id, day) DO UPDATE SET amount = excluded.amount
            """,
            (counter_id, today, new_val),
        )

        reset_at = _last_reset_at(row["reset_kind"], int(row["week_ends_on"]), now)
        total = _counter_sum_since_reset(conn, counter_id, reset_at)
        today_amt = new_val

    mode = row["counter_mode"]
    initial = int(row["counter_initial"] or 0)
    value = (initial - total) if mode == "negative" else total
    return {"ok": True, "value": value, "today": today_amt}


@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(item_id: int):
    with db_connect() as conn:
        conn.execute("DELETE FROM todo_items WHERE id = ?", (item_id,))
