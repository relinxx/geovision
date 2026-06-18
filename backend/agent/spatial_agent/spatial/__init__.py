"""Spatial Agent package for NSGA-II based land-use optimization."""

from __future__ import annotations

from .config import DEFAULT_LAND_USE_LABELS, NSGA2Config, SpatialConfig
from .objectives import (
    default_objectives,
    environmental_risk_exposure,
    fragmentation_penalty,
    make_green_area_deviation,
    make_land_use_balance_penalty,
    mean_suitability_loss,
    zoning_violation_penalty,
)
from .types import (
    Individual,
    ObjectiveFunction,
    OptimizationContext,
    OptimizationPlan,
    OptimizationResult,
    ParcelAssignment,
    ParcelRecord,
)

__all__ = [
    "DEFAULT_LAND_USE_LABELS",
    "NSGA2Config",
    "SpatialConfig",
    "SpatialOptimizer",
    "ObjectiveFunction",
    "OptimizationContext",
    "ParcelRecord",
    "ParcelAssignment",
    "OptimizationPlan",
    "OptimizationResult",
    "Individual",
    "build_parcels_from_geojson",
    "build_adjacency_from_geojson",
    "build_context_from_geojson",
    "infer_allowed_use_labels",
    "default_objectives",
    "make_green_area_deviation",
    "environmental_risk_exposure",
    "zoning_violation_penalty",
    "fragmentation_penalty",
    "make_land_use_balance_penalty",
    "mean_suitability_loss",
]


_GEO_EXPORTS = {
    "build_parcels_from_geojson",
    "build_adjacency_from_geojson",
    "build_context_from_geojson",
    "infer_allowed_use_labels",
}


def __getattr__(name: str):
    if name == "SpatialOptimizer":
        from .optimizer import SpatialOptimizer

        return SpatialOptimizer
    if name in _GEO_EXPORTS:
        from . import geo

        return getattr(geo, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
