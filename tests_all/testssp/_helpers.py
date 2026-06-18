"""Shared fixtures/helpers for Spatial Agent tests."""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from agent.spatial_agent.spatial.config import DEFAULT_LAND_USE_LABELS  # noqa: E402
from agent.spatial_agent.spatial.types import OptimizationContext, ParcelRecord  # noqa: E402


def make_sample_parcels() -> tuple[ParcelRecord, ...]:
    """Build a small deterministic parcel set for objective/optimizer tests."""
    return (
        ParcelRecord(
            parcel_id="p1",
            area_m2=100.0,
            centroid_x=0.0,
            centroid_y=0.0,
            risk_score_norm=0.2,
            suitability={
                "residential": 0.9,
                "commercial": 0.3,
                "industrial": 0.1,
                "green": 0.4,
            },
            allowed_use_codes=(0, 3),
        ),
        ParcelRecord(
            parcel_id="p2",
            area_m2=110.0,
            centroid_x=1.0,
            centroid_y=0.0,
            risk_score_norm=0.8,
            suitability={
                "residential": 0.2,
                "commercial": 0.6,
                "industrial": 0.7,
                "green": 0.9,
            },
            allowed_use_codes=(1, 2, 3),
        ),
        ParcelRecord(
            parcel_id="p3",
            area_m2=90.0,
            centroid_x=2.0,
            centroid_y=0.0,
            risk_score_norm=0.5,
            suitability={
                "residential": 0.5,
                "commercial": 0.7,
                "industrial": 0.4,
                "green": 0.6,
            },
            allowed_use_codes=(0, 1, 2, 3),
        ),
    )


def make_sample_context() -> OptimizationContext:
    """Build a deterministic optimization context."""
    return OptimizationContext(
        parcels=make_sample_parcels(),
        land_use_labels=DEFAULT_LAND_USE_LABELS,
        adjacency={
            0: (1,),
            1: (0, 2),
            2: (1,),
        },
    )
