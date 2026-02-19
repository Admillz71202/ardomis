from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class KnowledgeVault:
    """Small, durable personal knowledge + task store in a single SQLite DB."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_ts REAL NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_ts REAL NOT NULL,
                    content TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def add_note(self, content: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO notes (created_ts, content) VALUES (?, ?)",
                (time.time(), content.strip()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_notes(self, limit: int = 10) -> list[tuple[int, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, content FROM notes ORDER BY id DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [(int(r[0]), str(r[1])) for r in rows]

    def add_todo(self, content: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO todos (created_ts, content, done) VALUES (?, ?, 0)",
                (time.time(), content.strip()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def complete_todo(self, todo_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE todos SET done=1 WHERE id=?", (todo_id,))
            conn.commit()
            return cur.rowcount > 0

    def list_todos(self, include_done: bool = False, limit: int = 15) -> list[tuple[int, str, bool]]:
        query = "SELECT id, content, done FROM todos"
        params: list[object] = []
        if not include_done:
            query += " WHERE done=0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, limit))

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        return [(int(r[0]), str(r[1]), bool(r[2])) for r in rows]
