import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "semantic_memory.db"

_lock = threading.Lock()


def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_facts (
            tenant_id TEXT NOT NULL,
            phone TEXT NOT NULL,
            fact TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, phone, fact)
        )
        """
    )


def _migrate_legacy_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(semantic_facts)")}
    if not columns or "tenant_id" in columns:
        return

    conn.execute("ALTER TABLE semantic_facts RENAME TO semantic_facts_old")
    _create_table(conn)
    conn.execute(
        """
        INSERT OR IGNORE INTO semantic_facts (tenant_id, phone, fact, created_at)
        SELECT 'default', phone, fact, created_at FROM semantic_facts_old
        """
    )
    conn.execute("DROP TABLE semantic_facts_old")


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    _create_table(conn)
    _migrate_legacy_schema(conn)
    return conn


def recall(tenant_id: str, phone: str, limit: int = 20) -> list[str]:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            """
            SELECT fact FROM semantic_facts
            WHERE tenant_id = ? AND phone = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (tenant_id, phone, limit),
        ).fetchall()
        conn.close()
    return [row[0] for row in rows]


def store(tenant_id: str, phone: str, facts: list[str]) -> None:
    if not tenant_id or not phone or not facts:
        return

    now = datetime.now(UTC).isoformat()
    with _lock:
        conn = _connect()
        for fact in facts:
            clean = fact.strip()
            if clean:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO semantic_facts (tenant_id, phone, fact, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (tenant_id, phone, clean, now),
                )
        conn.commit()
        conn.close()
