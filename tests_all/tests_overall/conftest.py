"""
Shared pytest fixtures for backend endpoint tests.

Endpoint tests should check API behavior:
- status codes
- response shape
- request validation
- whether the endpoint calls the correct service/model

They should NOT run heavy things like:
- real RAG / ChromaDB
- real OpenAI
- real Redis
- real PostgreSQL
- full optimizer runs
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from datetime import datetime
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Make backend imports reliable
# ---------------------------------------------------------------------------
# This makes modules like main.py, services/, schemas/, agent/ importable even
# if pytest chooses a different root directory.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ---------------------------------------------------------------------------
# Safe testing environment
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAG_INGEST_ON_STARTUP", "false")
os.environ.setdefault("SPATIAL_OPTIMIZE_CACHE_TTL_SECONDS", "0")
os.environ.setdefault("GEOVISION_API_KEY", "")


# ---------------------------------------------------------------------------
# Optional dependency stubs
# ---------------------------------------------------------------------------
# Your main.py imports RAG/auth/database modules at startup.
# These stubs prevent endpoint tests from failing just because optional packages
# like ChromaDB are missing in the local test environment.

if importlib.util.find_spec("chromadb") is None:
    fake_chromadb = types.ModuleType("chromadb")
    fake_chromadb.PersistentClient = lambda *args, **kwargs: None

    fake_chromadb_utils = types.ModuleType("chromadb.utils")
    fake_embedding_functions = types.ModuleType("chromadb.utils.embedding_functions")
    fake_embedding_functions.SentenceTransformerEmbeddingFunction = lambda *args, **kwargs: None

    fake_chromadb_config = types.ModuleType("chromadb.config")
    fake_chromadb_config.Settings = lambda *args, **kwargs: None

    sys.modules["chromadb"] = fake_chromadb
    sys.modules["chromadb.utils"] = fake_chromadb_utils
    sys.modules["chromadb.utils.embedding_functions"] = fake_embedding_functions
    sys.modules["chromadb.config"] = fake_chromadb_config


if importlib.util.find_spec("pypdf") is None:
    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = lambda *args, **kwargs: None
    sys.modules["pypdf"] = fake_pypdf


if importlib.util.find_spec("bcrypt") is None:
    fake_bcrypt = types.ModuleType("bcrypt")
    fake_bcrypt.gensalt = lambda *args, **kwargs: b"test-salt"
    fake_bcrypt.hashpw = lambda password, salt: b"test-hash"
    fake_bcrypt.checkpw = lambda password, hashed: True
    sys.modules["bcrypt"] = fake_bcrypt


if importlib.util.find_spec("jose") is None:
    fake_jose = types.ModuleType("jose")

    class JWTError(Exception):
        pass

    fake_jose.JWTError = JWTError
    fake_jose.jwt = types.SimpleNamespace(
        encode=lambda payload, key, algorithm=None: "test-access-token",
        decode=lambda token, key, algorithms=None: {"sub": 1},
    )
    sys.modules["jose"] = fake_jose


try:
    from alembic import command as _alembic_command  # noqa: F401
    from alembic.config import Config as _AlembicConfig  # noqa: F401
except Exception:
    fake_alembic = types.ModuleType("alembic")
    fake_alembic_command = types.ModuleType("alembic.command")
    fake_alembic_command.upgrade = lambda *args, **kwargs: None

    fake_alembic_config = types.ModuleType("alembic.config")

    class AlembicConfig:
        def __init__(self, *args, **kwargs):
            pass

        def set_main_option(self, *args, **kwargs):
            pass

    fake_alembic_config.Config = AlembicConfig
    fake_alembic.command = fake_alembic_command

    sys.modules["alembic"] = fake_alembic
    sys.modules["alembic.command"] = fake_alembic_command
    sys.modules["alembic.config"] = fake_alembic_config


if importlib.util.find_spec("psycopg2") is None:
    fake_psycopg2 = types.ModuleType("psycopg2")

    class IntegrityError(Exception):
        pass

    fake_psycopg2.IntegrityError = IntegrityError
    fake_psycopg2.connect = lambda *args, **kwargs: None

    fake_psycopg2_extras = types.ModuleType("psycopg2.extras")

    class RealDictCursor:
        pass

    fake_psycopg2_extras.RealDictCursor = RealDictCursor

    fake_psycopg2_extensions = types.ModuleType("psycopg2.extensions")

    class connection:
        pass

    fake_psycopg2_extensions.connection = connection

    sys.modules["psycopg2"] = fake_psycopg2
    sys.modules["psycopg2.extras"] = fake_psycopg2_extras
    sys.modules["psycopg2.extensions"] = fake_psycopg2_extensions


@pytest.fixture
def sample_polygon_feature() -> dict:
    """
    Tiny valid GeoJSON parcel used by many endpoint tests.
    """
    return {
        "type": "Feature",
        "id": "parcel-1",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 1.0],
                    [0.0, 1.0],
                    [0.0, 0.0],
                ]
            ],
        },
        "properties": {
            "APN": "parcel-1",
            "centroid": {"x": 0.5, "y": 0.5},
            "environmental_risk": 0.25,
            "residential": 0.8,
            "commercial": 0.4,
            "industrial": 0.2,
            "green": 0.6,
            "ZONING_CODE": "RS-1-7",
            "JURISDICTION": "City of San Diego",
        },
    }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """
    FastAPI test client with heavy startup disabled.
    """
    import main

    # Do not initialize real RAG/Chroma/OpenAI during endpoint tests.
    monkeypatch.setattr(main, "_init_rag", lambda: None)
    monkeypatch.setattr(main, "_rag", None)
    monkeypatch.setattr(main, "_rag_unavailable_reason", "disabled in endpoint tests")
    monkeypatch.setattr(main, "_redis_store", None)

    # Do not use real Redis cache in endpoint tests.
    monkeypatch.setattr(main, "_get_redis_store_cached", lambda: None)
    monkeypatch.setattr(main, "get_spatial_optimize_cache_ttl_seconds", lambda: 0)

    with TestClient(main.app) as test_client:
        yield test_client

    # Prevent dependency overrides from leaking between tests.
    main.app.dependency_overrides.clear()


class FakeSteps:
    """Matches job.steps.to_dict() used by orchestrator router."""

    def to_dict(self) -> dict:
        return {
            "environment": "completed",
            "zoning": "completed",
            "merge": "completed",
            "spatial": "pending",
        }


@pytest.fixture
def fake_completed_job():
    """Fake completed orchestrator job object."""
    from types import SimpleNamespace

    return SimpleNamespace(
        job_id="job-123",
        status="completed",
        progress=100,
        stage="completed",
        steps=FakeSteps(),
        error=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )