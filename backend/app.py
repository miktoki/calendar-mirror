"""FastAPI backend for calendar, weather, todo-list, and counter APIs.

Endpoints defined in this file:
- GET  /api/events
- GET  /api/calendars
- POST /api/weather/refresh
- GET  /api/weather
- GET  /api/lists
- POST /api/lists
- DELETE /api/lists/{list_id}
- GET  /api/lists/{list_id}/items
- POST /api/lists/{list_id}/items
- PATCH  /api/items/{item_id}
- DELETE /api/items/{item_id}
- GET  /api/counters/{list_id}
- POST /api/counters/{list_id}/inc
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pydantic import BaseModel

from db import (
    BACKGROUND_COLOR,
    FOREGROUND_COLOR,
    WEATHER_TTL_SECONDS,
    _calendar_color,
    _counter_bucket,
    _db_connect,
    _db_init,
    _default_event_time_min,
    event_sort_key,
    rows_as_dicts,
)

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "")
MET_NO_LAT = os.environ.get("MET_NO_LAT", "59.9139")
MET_NO_LON = os.environ.get("MET_NO_LON", "10.7522")
MET_NO_USER_AGENT = os.environ.get(
    "MET_NO_USER_AGENT", "surface-calendar/1.0 fakemik2@gmail.com"
)
DB_PATH = os.environ["DB_PATH"]

CALENDAR_IDS = [
    cid.strip()
    for cid in os.environ.get(
        "CALENDAR_IDS",
        "en.norwegian#holiday@group.v.calendar.google.com",
    ).split(",")
    if cid.strip()
]
calendar_color = partial(_calendar_color, CALENDAR_IDS)
db_connect = partial(_db_connect, DB_PATH)
db_init = partial(_db_init, DB_PATH, CALENDAR_IDS)
print(f"Using calendar IDs: {CALENDAR_IDS}", os.environ.get("CALENDAR_IDS"))


def _get_counter_state(conn, list_id: int, now: datetime | None = None) -> dict:
    if now is None:
        now = datetime.now(timezone.utc)
    row = conn.execute("SELECT * FROM todo_lists WHERE id = ?", (list_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="counter not found")
    if row["list_type"] != "counter":
        raise HTTPException(status_code=400, detail="list is not a counter")

    reset_kind = row["reset_kind"] or "none"
    week_ends_on = row["week_ends_on"] or 0
    bucket = _counter_bucket(reset_kind, week_ends_on, now)
    state = conn.execute(
        "SELECT * FROM counter_state WHERE list_id = ?", (list_id,)
    ).fetchone()

    if not state or state["bucket"] != bucket:
        value = row["counter_initial"] or 0
        today = 0
        conn.execute(
            """
            INSERT INTO counter_state (list_id, bucket, value, today, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(list_id) DO UPDATE SET
                bucket     = excluded.bucket,
                value      = excluded.value,
                today      = excluded.today,
                updated_at = excluded.updated_at
            """,
            (list_id, bucket, value, today, now.isoformat()),
        )
    else:
        value = state["value"]
        today = state["today"]

    return {
        "counter_id": list_id,
        "reset_kind": reset_kind,
        "week_ends_on": week_ends_on,
        "mode": row["counter_mode"] or "normal",
        "initial": row["counter_initial"] or 0,
        "value": value,
        "today": today,
    }


async def _service(
    loop: asyncio.AbstractEventLoop,
    *,
    credentials: service_account.Credentials | None = None,
    developerKey: str | None = None,
):
    """Builds the Google Calendar API service object in a non-blocking way.

    Args:
        loop: The current event loop.
        credentials: Google| Nonecredentials for authentication.
        developerKey: API| Nonekey for authentication.

    """
    return await loop.run_in_executor(
        None,
        lambda: build(
            "calendar", "v3", credentials=credentials, developerKey=developerKey
        ),
    )


async def fetch_events_from_google(
    time_min_override: str | None = None,
    time_max_override: str | None = None,
) -> list:
    loop = asyncio.get_running_loop()
    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        service = await _service(loop, credentials=credentials)
    else:
        service = await _service(loop, developerKey=GOOGLE_API_KEY)

    now = datetime.now(timezone.utc)
    time_min = time_min_override or _default_event_time_min(now)
    time_max = time_max_override or (now + timedelta(days=150)).isoformat()
    is_default_range = time_min_override is None

    async def fetch_calendar_meta(cal_id: str) -> dict:
        bg, fg = calendar_color(cal_id)
        try:
            result = await loop.run_in_executor(
                None,
                lambda: service.calendars().get(calendarId=cal_id).execute(),
            )
            summary = result.get("summary", "")
        except Exception:
            summary = ""
        return {
            "id": cal_id,
            "summary": summary,
            "backgroundColor": bg,
            "foregroundColor": fg,
        }

    async def fetch_one(cal_id: str) -> tuple[str, list, bool]:
        try:
            result = await loop.run_in_executor(
                None,
                lambda: (
                    service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=250,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                ),
            )
            return cal_id, result.get("items", []), True
        except Exception as e:
            print(f"Error fetching events for {cal_id}: {e}")
            return cal_id, [], False

    event_results, meta_results = await asyncio.gather(
        asyncio.gather(*[fetch_one(cid) for cid in CALENDAR_IDS]),
        asyncio.gather(*[fetch_calendar_meta(cid) for cid in CALENDAR_IDS]),
    )

    any_succeeded = any(success for _, _, success in event_results)
    updated_at = now.isoformat()
    color_map = {m["id"]: m for m in meta_results}

    merged = []
    cached_events_by_calendar: dict[str, list] = {}
    for cal_id, items, success in event_results:
        meta = color_map.get(cal_id, {})
        calendar_events = []
        for event in items:
            event["calendarId"] = cal_id
            event["calendarColor"] = meta.get("backgroundColor", BACKGROUND_COLOR)
            event["calendarForeground"] = meta.get("foregroundColor", FOREGROUND_COLOR)
            event["calendarSummary"] = meta.get("summary", "")
            merged.append(event)
            calendar_events.append(event)
        if success:
            cached_events_by_calendar[cal_id] = calendar_events

    merged.sort(key=event_sort_key)

    with db_connect() as conn:
        for meta in meta_results:
            conn.execute(
                """
                INSERT INTO calendars (id, summary, background_color, foreground_color, updated_at)
                VALUES (:id, :summary, :backgroundColor, :foregroundColor, :updated_at)
                ON CONFLICT(id) DO UPDATE SET
                    summary          = excluded.summary,
                    background_color = excluded.background_color,
                    foreground_color = excluded.foreground_color,
                    updated_at       = excluded.updated_at
            """,
                {**meta, "updated_at": updated_at},
            )

        if is_default_range and any_succeeded:
            for cal_id, calendar_events in cached_events_by_calendar.items():
                conn.execute("DELETE FROM events WHERE calendar_id = ?", (cal_id,))
                conn.execute(
                    "INSERT INTO events (calendar_id, fetched_at, data) VALUES (?, ?, ?)",
                    (cal_id, now.isoformat(), json.dumps(calendar_events)),
                )

    if not any_succeeded:
        raise RuntimeError("Failed to refresh all calendars; kept cached events")
    return merged


def _load_events_from_db() -> tuple[list, datetime | None]:
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT fetched_at, data FROM events ORDER BY calendar_id"
        ).fetchall()
    if not rows:
        return [], None

    merged = []
    latest_fetched_at: datetime | None = None
    for row in rows:
        merged.extend(json.loads(row["data"]))
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        if latest_fetched_at is None or fetched_at > latest_fetched_at:
            latest_fetched_at = fetched_at

    merged.sort(key=event_sort_key)
    return merged, latest_fetched_at


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
        conn.execute(
            """
            INSERT INTO weather (id, fetched_at, forecast)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                forecast   = excluded.forecast
        """,
            (fetched_at, json.dumps(resp.json())),
        )
    return fetched_at


async def weather_refresh_loop():
    while True:
        try:
            with db_connect() as conn:
                row = conn.execute(
                    "SELECT fetched_at FROM weather WHERE id = 1"
                ).fetchone()
            if row:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(
                    row["fetched_at"]
                )
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
    event_min: str | None = Query(None, description="ISO8601 start of range"),
    event_max: str | None = Query(None, description="ISO8601 end of range"),
):
    db_events, _ = _load_events_from_db()

    if event_min or event_max:
        now = datetime.now(timezone.utc)
        time_min = event_min or _default_event_time_min(now)
        time_max = event_max or (now + timedelta(days=150)).isoformat()
        cached = _filter_events(db_events, time_min, time_max)
        asyncio.create_task(
            fetch_events_from_google(
                time_min_override=event_min,
                time_max_override=event_max,
            )
        )
        return cached

    if db_events:  # if already have events in DB, return them immediately and refresh in background
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
    return rows_as_dicts(rows)


@app.post("/api/weather/refresh")
async def weather_refresh():
    fetched_at = await fetch_and_store_weather()
    return {"status": "ok", "fetched_at": fetched_at}


@app.get("/api/weather")
async def weather():
    with db_connect() as conn:
        row = conn.execute(
            "SELECT fetched_at, forecast FROM weather WHERE id = 1"
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="no weather data yet")
    return {"fetched_at": row["fetched_at"], "forecast": json.loads(row["forecast"])}


class ListCreate(BaseModel):
    name: str
    list_type: Literal["todo", "counter"] = "todo"
    reset_kind: Literal["none", "daily", "weekly", "monthly", "yearly"] = "none"
    week_ends_on: int = 0
    counter_mode: Literal["normal", "negative"] = "normal"
    counter_initial: int = 0


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
    return rows_as_dicts(rows)


@app.post("/api/lists", status_code=201)
async def create_list(body: ListCreate):
    with db_connect() as conn:
        week_ends_on = body.week_ends_on % 7 if body.reset_kind == "weekly" else 0
        counter_mode = body.counter_mode if body.list_type == "counter" else "normal"
        counter_initial = body.counter_initial if body.list_type == "counter" else 0
        cur = conn.execute(
            """
            INSERT INTO todo_lists (
                name, list_type, reset_kind, week_ends_on, counter_mode, counter_initial
            )
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                body.name,
                body.list_type,
                body.reset_kind,
                week_ends_on,
                counter_mode,
                counter_initial,
            ),
        )
        row = cur.fetchone()
    return dict(row)


