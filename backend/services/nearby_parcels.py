"""Nearby parcel lookup using Redis GEO with a memory fallback."""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from shapely.errors import ShapelyError
from shapely.geometry import shape as shapely_shape

from services.redis_store import RedisStore, get_redis_store

logger = logging.getLogger(__name__)

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

REDIS_GEO_KEY = "parcels:geo"

RISK_FIELD_KEYS = (
    "xgb_risk_score",
    "rule_risk_score",
    "environmental_risk",
    "risk_score",
    "XGB_RISK_SCORE",
    "RULE_RISK_SCORE",
    "ENVIRONMENTAL_RISK",
    "RISK_SCORE",
)

ZONING_FIELD_KEYS = (
    "zoning",
    "ZONING",
    "zoning_code",
    "ZONE",
    "GP_LAND_USE",
    "land_use",
)

LAND_USE_FIELD_KEYS = (
    "assigned_use",
    "land_use",
    "existing_land_use",
    "GP_LAND_USE",
    "best_use",
)

HAZARD_FIELD_ALIASES = {
    "flood": ("has_flood", "hasFlood", "HAS_FLOOD", "flood", "FLOOD"),
    "fault": ("has_fault", "hasFault", "HAS_FAULT", "fault", "FAULT"),
    "liquefaction": (
        "has_liquefaction",
        "hasLiquefaction",
        "HAS_LIQUEFACTION",
        "liquefaction",
        "LIQUEFACTION",
    ),
    "steep_slope": ("is_steep", "isSteep", "IS_STEEP", "steep_slope", "STEEP_SLOPE"),
    "fire": ("is_fire_zone", "isFireZone", "IS_FIRE_ZONE", "fire_zone", "FIRE_ZONE"),
    "esa": ("in_esa", "inEsa", "IN_ESA", "esa", "ESA"),
    "mscp": ("in_mscp", "inMscp", "IN_MSCP", "mscp", "MSCP"),
}


class NearbyParcelLookupError(RuntimeError):
    """Base error for nearby parcel lookup failures."""


class NearbyParcelDataError(NearbyParcelLookupError):
    """Raised when the parcel dataset cannot be loaded."""


class NearbyParcelNotFoundError(NearbyParcelLookupError):
    """Raised when a parcel ID does not exist in the dataset."""


@dataclass(frozen=True)
class _ParcelCentroid:
    parcel_id: str
    longitude: float
    latitude: float
    properties: Dict[str, Any]


def _first_non_empty(properties: Dict[str, Any], keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = properties.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _is_truthy_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "t", "on"}


def _normalize_risk_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(numeric) or math.isinf(numeric):
        return None
    if numeric > 1.0 and numeric <= 100.0:
        numeric = numeric / 100.0
    elif numeric > 100.0:
        numeric = 1.0

    return max(0.0, min(1.0, numeric))


def _extract_risk_value(properties: Dict[str, Any]) -> Optional[float]:
    for key in RISK_FIELD_KEYS:
        normalized = _normalize_risk_value(properties.get(key))
        if normalized is not None:
            return normalized
    return None


def _normalize_land_use_label(raw_value: Any) -> str:
    if raw_value is None:
        return "unknown"

    text = str(raw_value).strip().lower()
    if not text:
        return "unknown"

    if any(token in text for token in ("residential", "res", "housing", "dwelling", "single-family", "single family")):
        return "residential"
    if any(token in text for token in ("commercial", "retail", "office", "service", "mixed use", "mixed-use", "mixeduse")):
        return "commercial"
    if any(token in text for token in ("industrial", "manufacturing", "warehouse", "distribution", "heavy")):
        return "industrial"
    if any(token in text for token in ("green", "open space", "openspace", "park", "recreation", "agric", "conservation")):
        return "green"
    return "unknown"


