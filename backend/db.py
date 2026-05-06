import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone

WHITE = "#ffffff"
FOREGROUND_COLOR = WHITE
BACKGROUND_COLOR = "#4285f4"

_CALENDAR_PALETTE = [
    ("#3F854D", WHITE),
    ("#039BE5", WHITE),
    ("#7986CB", WHITE),
    ("#E67C73", WHITE),
    ("#33B679", WHITE),
    ("#F6BF26", WHITE),
    ("#D50000", WHITE),
    ("#4285F4", WHITE),
    ("#8E24AA", WHITE),
    ("#616161", WHITE),
]

WEATHER_TTL_SECONDS = 3600


def _db_connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def event_sort_key(ev: dict) -> str:
    s = ev.get("start", {})
    return s.get("dateTime") or s.get("date") or ""


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _calendar_color(calendar_ids: list[str], cal_id: str) -> tuple[str, str]:
    if cal_id in calendar_ids:
        idx = calendar_ids.index(cal_id)
    else:
        idx = int(hashlib.md5(cal_id.encode()).hexdigest(), 16)
    return _CALENDAR_PALETTE[idx % len(_CALENDAR_PALETTE)]


def _default_event_time_min(now: datetime) -> str:
    now_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (now_month - timedelta(days=1)).replace(day=1)
    return prev_month_start.isoformat()


def _counter_bucket(reset_kind: str, week_ends_on: int, now: datetime) -> str:
    local_now = now.astimezone()
    if reset_kind == "daily":
        return local_now.date().isoformat()
    if reset_kind == "weekly":
        weekday = (local_now.weekday() + 1) % 7
        week_start = (week_ends_on + 1) % 7
        days_since_start = (weekday - week_start) % 7
        bucket_start = local_now.date() - timedelta(days=days_since_start)
        return bucket_start.isoformat()
    if reset_kind == "monthly":
        return f"{local_now.year:04d}-{local_now.month:02d}"
    if reset_kind == "yearly":
        return f"{local_now.year:04d}"
    return "all-time"


def _db_init(db_path: str, calendar_ids: list[str]) -> None:
    with _db_connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                fetched_at TEXT NOT NULL,
                forecast   TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS calendars (
                id               TEXT PRIMARY KEY,
                summary          TEXT NOT NULL DEFAULT '',
                background_color TEXT NOT NULL DEFAULT '{BACKGROUND_COLOR}',
                foreground_color TEXT NOT NULL DEFAULT '{FOREGROUND_COLOR}',
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
        for col, definition in [
            ("list_type", "TEXT NOT NULL DEFAULT 'todo'"),
            ("reset_kind", "TEXT NOT NULL DEFAULT 'none'"),
            ("week_ends_on", "INTEGER NOT NULL DEFAULT 0"),
            ("counter_mode", "TEXT NOT NULL DEFAULT 'normal'"),
            ("counter_initial", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if not _has_column(conn, "todo_lists", col):
                conn.execute(f"ALTER TABLE todo_lists ADD COLUMN {col} {definition}")

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
        event_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(events)").fetchall()
        }
        if event_columns and "calendar_id" not in event_columns:
            conn.execute("DROP TABLE events")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                calendar_id TEXT PRIMARY KEY,
                fetched_at  TEXT NOT NULL,
                data        TEXT NOT NULL
            )
        """)
        placeholder_fetched_at = datetime.fromtimestamp(0, timezone.utc).isoformat()
        if calendar_ids:
            conn.executemany(
                """
                INSERT INTO events (calendar_id, fetched_at, data)
                VALUES (?, ?, '[]')
                ON CONFLICT(calendar_id) DO NOTHING
                """,
                [(cal_id, placeholder_fetched_at) for cal_id in calendar_ids],
            )
            placeholders = ", ".join("?" for _ in calendar_ids)
            conn.execute(
                f"DELETE FROM events WHERE calendar_id NOT IN ({placeholders})",
                calendar_ids,
            )
        else:
            conn.execute("DELETE FROM events")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS counter_state (
                list_id     INTEGER PRIMARY KEY REFERENCES todo_lists(id) ON DELETE CASCADE,
                bucket      TEXT NOT NULL,
                value       INTEGER NOT NULL,
                today       INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute("PRAGMA foreign_keys = ON")
