import hashlib
import json
import logging
import math
import os
import sqlite3
import struct
import threading
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))
RAG_DIR = DATA_DIR / "rag"

_lock = threading.Lock()
_SUPPORTED_SUFFIXES = {".md", ".txt"}


def is_rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes"}


def _db_path(tenant_id: str) -> Path:
    return RAG_DIR / f"{tenant_id}.db"


def _connect(tenant_id: str) -> sqlite3.Connection:
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path(tenant_id))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            tenant_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, source_path)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            tenant_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            PRIMARY KEY (tenant_id, source_path, chunk_index)
        )
        """
    )
    return conn


def _pack_embedding(values: list[float]) -> bytes:
    return struct.pack(f"{len(values)}f", *values)


def _unpack_embedding(blob: bytes) -> list[float]:
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def discover_knowledge_files(knowledge_dir: Path) -> list[Path]:
    if not knowledge_dir.is_dir():
        return []

    files: list[Path] = []
    for path in sorted(knowledge_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        if path.name.upper() == "README.MD" and path.stat().st_size < 200:
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        files.append(path)
    return files


def _relative_source(knowledge_dir: Path, file_path: Path) -> str:
    return f"knowledge/{file_path.relative_to(knowledge_dir).as_posix()}"


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_indexed_sources(tenant_id: str) -> dict[str, str]:
    with _lock:
        conn = _connect(tenant_id)
        rows = conn.execute(
            "SELECT source_path, content_hash FROM knowledge_sources WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchall()
        conn.close()
    return {row[0]: row[1] for row in rows}


def delete_source(tenant_id: str, source_path: str) -> None:
    with _lock:
        conn = _connect(tenant_id)
        conn.execute(
            "DELETE FROM knowledge_chunks WHERE tenant_id = ? AND source_path = ?",
            (tenant_id, source_path),
        )
        conn.execute(
            "DELETE FROM knowledge_sources WHERE tenant_id = ? AND source_path = ?",
            (tenant_id, source_path),
        )
        conn.commit()
        conn.close()


def save_chunks(
    tenant_id: str,
    source_path: str,
    content_hash: str,
    chunks: list[tuple[int, str, list[float]]],
) -> None:
    now = datetime.now(UTC).isoformat()
    with _lock:
        conn = _connect(tenant_id)
        conn.execute(
            "DELETE FROM knowledge_chunks WHERE tenant_id = ? AND source_path = ?",
            (tenant_id, source_path),
        )
        for chunk_index, text, embedding in chunks:
            conn.execute(
                """
                INSERT INTO knowledge_chunks
                (tenant_id, source_path, chunk_index, text, embedding)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_id, source_path, chunk_index, text, _pack_embedding(embedding)),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_sources
            (tenant_id, source_path, content_hash, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (tenant_id, source_path, content_hash, now),
        )
        conn.commit()
        conn.close()


def load_all_chunks(tenant_id: str) -> list[tuple[str, str, list[float]]]:
    with _lock:
        conn = _connect(tenant_id)
        rows = conn.execute(
            """
            SELECT source_path, text, embedding FROM knowledge_chunks
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        ).fetchall()
        conn.close()
    return [(row[0], row[1], _unpack_embedding(row[2])) for row in rows]


def chunk_count(tenant_id: str) -> int:
    with _lock:
        conn = _connect(tenant_id)
        row = conn.execute(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        conn.close()
    return int(row[0]) if row else 0


def chunks_by_tenant(tenant_ids: list[str]) -> dict[str, int]:
    return {tenant_id: chunk_count(tenant_id) for tenant_id in tenant_ids}
