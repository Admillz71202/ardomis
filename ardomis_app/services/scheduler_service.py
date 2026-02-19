from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass
class ScheduledItem:
    item_id: int
    kind: str
    text: str
    due_ts: float


class SchedulerService:
    """Durable timer/alarm/reminder scheduler backed by SQLite."""

    def __init__(self, db_path: str, timezone_name: str):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone_name = timezone_name
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_ts REAL NOT NULL,
                    due_ts REAL NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def _add(self, due_ts: float, kind: str, text: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO schedule_items (created_ts, due_ts, kind, text, delivered) VALUES (?, ?, ?, ?, 0)",
                (time.time(), due_ts, kind, text.strip()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def add_timer(self, seconds: int, text: str) -> tuple[int, float]:
        due = time.time() + max(1, seconds)
        return self._add(due, "timer", text), due

    def add_reminder_in_minutes(self, minutes: int, text: str) -> tuple[int, float]:
        due = time.time() + max(1, minutes) * 60
        return self._add(due, "reminder", text), due

    def add_alarm_hhmm(self, hhmm_24: str, text: str = "Alarm") -> tuple[int, float]:
        zone = ZoneInfo(self.timezone_name)
        now = datetime.now(zone)
        hour, minute = [int(x) for x in hhmm_24.split(":", 1)]
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        due = target.timestamp()
        return self._add(due, "alarm", text), due

    def add_reminder_at_iso(self, when_local: str, text: str) -> tuple[int, float]:
        # expected format: YYYY-MM-DD HH:MM (local timezone)
        zone = ZoneInfo(self.timezone_name)
        dt = datetime.strptime(when_local, "%Y-%m-%d %H:%M").replace(tzinfo=zone)
        due = dt.timestamp()
        return self._add(due, "reminder", text), due

    def due_items(self) -> list[ScheduledItem]:
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, text, due_ts FROM schedule_items WHERE delivered=0 AND due_ts<=? ORDER BY due_ts ASC",
                (now,),
            ).fetchall()
            ids = [int(r[0]) for r in rows]
            if ids:
                conn.executemany("UPDATE schedule_items SET delivered=1 WHERE id=?", [(i,) for i in ids])
            conn.commit()

        return [ScheduledItem(int(r[0]), str(r[1]), str(r[2]), float(r[3])) for r in rows]

    def list_pending(self, limit: int = 10) -> list[ScheduledItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, text, due_ts FROM schedule_items WHERE delivered=0 ORDER BY due_ts ASC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [ScheduledItem(int(r[0]), str(r[1]), str(r[2]), float(r[3])) for r in rows]
