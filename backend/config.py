"""
Centralized backend configuration.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: str | None, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(str(value)) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(parsed, minimum)
    return parsed


def _default_cors_origins() -> list[str]:
    local_hosts = ("http://localhost", "http://127.0.0.1")
    local_ports = (3000, 3001, 3002, 5173, 5174, 5175, 5176)
    return [f"{host}:{port}" for host in local_hosts for port in local_ports]


def _csv_env(value: str | None, fallback: list[str]) -> list[str]:
    raw = value if value is not None else ",".join(fallback)
    items = [part.strip() for part in str(raw).split(",") if part.strip()]
    return items or fallback


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    redis_url: str | None
    redis_host: str
    redis_port: int
    redis_db: int
    redis_key_prefix: str
    cors_origins: list[str]
    geovision_api_key: str | None
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int
    rag_persist_dir: str | None
    rag_ingest_on_startup: bool
    spatial_optimize_cache_ttl_seconds: int
    chroma_db_dir: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = str(os.getenv("ENVIRONMENT", "development")).strip().lower() or "development"
    is_production = environment in {"production", "prod"}

    postgres_host = str(os.getenv("POSTGRES_HOST", "localhost")).strip() or "localhost"
    postgres_port = _as_int(os.getenv("POSTGRES_PORT"), default=5432, minimum=1)
    postgres_db = str(os.getenv("POSTGRES_DB", "geovision")).strip() or "geovision"
    postgres_user = str(os.getenv("POSTGRES_USER", "postgres")).strip() or "postgres"
    postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    database_url = str(
        os.getenv(
            "DATABASE_URL",
            f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}",
        )
    ).strip()

    redis_host = str(os.getenv("REDIS_HOST", "localhost")).strip() or "localhost"
    redis_port = _as_int(os.getenv("REDIS_PORT"), default=6379, minimum=1)
    redis_db = _as_int(os.getenv("REDIS_DB"), default=0, minimum=0)
    redis_url = str(
        os.getenv("REDIS_URL", f"redis://{redis_host}:{redis_port}/{redis_db}")
    ).strip()
    redis_url = redis_url or None

    raw_secret = os.getenv("JWT_SECRET_KEY")
    if not raw_secret:
        if is_production:
            raise RuntimeError(
                "JWT_SECRET_KEY environment variable is not set. "
                "Set a strong random secret before starting in production."
            )
        warnings.warn(
            "JWT_SECRET_KEY is not set — using insecure default. "
            "Set JWT_SECRET_KEY before deploying to production.",
            stacklevel=1,
        )
    jwt_secret_key = raw_secret or "dev-only-insecure-default-change-before-production"

    return Settings(
        environment=environment,
        database_url=database_url,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        postgres_db=postgres_db,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        redis_url=redis_url,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        redis_key_prefix=str(os.getenv("REDIS_KEY_PREFIX", "geovision")).strip() or "geovision",
        cors_origins=_csv_env(os.getenv("CORS_ORIGINS"), _default_cors_origins()),
        geovision_api_key=(str(os.getenv("GEOVISION_API_KEY", "")).strip() or None),
        jwt_secret_key=jwt_secret_key,
        jwt_algorithm=str(os.getenv("JWT_ALGORITHM", "HS256")).strip() or "HS256",
        jwt_access_token_expire_minutes=_as_int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES"),
            default=60 * 24,
            minimum=1,
        ),
        rag_persist_dir=(str(os.getenv("RAG_PERSIST_DIR", "")).strip() or None),
        rag_ingest_on_startup=_as_bool(os.getenv("RAG_INGEST_ON_STARTUP"), default=False),
        spatial_optimize_cache_ttl_seconds=_as_int(
            os.getenv("SPATIAL_OPTIMIZE_CACHE_TTL_SECONDS"),
            default=900,
            minimum=0,
        ),
        chroma_db_dir=str(
            os.getenv("CHROMA_DB_DIR", "agent/zoning_agent/src/chroma_db")
        ).strip() or "agent/zoning_agent/src/chroma_db",
    )


def reset_settings_cache_for_tests() -> None:
    get_settings.cache_clear()
