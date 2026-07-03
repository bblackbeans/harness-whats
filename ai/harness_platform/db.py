import os
from collections.abc import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DEFAULT_URL = "postgresql+psycopg2://harness:harness@localhost:5432/harness"


def normalize_database_url(url: str) -> str:
    """Aceita postgres:// (Easypanel, Railway, etc.) e força driver psycopg2."""
    raw = url.strip()
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://") and "+" not in raw.split("://", 1)[0]:
        return "postgresql+psycopg2://" + raw[len("postgresql://") :]
    return raw


def resolve_database_url() -> str:
    """Monta URL com senha escapada — evita quebrar quando a senha contém @ ou :."""
    host = os.getenv("POSTGRES_HOST", "").strip()
    if host:
        user = os.getenv("POSTGRES_USER", "harness").strip()
        password = os.getenv("POSTGRES_PASSWORD", "harness")
        port = os.getenv("POSTGRES_PORT", "5432").strip()
        database = os.getenv("POSTGRES_DB", "harness").strip()
        sslmode = os.getenv("POSTGRES_SSLMODE", "").strip()
        query = f"?sslmode={quote_plus(sslmode)}" if sslmode else ""
        return (
            f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{database}{query}"
        )

    raw = os.getenv("DATABASE_URL", "").strip()
    return normalize_database_url(raw or _DEFAULT_URL)


DATABASE_URL = resolve_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_db_configured() -> bool:
    return bool(os.getenv("POSTGRES_HOST", "").strip() or os.getenv("DATABASE_URL", "").strip())
