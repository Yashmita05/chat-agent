"""Timestamped conversation memory backed by SQLite (stdlib only).

Every user message and assistant reply is stored with a UTC timestamp.
The agent reads it back in two ways:
  * recent turns  -> replayed as normal chat messages (short-term context)
  * question log  -> compact "what the user asked, and when" digest that is
                     injected into the system prompt (long-term recall)
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL    NOT NULL,          -- unix seconds, UTC
    session TEXT    NOT NULL,
    role    TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS turns_session_ts ON turns (session, ts);
"""


class Memory:
    def __init__(self, path: str = "memory.db", session: str = "default", tz: str = "UTC"):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.session = session
        self.tz = ZoneInfo(tz)

    # -- writing -----------------------------------------------------------
    def add(self, role: str, content: str, ts: float | None = None) -> None:
        self.db.execute(
            "INSERT INTO turns (ts, session, role, content) VALUES (?, ?, ?, ?)",
            (ts if ts is not None else time.time(), self.session, role, content),
        )
        self.db.commit()

    # -- reading -----------------------------------------------------------
    def recent_messages(self, n: int = 12) -> list[dict]:
        """Last n turns as API messages, oldest first, always starting with 'user'."""
        rows = self.db.execute(
            "SELECT role, content FROM turns WHERE session = ? ORDER BY id DESC LIMIT ?",
            (self.session, n),
        ).fetchall()
        msgs = [{"role": r, "content": c} for r, c in reversed(rows)]
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        return msgs

    def question_log(self, limit: int = 60, max_chars: int = 140) -> str:
        """Digest of past user questions with local timestamps, oldest first."""
        rows = self.db.execute(
            "SELECT ts, content FROM turns WHERE session = ? AND role = 'user' "
            "ORDER BY id DESC LIMIT ?",
            (self.session, limit),
        ).fetchall()
        lines = []
        for ts, content in reversed(rows):
            when = datetime.fromtimestamp(ts, timezone.utc).astimezone(self.tz)
            text = " ".join(content.split())
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            lines.append(f"[{when:%Y-%m-%d %H:%M}] {text}")
        return "\n".join(lines)

    def clear(self) -> None:
        self.db.execute("DELETE FROM turns WHERE session = ?", (self.session,))
        self.db.commit()
