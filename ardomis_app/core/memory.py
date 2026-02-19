from __future__ import annotations

import sqlite3
import time
from collections import deque
from pathlib import Path


class ChatMemory:
    """Bounded in-memory chat history backed by a single SQLite file.

    Keeps the latest `max_messages` in RAM for prompt context and persists a larger,
    bounded history to disk so context survives power cycles/restarts.
    """

    def __init__(self, max_messages: int = 24, db_path: str = "~/ardomis/memory.db", max_persist_rows: int = 800):
        self.max_messages = max_messages
        self.max_persist_rows = max(50, int(max_persist_rows))
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.buf = deque(maxlen=max_messages)

        self._init_db()
        self._load_recent()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _load_recent(self) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
                (self.max_messages,),
            ).fetchall()

        for role, content in reversed(rows):
            self.buf.append({"role": role, "content": content})

    def _persist(self, role: str, content: str) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (ts, role, content) VALUES (?, ?, ?)",
                (now, role, content),
            )
            conn.execute(
                """
                DELETE FROM messages
                WHERE id NOT IN (
                    SELECT id FROM messages ORDER BY id DESC LIMIT ?
                )
                """,
                (self.max_persist_rows,),
            )
            conn.commit()

    def add_user(self, text: str) -> None:
        value = (text or "").strip()
        if value:
            self.buf.append({"role": "user", "content": value})
            self._persist("user", value)

    def add_assistant(self, text: str) -> None:
        value = (text or "").strip()
        if value:
            self.buf.append({"role": "assistant", "content": value})
            self._persist("assistant", value)

    def messages(self) -> list[dict[str, str]]:
        return list(self.buf)

    def clear(self) -> None:
        self.buf.clear()
        with self._connect() as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()
