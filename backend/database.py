"""
Database module for PostgreSQL connection and initialization.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config as AlembicConfig
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import connection as PGConnection

from config import get_settings


def _connect() -> PGConnection:
    settings = get_settings()
    return psycopg2.connect(settings.database_url)


def init_db() -> None:
    """Initialize PostgreSQL schema by running Alembic migrations."""
    settings = get_settings()
    backend_dir = Path(__file__).resolve().parent
    alembic_cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")


@contextmanager
def get_db() -> Iterator[PGConnection]:
    """Context manager for PostgreSQL connections with dict-like rows."""
    conn = psycopg2.connect(get_settings().database_url, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()
