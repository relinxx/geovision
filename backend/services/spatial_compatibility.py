"""Spatial compatibility helpers for neighbour-aware plan scoring.

The functions in this module are intentionally pure and request-scoped. They
precompute centroid neighbour pairs once, then score candidate assignments by
looping over that fixed pair list.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import math
from typing import Any

from agent.spatial_agent.spatial.types import Chromosome, ObjectiveFunction, OptimizationContext

PARCEL_ID_KEYS = (
    "APN",
    "apn",
    "parcel_id",
    "parcelId",
    "PARCELID",
    "PARNO",
    "join_key",
    "id",
)

RISK_FIELD_KEYS = (
    "xgb_risk_score",
    "rule_risk_score",
    "environmental_risk",
    "risk_score",
    "risk_score_norm",
)

LAND_USE_COMPATIBILITY_MATRIX: dict[str, dict[str, float]] = {
    "residential": {
        "residential": 2.0,
        "commercial": 0.5,
        "industrial": -4.0,
        "green": 1.0,
        "unknown": 0.0,
    },
    "commercial": {
        "residential": 0.5,
        "commercial": 2.0,
        "industrial": -1.0,
        "green": 0.0,
        "unknown": 0.0,
    },
    "industrial": {
        "residential": -4.0,
        "commercial": -1.0,
        "industrial": 2.0,
        "green": -2.0,
        "unknown": 0.0,
    },
    "green": {
        "residential": 1.0,
        "commercial": 0.0,
        "industrial": -2.0,
        "green": 3.0,
        "unknown": 0.0,
    },
    "unknown": {
        "residential": 0.0,
        "commercial": 0.0,
        "industrial": 0.0,
        "green": 0.0,
        "unknown": 0.0,
    },
}

_LAND_USE_ALIASES: dict[str, str] = {
    "res": "residential",
    "r": "residential",
    "housing": "residential",
    "house": "residential",
    "homes": "residential",
    "commercial": "commercial",
    "com": "commercial",
    "c": "commercial",
    "retail": "commercial",
    "mixed": "commercial",
    "mixeduse": "commercial",
    "mixed_use": "commercial",
    "mixed-use": "commercial",
    "industrial": "industrial",
    "ind": "industrial",
    "i": "industrial",
    "manufacturing": "industrial",
    "warehouse": "industrial",
    "warehousing": "industrial",
    "green": "green",
    "open_space": "green",
    "openspace": "green",
    "open-space": "green",
    "park": "green",
    "parks": "green",
    "conservation": "green",
    "recreation": "green",
    "recreational": "green",
}

NeighborPair = tuple[str, str, float]


def normalize_land_use(value: str | None) -> str:
    """Normalize a land-use label into the optimizer's supported buckets."""
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower()
    if not normalized:
        return "unknown"
    normalized = normalized.replace(" ", "_")
    if normalized in LAND_USE_COMPATIBILITY_MATRIX:
        return normalized
    return _LAND_USE_ALIASES.get(normalized, "unknown")


def normalize_risk_value(value: Any) -> float:
    """Normalize risk values to 0..1, accepting both fractions and percentages."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric > 1.0 and numeric <= 100.0:
        numeric = numeric / 100.0
    return min(max(numeric, 0.0), 1.0)


def build_parcel_feature_lookup(
    features: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Build a unique parcel feature lookup keyed by common parcel ID fields."""
    lookup: dict[str, Mapping[str, Any]] = {}
    for index, feature in enumerate(features):
        parcel_id = _extract_parcel_id(feature, fallback=f"parcel-{index}")
        if not parcel_id or parcel_id in lookup:
            continue
        lookup[parcel_id] = feature
    return lookup


def build_neighbor_pairs(
    parcel_ids: Sequence[str],
    parcel_feature_lookup: Mapping[str, Mapping[str, Any]],
    radius_m: float,
) -> list[NeighborPair]:
    """Return unique centroid-neighbour pairs within ``radius_m``."""
    try:
        radius = float(radius_m)
    except (TypeError, ValueError):
        return []
    if radius <= 0.0:
        return []

    unique_ids = list(dict.fromkeys(str(parcel_id) for parcel_id in parcel_ids if parcel_id))
    centroids: dict[str, tuple[float, float]] = {}
    for parcel_id in unique_ids:
        feature = parcel_feature_lookup.get(parcel_id)
        if not feature:
            continue
        centroid = _extract_centroid(feature)
        if centroid is not None:
            centroids[parcel_id] = centroid

    pairs: list[NeighborPair] = []
    for left_index, left_id in enumerate(unique_ids):
        left_centroid = centroids.get(left_id)
        if left_centroid is None:
            continue
        for right_id in unique_ids[left_index + 1:]:
            right_centroid = centroids.get(right_id)
            if right_centroid is None or right_id == left_id:
                continue
            distance_m = _haversine_m(left_centroid[0], left_centroid[1], right_centroid[0], right_centroid[1])
            if distance_m <= radius:
                pairs.append((left_id, right_id, distance_m))
    return pairs


