"""Shared service helpers used by main.py and orchestrator_steps.py."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent.environment_agent.agent import SuitabilityAgent, find_default_risk_data_path
from config import get_settings

_suitability_agent: Optional[SuitabilityAgent] = None


def resolve_rag_persist_dir(backend_dir: Path) -> Path:
    settings = get_settings()
    configured = settings.rag_persist_dir or settings.chroma_db_dir
    configured_path = Path(configured).expanduser()
    return configured_path if configured_path.is_absolute() else (backend_dir / configured_path)


def get_suitability_agent() -> SuitabilityAgent:
    """Return the process-wide SuitabilityAgent singleton (lazy-initialized)."""
    global _suitability_agent
    if _suitability_agent is None:
        _suitability_agent = SuitabilityAgent(model_path=find_default_risk_data_path())
    return _suitability_agent