@app.delete("/api/lists/{list_id}", status_code=204)
async def delete_list(list_id: int):
    with db_connect() as conn:
        conn.execute("DELETE FROM todo_lists WHERE id = ?", (list_id,))


@app.get("/api/lists/{list_id}/items")
async def get_items(list_id: int):
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM todo_items WHERE list_id = ? ORDER BY sort_order, created_at",
            (list_id,),
        ).fetchall()
    return rows_as_dicts(rows)


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


@app.get("/api/counters/{list_id}")
async def get_counter(list_id: int):
    with db_connect() as conn:
        return _get_counter_state(conn, list_id)


@app.post("/api/counters/{list_id}/inc")
async def increment_counter(list_id: int, body: CounterDelta):
    with db_connect() as conn:
        state = _get_counter_state(conn, list_id)
        delta = body.delta
        next_value = state["value"] + delta
        if state["mode"] == "negative":
            if next_value < 0 or next_value > state["initial"]:
                raise HTTPException(
                    status_code=409, detail="counter update out of range"
                )
        elif next_value < 0:
            raise HTTPException(status_code=409, detail="counter update out of range")
        effective_today_delta = delta if state["mode"] == "normal" else -delta
        value = next_value
        today = state["today"] + effective_today_delta
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE counter_state SET value = ?, today = ?, updated_at = ? WHERE list_id = ?",
            (value, today, now, list_id),
        )
    return {"ok": True, "value": value, "today": today}