def _build_planning_insight(summary: Dict[str, Any]) -> str:
    average_risk = float(summary.get("average_risk") or 0.0)
    high_risk_count = int(summary.get("high_risk_count") or 0)
    land_use_counts = summary.get("land_use_counts") or {}
    zoning_counts = summary.get("zoning_counts") or {}

    residential = int(land_use_counts.get("residential") or 0)
    commercial = int(land_use_counts.get("commercial") or 0)
    industrial = int(land_use_counts.get("industrial") or 0)
    green = int(land_use_counts.get("green") or 0)
    total = residential + commercial + industrial + green + int(land_use_counts.get("unknown") or 0)

    if total > 0 and (average_risk >= 0.6 or high_risk_count >= max(3, math.ceil(total * 0.3))):
        return (
            "Nearby parcels show elevated environmental risk. "
            "Green/open-space allocation or additional environmental review may be appropriate."
        )

    if industrial >= 2 and residential >= 2:
        return (
            "The nearby area contains both industrial and residential activity, "
            "so buffering and compatibility review are recommended."
        )

    if commercial > 0 and commercial >= max(residential, industrial, green):
        return (
            "This parcel is close to an existing commercial cluster, "
            "which may support service-oriented or mixed-use planning."
        )

    if residential > 0 and residential >= max(commercial, industrial, green) and average_risk <= 0.35:
        return (
            "This parcel is located in a mostly residential, low-risk area. "
            "Residential growth may fit the surrounding pattern, while commercial use should be reviewed for compatibility."
        )

    if green > 0 and green >= max(residential, commercial, industrial):
        return (
            "This parcel is surrounded by more open-space and environmental activity, "
            "so conservation-sensitive planning may be appropriate."
        )

    dominant_zoning = str(summary.get("dominant_zoning") or "mixed")
    if dominant_zoning.lower() == "unknown" and zoning_counts:
        dominant_zoning = max(zoning_counts.items(), key=lambda item: item[1])[0]

    return (
        f"This parcel sits in a mixed-use area dominated by {dominant_zoning.lower()}. "
        "Compatibility review is recommended."
    )


