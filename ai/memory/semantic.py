import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "semantic_memory.db"

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_facts (
            phone TEXT NOT NULL,
            fact TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (phone, fact)
        )
        """
    )
    return conn


def recall(phone: str, limit: int = 20) -> list[str]:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT fact FROM semantic_facts WHERE phone = ? ORDER BY created_at DESC LIMIT ?",
            (phone, limit),
        ).fetchall()
        conn.close()
    return [row[0] for row in rows]


def store(phone: str, facts: list[str]) -> None:
    if not phone or not facts:
        return

    now = datetime.now(UTC).isoformat()
    with _lock:
        conn = _connect()
        for fact in facts:
            clean = fact.strip()
            if clean:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_facts (phone, fact, created_at) VALUES (?, ?, ?)",
                    (phone, clean, now),
                )
        conn.commit()
        conn.close()
