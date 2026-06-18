"""
Spatial optimization cache helpers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List

from config import get_settings

PARCEL_ID_CANDIDATES = (
    "APN",
    "apn",
    "parcel_id",
    "parcelId",
    "PARCELID",
    "PARNO",
    "id",
    "OBJECTID",
)

SPATIAL_OPTIMIZE_CACHE_VERSION = "v2"


def get_spatial_optimize_cache_ttl_seconds() -> int:
    return max(get_settings().spatial_optimize_cache_ttl_seconds, 0)


def extract_parcel_cache_id(feature: Dict[str, Any]) -> str:
    properties = feature.get("properties") or {}
    for key in PARCEL_ID_CANDIDATES:
        value = properties.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized

    fallback = feature.get("id")
    if fallback is not None:
        normalized = str(fallback).strip()
        if normalized:
            return normalized
    return ""


def normalize_target_mix(target_mix: Dict[str, Any] | None) -> Dict[str, float]:
    cleaned_mix: Dict[str, float] = {}
    for key, value in (target_mix or {}).items():
        label = str(key).strip().lower()
        if not label:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if numeric_value > 0.0:
            cleaned_mix[label] = numeric_value

    if not cleaned_mix:
        return {}

    total = sum(cleaned_mix.values())
    if total <= 0.0:
        return {}
    return {label: value / total for label, value in sorted(cleaned_mix.items())}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _canonicalize_features(features: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    decorated: list[tuple[str, str, Dict[str, Any]]] = []
    for feature in features:
        normalized_feature = feature if isinstance(feature, dict) else dict(feature)
        parcel_id = extract_parcel_cache_id(normalized_feature)
        serialized = _canonical_json(normalized_feature)
        decorated.append((parcel_id, serialized, normalized_feature))

    decorated.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in decorated]


def build_spatial_optimize_cache_key(
    *,
    features: Iterable[Dict[str, Any]],
    num_output_plans: int,
    population_size: int,
    generations: int,
    include_adjacency: bool,
    adjacency_predicate: str,
    target_mix: Dict[str, float],
    use_spatial_compatibility: bool = False,
    spatial_neighbor_radius_m: float | None = None,
    spatial_compatibility_weight: float | None = None,
) -> str:
    payload = {
        "version": SPATIAL_OPTIMIZE_CACHE_VERSION,
        "features": _canonicalize_features(features),
        "settings": {
            "num_output_plans": int(num_output_plans),
            "population_size": int(population_size),
            "generations": int(generations),
            "include_adjacency": bool(include_adjacency),
            "adjacency_predicate": str(adjacency_predicate),
            "target_mix": dict(sorted(target_mix.items())),
            "use_spatial_compatibility": bool(use_spatial_compatibility),
            "spatial_neighbor_radius_m": (
                float(spatial_neighbor_radius_m)
                if use_spatial_compatibility and spatial_neighbor_radius_m is not None
                else None
            ),
            "spatial_compatibility_weight": (
                float(spatial_compatibility_weight)
                if use_spatial_compatibility and spatial_compatibility_weight is not None
                else None
            ),
        },
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"spatial:optimize:{digest}"