def _build_nearby_planning_summary(
    parcel_properties: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    zoning_counts: Counter[str] = Counter()
    land_use_counts: Dict[str, int] = {
        "residential": 0,
        "commercial": 0,
        "industrial": 0,
        "green": 0,
        "unknown": 0,
    }
    hazard_counts: Dict[str, int] = {key: 0 for key in HAZARD_FIELD_ALIASES}

    risk_values: list[float] = []
    high_risk_count = 0

    for properties in parcel_properties:
        risk_value = _extract_risk_value(properties)
        if risk_value is not None:
            risk_values.append(risk_value)
            if risk_value >= 0.6:
                high_risk_count += 1

        zoning = _first_non_empty(properties, ZONING_FIELD_KEYS)
        if zoning:
            zoning_counts[zoning] += 1

        land_use = _first_non_empty(properties, LAND_USE_FIELD_KEYS)
        category = _normalize_land_use_label(land_use)
        land_use_counts[category] = land_use_counts.get(category, 0) + 1

        for hazard_name, aliases in HAZARD_FIELD_ALIASES.items():
            if any(_is_truthy_value(properties.get(alias)) for alias in aliases):
                hazard_counts[hazard_name] += 1

    average_risk = round(sum(risk_values) / len(risk_values), 3) if risk_values else 0.0
    dominant_zoning = zoning_counts.most_common(1)[0][0] if zoning_counts else "Unknown"
    zoning_counts_dict = dict(zoning_counts)

    summary = {
        "average_risk": average_risk,
        "high_risk_count": high_risk_count,
        "dominant_zoning": dominant_zoning,
        "zoning_counts": zoning_counts_dict,
        "land_use_counts": land_use_counts,
        "hazard_counts": hazard_counts,
    }
    summary["insight"] = _build_planning_insight(summary)
    return summary


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_data_candidates() -> list[Path]:
    backend_dir = _backend_dir()
    repo_root = backend_dir.parent
    return [
        backend_dir / "data" / "parcels_env_risk_clipped.geojson",
        repo_root / "frontend" / "public" / "parcels_env_risk_clipped.geojson",
    ]


def _parcel_id_from_feature(feature: Dict[str, Any]) -> str:
    properties = feature.get("properties") or {}
    for key in PARCEL_ID_KEYS:
        value = properties.get(key)
        if value is None:
            continue
        parcel_id = str(value).strip()
        if parcel_id:
            return parcel_id

    fallback = feature.get("id")
    if fallback is not None:
        parcel_id = str(fallback).strip()
        if parcel_id:
            return parcel_id
    return ""


def _extract_centroid(feature: Dict[str, Any]) -> tuple[float, float]:
    geometry = feature.get("geometry")
    if not geometry:
        raise ValueError("missing geometry")

    geom = shapely_shape(geometry)
    centroid = geom.centroid
    longitude = float(centroid.x)
    latitude = float(centroid.y)
    if not (math.isfinite(longitude) and math.isfinite(latitude)):
        raise ValueError("non-finite centroid coordinates")
    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        raise ValueError("centroid outside valid longitude/latitude range")
    return longitude, latitude


def _haversine_distance_m(
    lon_a: float,
    lat_a: float,
    lon_b: float,
    lat_b: float,
) -> float:
    radius_earth_m = 6_371_000.0
    phi1 = math.radians(lat_a)
    phi2 = math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lon_b - lon_a)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * radius_earth_m * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class NearbyParcelsService:
    """Load parcel centroids and resolve nearby parcels by radius."""

    def __init__(
        self,
        data_path: Optional[Path] = None,
        redis_store: Optional[RedisStore] = None,
    ) -> None:
        self._configured_data_path = Path(data_path) if data_path is not None else None
        self._redis_store = redis_store
        self._loaded = False
        self._load_error: Optional[str] = None
        self._geo_index_ready = False
        self._redis_checked = redis_store is not None
        self._centroids_by_id: Dict[str, _ParcelCentroid] = {}

    def _resolve_data_path(self) -> Path:
        if self._configured_data_path is not None:
            return self._configured_data_path

        for candidate in _default_data_candidates():
            if candidate.exists():
                return candidate

        candidates = ", ".join(str(path) for path in _default_data_candidates())
        raise NearbyParcelDataError(
            "Nearby parcel dataset not found. Expected parcels_env_risk_clipped.geojson "
            f"in one of: {candidates}"
        )

    def _load_dataset(self) -> None:
        if self._loaded:
            return

        data_path = self._resolve_data_path()
        if not data_path.exists():
            self._load_error = (
                f"Nearby parcel dataset not found at {data_path}. "
                "Expected parcels_env_risk_clipped.geojson."
            )
            self._loaded = True
            raise NearbyParcelDataError(self._load_error)

        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._load_error = f"Failed to read nearby parcel dataset at {data_path}: {exc}"
            self._loaded = True
            raise NearbyParcelDataError(self._load_error) from exc

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            self._load_error = f"Nearby parcel dataset at {data_path} is not a GeoJSON FeatureCollection."
            self._loaded = True
            raise NearbyParcelDataError(self._load_error)

        centroids: Dict[str, _ParcelCentroid] = {}
        duplicates = 0
        invalid = 0

        for raw_feature in features:
            if not isinstance(raw_feature, dict):
                invalid += 1
                continue

            parcel_id = _parcel_id_from_feature(raw_feature)
            if not parcel_id:
                invalid += 1
                continue
            if parcel_id in centroids:
                duplicates += 1
                continue

            try:
                longitude, latitude = _extract_centroid(raw_feature)
            except (ShapelyError, ValueError, TypeError) as exc:
                logger.warning("Skipping parcel %s with invalid geometry: %s", parcel_id, exc)
                invalid += 1
                continue

            centroids[parcel_id] = _ParcelCentroid(
                parcel_id=parcel_id,
                longitude=longitude,
                latitude=latitude,
                properties=dict(raw_feature.get("properties") or {}),
            )

        if not centroids:
            self._load_error = f"No usable parcel geometries were found in {data_path}."
            self._loaded = True
            raise NearbyParcelDataError(self._load_error)

        self._centroids_by_id = centroids
        self._loaded = True
        self._load_error = None
        logger.info(
            "Loaded %d parcel centroids from %s (invalid=%d duplicate=%d)",
            len(centroids),
            data_path,
            invalid,
            duplicates,
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_dataset()

    def _ensure_redis_index(self) -> bool:
        if self._geo_index_ready:
            return True

        if self._redis_store is None and not self._redis_checked:
            self._redis_store = get_redis_store()
            self._redis_checked = True
        if self._redis_store is None:
            return False

        try:
            for parcel in self._centroids_by_id.values():
                self._redis_store.geoadd(
                    REDIS_GEO_KEY,
                    parcel.longitude,
                    parcel.latitude,
                    parcel.parcel_id,
                )
            self._geo_index_ready = True
            return True
        except Exception as exc:
            logger.warning("Redis GEO index build failed; using memory fallback: %s", exc)
            self._geo_index_ready = False
            return False

    def nearby_parcels(self, parcel_id: str, radius_m: float, limit: int = 150) -> Dict[str, Any]:
        self._ensure_loaded()
        if not self._centroids_by_id:
            if self._load_error:
                raise NearbyParcelDataError(self._load_error)
            raise NearbyParcelDataError("Nearby parcel dataset is empty.")

        normalized_parcel_id = str(parcel_id or "").strip()
        if not normalized_parcel_id:
            raise NearbyParcelLookupError("parcel_id is required")

        center = self._centroids_by_id.get(normalized_parcel_id)
        if center is None:
            raise NearbyParcelNotFoundError(
                f"Parcel '{normalized_parcel_id}' was not found in the nearby parcel dataset."
            )

        use_redis = self._ensure_redis_index()
        source = "redis_geo" if use_redis else "memory_fallback"

        if use_redis and self._redis_store is not None:
            try:
                nearby = self._redis_store.geosearch_by_member(
                    REDIS_GEO_KEY,
                    normalized_parcel_id,
                    radius_m=radius_m,
                    limit=limit,
                    withdist=True,
                )
                normalized_results = []
                for member, distance_m in nearby:
                    candidate = self._centroids_by_id.get(str(member))
                    if candidate is None:
                        continue
                    normalized_results.append(
                        {
                            "parcel_id": candidate.parcel_id,
                            "distance_m": round(float(distance_m or 0.0), 3),
                        }
                    )
                if normalized_results:
                    summary = self.build_planning_summary(
                        [item["parcel_id"] for item in normalized_results]
                    )
                    return self._build_response(
                        normalized_parcel_id,
                        radius_m,
                        normalized_results,
                        summary,
                        source,
                    )
            except Exception as exc:
                logger.warning("Redis GEO search failed; falling back to memory lookup: %s", exc)
                source = "memory_fallback"

        results = []
        for candidate in self._centroids_by_id.values():
            distance_m = _haversine_distance_m(
                center.longitude,
                center.latitude,
                candidate.longitude,
                candidate.latitude,
            )
            if distance_m <= float(radius_m):
                results.append(
                    {
                        "parcel_id": candidate.parcel_id,
                        "distance_m": round(distance_m, 3),
                    }
                )

        results.sort(key=lambda item: (item["distance_m"], item["parcel_id"]))
        limited_results = results[: int(limit)]
        summary = self.build_planning_summary([item["parcel_id"] for item in limited_results])
        return self._build_response(normalized_parcel_id, radius_m, limited_results, summary, source)

    def build_planning_summary(self, parcel_ids: Sequence[str]) -> Dict[str, Any]:
        self._ensure_loaded()

        parcel_properties = []
        for parcel_id in parcel_ids:
            record = self._centroids_by_id.get(str(parcel_id))
            if record is None:
                continue
            parcel_properties.append(record.properties)

        if not parcel_properties:
            return {
                "average_risk": 0.0,
                "high_risk_count": 0,
                "dominant_zoning": "Unknown",
                "zoning_counts": {},
                "land_use_counts": {
                    "residential": 0,
                    "commercial": 0,
                    "industrial": 0,
                    "green": 0,
                    "unknown": 0,
                },
                "hazard_counts": {key: 0 for key in HAZARD_FIELD_ALIASES},
                "insight": "Select nearby parcels to view planning context.",
            }

        return _build_nearby_planning_summary(parcel_properties)

    @staticmethod
    def _build_response(
        center_parcel_id: str,
        radius_m: float,
        results: list[Dict[str, Any]],
        summary: Dict[str, Any],
        source: str,
    ) -> Dict[str, Any]:
        parcel_ids = [str(item["parcel_id"]) for item in results]
        return {
            "center_parcel_id": center_parcel_id,
            "radius_m": float(radius_m),
            "count": len(results),
            "parcel_ids": parcel_ids,
            "results": results,
            "summary": summary,
            "source": source,
        }


_nearby_parcels_service: Optional[NearbyParcelsService] = None


def get_nearby_parcels_service() -> NearbyParcelsService:
    global _nearby_parcels_service
    if _nearby_parcels_service is None:
        _nearby_parcels_service = NearbyParcelsService()
    return _nearby_parcels_service
