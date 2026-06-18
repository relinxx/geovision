"""GeoJSON helpers for converting parcel features into optimization records."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
import logging
import time
from typing import Any

import numpy as np
from shapely import STRtree
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from .config import DEFAULT_LAND_USE_LABELS
from .types import AdjacencyMap, OptimizationContext, ParcelRecord

logger = logging.getLogger(__name__)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(max(value, lower), upper)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_geometry(feature: Mapping[str, Any]) -> BaseGeometry:
    feature_id = feature.get("id", "unknown")
    raw_geometry = feature.get("geometry")
    if not raw_geometry:
        logger.debug("Geometry missing | feature_id=%s | fallback=Point(0,0)", feature_id)
        return Point(0.0, 0.0)
    try:
        geometry = shape(raw_geometry)
        if geometry.is_empty:
            return Point(0.0, 0.0)
        if not geometry.is_valid:
            try:
                geometry = make_valid(geometry)
            except Exception:
                geometry = geometry.buffer(0)
        if geometry.is_empty:
            return Point(0.0, 0.0)
        return geometry
    except Exception:
        logger.warning(
            "Geometry extraction failed | feature_id=%s | fallback=Point(0,0)",
            feature_id,
            exc_info=True,
        )
        return Point(0.0, 0.0)


def _geometry_area_m2(geometry: BaseGeometry) -> float:
    if geometry.is_empty:
        return 0.0
    try:
        from pyproj import Geod
        geod = Geod(ellps="WGS84")
        area, _ = geod.geometry_area_perimeter(geometry)
        return float(abs(area))
    except Exception:
        return float(abs(geometry.area))


def normalize_risk_score(properties: Mapping[str, Any]) -> float:
    if "risk_score_norm" in properties:
        return _clamp(_safe_float(properties.get("risk_score_norm"), 0.0))
    if "environmental_risk" in properties:
        return _clamp(_safe_float(properties.get("environmental_risk"), 0.0))
    if "xgb_risk_score" in properties:
        return _clamp(_safe_float(properties.get("xgb_risk_score"), 0.0) / 100.0)
    if "rule_risk_score" in properties:
        return _clamp(_safe_float(properties.get("rule_risk_score"), 0.0) / 100.0)
    return 0.0


def _risk_to_suitability_scores(risk_norm: float) -> dict[str, float]:
    risk = _clamp(float(risk_norm))

    return {
        "residential": max(0.0, 0.8 - risk),
        "commercial": max(0.0, 0.7 - risk * 0.8),
        "industrial": max(0.0, 0.6 - risk * 0.5),
        "green": min(1.0, 0.2 + risk),
    }


def extract_suitability_scores(
    properties: Mapping[str, Any],
    land_use_labels: Sequence[str] = DEFAULT_LAND_USE_LABELS,
) -> dict[str, float]:
    normalized_labels = tuple(label.strip().lower() for label in land_use_labels)

    scores: dict[str, float] = {}
    found_explicit_score = False

    for label in normalized_labels:
        raw_score = properties.get(f"suitability_{label}")
        if raw_score is None:
            raw_score = properties.get(label)

        if raw_score is not None:
            found_explicit_score = True
            scores[label] = _clamp(_safe_float(raw_score, 0.0))
        else:
            scores[label] = 0.0

    if found_explicit_score:
        return scores

    has_risk_signal = any(
        properties.get(key) not in (None, "")
        for key in (
            "risk_score_norm",
            "environmental_risk",
            "xgb_risk_score",
            "rule_risk_score",
        )
    )

    if has_risk_signal:
        derived = _risk_to_suitability_scores(normalize_risk_score(properties))
        return {
            label: derived.get(label, 0.0)
            for label in normalized_labels
        }

    return scores

def infer_allowed_use_labels(
    properties: Mapping[str, Any],
    land_use_labels: Sequence[str] = DEFAULT_LAND_USE_LABELS,
) -> tuple[str, ...]:
    normalized_labels = tuple(label.strip().lower() for label in land_use_labels)

    explicit = properties.get("allowed_uses")
    if explicit:
        if isinstance(explicit, str):
            tokens = [t.strip().lower() for t in explicit.split(",") if t]
        elif isinstance(explicit, Iterable):
            tokens = [str(t).strip().lower() for t in explicit if t]
        else:
            tokens = []
        from_explicit = tuple(l for l in normalized_labels if l in tokens)
        if from_explicit:
            return from_explicit

    text_blob = " ".join(
        str(properties.get(f, ""))
        for f in ("ZONING_CODE", "GP_LAND_USE", "zoning_code", "gp_land_use")
    ).lower()

    allowed: set[str] = set()
    keyword_map: dict[str, tuple[str, ...]] = {
        "residential": ("residential", "rs", "rm", "r-"),
        "commercial":  ("commercial",  "cn", "cc", "cg", "c-"),
        "industrial":  ("industrial",  "ig", "il", "ih", "i-"),
        "green":       ("green", "open space", "park", "agri", "conservation"),
    }

    if "mixed" in text_blob:
        allowed.update({"residential", "commercial"})

    for label in normalized_labels:
        for token in keyword_map.get(label, ()):
            if token in text_blob:
                allowed.add(label)
                break

    if not allowed:
        return normalized_labels
    return tuple(l for l in normalized_labels if l in allowed)


def build_parcels_from_geojson(
    features: Iterable[Mapping[str, Any]],
    land_use_labels: Sequence[str] = DEFAULT_LAND_USE_LABELS,
) -> tuple[ParcelRecord, ...]:
    started_at = time.perf_counter()
    feature_list = list(features)
    normalized_labels = tuple(l.strip().lower() for l in land_use_labels)
    use_code_lookup = {label: idx for idx, label in enumerate(normalized_labels)}
    default_allowed_codes = tuple(range(len(normalized_labels)))

    parcels: list[ParcelRecord] = []
    for index, feature in enumerate(feature_list):
        properties = feature.get("properties", {})
        if not isinstance(properties, Mapping):
            properties = {}

        geometry = _extract_geometry(feature)
        centroid  = geometry.centroid if not geometry.is_empty else Point(0.0, 0.0)

        centroid_data = properties.get("centroid")
        if isinstance(centroid_data, Mapping):
            centroid_x = _safe_float(centroid_data.get("x"), float(centroid.x))
            centroid_y = _safe_float(centroid_data.get("y"), float(centroid.y))
        else:
            centroid_x = _safe_float(properties.get("centroid_x"), float(centroid.x))
            centroid_y = _safe_float(properties.get("centroid_y"), float(centroid.y))

        parcel_id_candidates = (
            properties.get("parcel_id"), properties.get("parcelId"),
            properties.get("APN"),       properties.get("apn"),
            properties.get("PARCELID"),  properties.get("PARNO"),
            properties.get("join_key"),  properties.get("id"),
            feature.get("id"),           f"parcel-{index}",
        )
        parcel_id = next(
            (str(c).strip() for c in parcel_id_candidates if c is not None and str(c).strip()),
            f"parcel-{index}",
        )

        allowed_labels = infer_allowed_use_labels(properties, normalized_labels)
        allowed_codes  = tuple(
            use_code_lookup[l] for l in allowed_labels if l in use_code_lookup
        ) or default_allowed_codes

        parcels.append(ParcelRecord(
            parcel_id        = parcel_id,
            area_m2          = _geometry_area_m2(geometry),
            centroid_x       = centroid_x,
            centroid_y       = centroid_y,
            risk_score_norm  = normalize_risk_score(properties),
            suitability      = extract_suitability_scores(properties, normalized_labels),
            allowed_use_codes= allowed_codes,
            properties       = dict(properties),
        ))

    logger.debug(
        "Parcel build completed | parcel_count=%d | elapsed_seconds=%.4f",
        len(parcels), time.perf_counter() - started_at,
    )
    return tuple(parcels)


def build_adjacency_from_geojson(
    features: Sequence[Mapping[str, Any]],
    adjacency_predicate: str = "touches",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AdjacencyMap:
    """
    Build an undirected parcel adjacency map using STRtree bulk query.

    Replaces the original O(n²) nested loop (one Shapely predicate call per
    pair) with a single vectorized STRtree.query() call.  Shapely 2.0 releases
    the GIL during predicate queries so this is also thread-safe.

    Expected speedup vs. the loop: 10-100× depending on parcel count and
    geometry complexity.
    """
    started_at = time.perf_counter()
    total = len(features)

    def emit(event: dict[str, Any]) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(event)
        except Exception:
            logger.debug("Adjacency progress callback failed | stage=%s", event.get("stage"), exc_info=True)

    emit({"stage": "adjacency_started", "total_items": total,
          "elapsed_seconds": 0.0, "predicate": adjacency_predicate})

    # Extract geometries; track which indices are non-empty (STRtree needs valid geoms)
    all_geoms     = [_extract_geometry(f) for f in features]
    valid_indices = [i for i, g in enumerate(all_geoms) if not g.is_empty]
    valid_geoms   = [all_geoms[i] for i in valid_indices]

    neighbors: dict[int, set[int]] = {i: set() for i in range(total)}

    if len(valid_geoms) >= 2:
        tree   = STRtree(valid_geoms)
        result = tree.query(valid_geoms, predicate=adjacency_predicate)
        # result shape: (2, n_pairs)
        # result[0] = positions in valid_geoms (left)
        # result[1] = positions in valid_geoms (right)
        if result.size > 0:
            for left_pos, right_pos in zip(result[0], result[1]):
                if left_pos == right_pos:
                    continue  # self-touch guard (can occur with "intersects")
                left_orig  = valid_indices[left_pos]
                right_orig = valid_indices[right_pos]
                neighbors[left_orig].add(right_orig)
                # STRtree returns symmetric pairs so right→left is also covered,
                # but adding both sides defensively costs nothing.
                neighbors[right_orig].add(left_orig)

    edge_count = sum(len(v) for v in neighbors.values()) // 2
    elapsed    = time.perf_counter() - started_at

    logger.debug(
        "Adjacency build completed | nodes=%d | valid_nodes=%d | edges=%d | elapsed_seconds=%.4f",
        total, len(valid_geoms), edge_count, elapsed,
    )
    emit({
        "stage":        "adjacency_completed",
        "total_items":  total,
        "elapsed_seconds": elapsed,
        "comparisons":  len(valid_geoms) ** 2 // 2,  # equivalent work if done as loop
        "edge_count":   edge_count,
    })

    return {i: tuple(sorted(vs)) for i, vs in neighbors.items()}


def build_context_from_geojson(
    features: Iterable[Mapping[str, Any]],
    land_use_labels: Sequence[str] = DEFAULT_LAND_USE_LABELS,
    include_adjacency: bool = True,
    adjacency_predicate: str = "touches",
) -> OptimizationContext:
    started_at   = time.perf_counter()
    feature_list = list(features)
    parcels      = build_parcels_from_geojson(feature_list, land_use_labels)
    adjacency: AdjacencyMap = {}
    if include_adjacency:
        adjacency = build_adjacency_from_geojson(feature_list, adjacency_predicate=adjacency_predicate)
    logger.debug(
        "Context build completed | parcel_count=%d | adjacency_nodes=%d | elapsed_seconds=%.4f",
        len(parcels), len(adjacency), time.perf_counter() - started_at,
    )
    return OptimizationContext(
        parcels=parcels,
        land_use_labels=tuple(land_use_labels),
        adjacency=adjacency,
    )