def score_spatial_compatibility(
    assignments: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    neighbor_pairs: Sequence[NeighborPair],
    parcel_feature_lookup: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Score a decoded plan against precomputed neighbour pairs."""
    summary = {
        "neighbor_pairs_evaluated": 0,
        "compatible_pairs": 0,
        "conflict_pairs": 0,
        "green_buffer_pairs": 0,
        "industrial_residential_conflicts": 0,
    }
    if not neighbor_pairs:
        return {"score": 0.0, "raw_score": 0.0, "summary": summary}

    assignment_lookup = _coerce_assignment_lookup(assignments)
    raw_score = 0.0

    for left_id, right_id, _distance_m in neighbor_pairs:
        left_use = normalize_land_use(assignment_lookup.get(left_id))
        right_use = normalize_land_use(assignment_lookup.get(right_id))
        pair_score = _compatibility_value(left_use, right_use)

        left_risk = _extract_feature_risk(parcel_feature_lookup.get(left_id))
        right_risk = _extract_feature_risk(parcel_feature_lookup.get(right_id))
        max_risk = max(left_risk, right_risk)

        has_green = left_use == "green" or right_use == "green"
        has_industrial = left_use == "industrial" or right_use == "industrial"
        has_residential = left_use == "residential" or right_use == "residential"
        has_sensitive_built = left_use in {"residential", "commercial"} or right_use in {"residential", "commercial"}

        if has_green and max_risk >= 0.6:
            pair_score += 0.75
            summary["green_buffer_pairs"] += 1
        if has_industrial and max_risk >= 0.6:
            pair_score -= 0.4
        if has_sensitive_built and max_risk >= 0.8:
            pair_score -= 0.25
        elif has_sensitive_built and max_risk >= 0.6:
            pair_score -= 0.15
        if has_industrial and has_residential:
            summary["industrial_residential_conflicts"] += 1

        summary["neighbor_pairs_evaluated"] += 1
        if pair_score > 0.0:
            summary["compatible_pairs"] += 1
        elif pair_score < 0.0:
            summary["conflict_pairs"] += 1
        raw_score += pair_score

    pair_count = summary["neighbor_pairs_evaluated"]
    if pair_count <= 0:
        return {"score": 0.0, "raw_score": 0.0, "summary": summary}

    average_pair_score = raw_score / pair_count
    normalized_score = (average_pair_score + 5.0) / 9.0
    normalized_score = min(max(normalized_score, 0.0), 1.0)
    return {
        "score": round(normalized_score, 4),
        "raw_score": round(raw_score, 4),
        "summary": summary,
    }


def explain_spatial_compatibility(
    assignments: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    neighbor_pairs: Sequence[NeighborPair],
    parcel_feature_lookup: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Generate deterministic, compact warnings/notes for plan display."""
    result = score_spatial_compatibility(assignments, neighbor_pairs, parcel_feature_lookup)
    summary = result["summary"]
    notes: list[str] = []
    industrial_residential_conflicts = int(summary["industrial_residential_conflicts"])
    green_buffer_pairs = int(summary["green_buffer_pairs"])
    conflict_pairs = int(summary["conflict_pairs"])

    if industrial_residential_conflicts > 0:
        notes.append(
            f"{industrial_residential_conflicts} industrial-residential proximity "
            f"conflict{'s were' if industrial_residential_conflicts != 1 else ' was'} detected."
        )
    elif conflict_pairs > 0:
        notes.append(
            f"{conflict_pairs} nearby land-use compatibility "
            f"conflict{'s were' if conflict_pairs != 1 else ' was'} detected."
        )
    if green_buffer_pairs > 0:
        notes.append(
            f"{green_buffer_pairs} green-buffer relationship"
            f"{'s' if green_buffer_pairs != 1 else ''} support environmental protection."
        )
    return notes


def explain_assignment_spatial_context(
    parcel_id: str,
    assignments: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    neighbor_pairs: Sequence[NeighborPair],
    parcel_feature_lookup: Mapping[str, Mapping[str, Any]],
    radius_m: float | None = None,
) -> dict[str, Any]:
    """Return local neighbour context for one parcel assignment.

    The optimizer scores the whole plan, while this helper explains how the
    clicked parcel relates to its nearby assigned neighbours.
    """
    resolved_parcel_id = str(parcel_id or "").strip()
    assignment_lookup = _coerce_assignment_lookup(assignments)
    assigned_use = normalize_land_use(assignment_lookup.get(resolved_parcel_id))

    local_pairs = [
        pair
        for pair in neighbor_pairs
        if pair[0] == resolved_parcel_id or pair[1] == resolved_parcel_id
    ]

    nearby_use_counts = {
        "residential": 0,
        "commercial": 0,
        "industrial": 0,
        "green": 0,
        "unknown": 0,
    }
    closest_neighbors: list[dict[str, Any]] = []
    reasons: list[str] = []
    warnings: list[str] = []

    compatible_pairs = 0
    conflict_pairs = 0
    green_buffer_pairs = 0
    industrial_residential_conflicts = 0

    center_risk = _extract_feature_risk(parcel_feature_lookup.get(resolved_parcel_id))

    for left_id, right_id, distance_m in local_pairs:
        other_id = right_id if left_id == resolved_parcel_id else left_id
        other_use = normalize_land_use(assignment_lookup.get(other_id))
        nearby_use_counts[other_use] = nearby_use_counts.get(other_use, 0) + 1

        pair_score = _compatibility_value(assigned_use, other_use)
        other_risk = _extract_feature_risk(parcel_feature_lookup.get(other_id))
        max_risk = max(center_risk, other_risk)

        has_green = assigned_use == "green" or other_use == "green"
        has_industrial = assigned_use == "industrial" or other_use == "industrial"
        has_residential = assigned_use == "residential" or other_use == "residential"

        if has_green and max_risk >= 0.6:
            pair_score += 0.75
            green_buffer_pairs += 1
        if has_industrial and max_risk >= 0.6:
            pair_score -= 0.4
        if has_industrial and has_residential:
            industrial_residential_conflicts += 1

        if pair_score > 0.0:
            compatible_pairs += 1
        elif pair_score < 0.0:
            conflict_pairs += 1

        closest_neighbors.append(
            {
                "parcel_id": other_id,
                "assigned_use": other_use,
                "distance_m": round(float(distance_m), 1),
                "compatibility_score": round(float(pair_score), 3),
            }
        )

    closest_neighbors.sort(key=lambda item: item["distance_m"])

    total_neighbors = len(local_pairs)
    same_use_count = nearby_use_counts.get(assigned_use, 0) if assigned_use != "unknown" else 0

    if total_neighbors <= 0:
        reasons.append(
            "No nearby assigned parcels were found within the spatial compatibility radius, so this assignment is not strongly influenced by local clustering."
        )
    else:
        if same_use_count > 0:
            label = assigned_use.replace("_", " ")
            reasons.append(
                f"Within the spatial compatibility radius, this parcel is near {same_use_count} other {label} assignment{'s' if same_use_count != 1 else ''}, which supports land-use clustering."
            )

        if green_buffer_pairs > 0:
            reasons.append(
                f"Nearby green/open-space relationships help buffer environmental risk in {green_buffer_pairs} local pair{'s' if green_buffer_pairs != 1 else ''}."
            )

        if assigned_use == "green" and center_risk >= 0.6:
            reasons.append(
                "This parcel has elevated environmental risk, so green assignment can support local buffering and lower-intensity use."
            )

        if industrial_residential_conflicts > 0:
            warnings.append(
                f"This parcel is involved in {industrial_residential_conflicts} industrial-residential proximity conflict{'s' if industrial_residential_conflicts != 1 else ''}; buffering or compatibility review is recommended."
            )
        elif conflict_pairs > 0:
            warnings.append(
                f"This parcel has {conflict_pairs} nearby land-use compatibility conflict{'s' if conflict_pairs != 1 else ''} within the selected radius."
            )

        if assigned_use == "industrial" and nearby_use_counts.get("green", 0) > 0:
            warnings.append(
                "Industrial assignment is close to green/open-space parcels, so environmental buffering and edge compatibility should be reviewed."
            )

    return {
        "enabled": True,
        "radius_m": radius_m,
        "assigned_use": assigned_use,
        "neighbor_pairs_evaluated": total_neighbors,
        "compatible_pairs": compatible_pairs,
        "conflict_pairs": conflict_pairs,
        "green_buffer_pairs": green_buffer_pairs,
        "industrial_residential_conflicts": industrial_residential_conflicts,
        "nearby_use_counts": nearby_use_counts,
        "closest_neighbors": closest_neighbors[:5],
        "reasons": reasons,
        "warnings": warnings,
    }


def make_spatial_compatibility_objective(
    neighbor_pairs: Sequence[NeighborPair],
    parcel_feature_lookup: Mapping[str, Mapping[str, Any]],
    weight: float = 0.15,
) -> ObjectiveFunction:
    """Create a minimization objective from the spatial compatibility score."""
    try:
        objective_weight = max(float(weight), 0.0)
    except (TypeError, ValueError):
        objective_weight = 0.15

    fixed_pairs = tuple(neighbor_pairs)

    def spatial_compatibility_penalty(
        chromosome: Chromosome,
        context: OptimizationContext,
    ) -> float:
        if not fixed_pairs or objective_weight <= 0.0:
            return 0.0
        decoded_assignments = {
            parcel.parcel_id: context.land_use_labels[gene]
            if 0 <= gene < len(context.land_use_labels)
            else "unknown"
            for gene, parcel in zip(chromosome, context.parcels)
        }
        score = float(
            score_spatial_compatibility(
                decoded_assignments,
                fixed_pairs,
                parcel_feature_lookup,
            )["score"]
        )
        return objective_weight * (1.0 - score)

    spatial_compatibility_penalty.__name__ = "spatial_compatibility_penalty"
    return spatial_compatibility_penalty


def _compatibility_value(left_use: str, right_use: str) -> float:
    return LAND_USE_COMPATIBILITY_MATRIX.get(left_use, {}).get(right_use, 0.0)


def _coerce_assignment_lookup(
    assignments: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    if isinstance(assignments, Mapping):
        return {str(parcel_id): str(value) for parcel_id, value in assignments.items()}

    lookup: dict[str, str] = {}
    for assignment in assignments:
        parcel_id = assignment.get("parcel_id") or assignment.get("parcelId")
        use_label = assignment.get("use_label") or assignment.get("assigned_use") or assignment.get("land_use")
        if parcel_id is None or use_label is None:
            continue
        lookup[str(parcel_id)] = str(use_label)
    return lookup


def _extract_feature_risk(feature: Mapping[str, Any] | None) -> float:
    if not feature:
        return 0.0
    properties = feature.get("properties") or {}
    if not isinstance(properties, Mapping):
        return 0.0
    for key in RISK_FIELD_KEYS:
        if key in properties:
            return normalize_risk_value(properties.get(key))
    return 0.0


def _extract_parcel_id(feature: Mapping[str, Any], fallback: str = "") -> str:
    properties = feature.get("properties") or {}
    if isinstance(properties, Mapping):
        for key in PARCEL_ID_KEYS:
            value = properties.get(key)
            if value is None:
                continue
            candidate = str(value).strip()
            if candidate:
                return candidate
    feature_id = feature.get("id")
    if feature_id is not None:
        candidate = str(feature_id).strip()
        if candidate:
            return candidate
    return fallback


def _extract_centroid(feature: Mapping[str, Any]) -> tuple[float, float] | None:
    properties = feature.get("properties") or {}
    if isinstance(properties, Mapping):
        centroid = properties.get("centroid")
        if isinstance(centroid, Mapping):
            candidate = _lon_lat_from_values(
                centroid.get("x", centroid.get("lon", centroid.get("lng", centroid.get("longitude")))),
                centroid.get("y", centroid.get("lat", centroid.get("latitude"))),
            )
            if candidate is not None:
                return candidate

        for lon_key, lat_key in (
            ("centroid_x", "centroid_y"),
            ("CENTROID_X", "CENTROID_Y"),
            ("longitude", "latitude"),
            ("lon", "lat"),
        ):
            candidate = _lon_lat_from_values(properties.get(lon_key), properties.get(lat_key))
            if candidate is not None:
                return candidate

    geometry = feature.get("geometry")
    if isinstance(geometry, Mapping):
        if geometry.get("type") == "Point":
            coordinates = geometry.get("coordinates")
            if isinstance(coordinates, Sequence) and len(coordinates) >= 2:
                candidate = _lon_lat_from_values(coordinates[0], coordinates[1])
                if candidate is not None:
                    return candidate
        try:
            from shapely.geometry import shape

            centroid = shape(geometry).centroid
            candidate = _lon_lat_from_values(centroid.x, centroid.y)
            if candidate is not None:
                return candidate
        except Exception:
            return None

    return None


def _lon_lat_from_values(lon_value: Any, lat_value: Any) -> tuple[float, float] | None:
    try:
        lon = float(lon_value)
        lat = float(lat_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(lon) or not math.isfinite(lat):
        return None
    if lon < -180.0 or lon > 180.0 or lat < -90.0 or lat > 90.0:
        return None
    return lon, lat


def _haversine_m(left_lon: float, left_lat: float, right_lon: float, right_lat: float) -> float:
    radius_m = 6_371_000.0
    lat1 = math.radians(left_lat)
    lat2 = math.radians(right_lat)
    delta_lat = math.radians(right_lat - left_lat)
    delta_lon = math.radians(right_lon - left_lon)
    a = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2.0) ** 2
    )
    return radius_m * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
