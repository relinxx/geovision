from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.nearby_parcels import (
    NearbyParcelLookupError,
    NearbyParcelsService,
    _build_planning_insight,
    _normalize_risk_value,
)


class FakeRedisStore:
    def __init__(self):
        self.geoadded = []
        self.search_calls = []

    def geoadd(self, key, longitude, latitude, member):
        self.geoadded.append((key, longitude, latitude, member))

    def geosearch_by_member(self, key, member, radius_m, limit=None, withdist=True):
        self.search_calls.append((key, member, radius_m, limit, withdist))
        return [
            (member, 0.0),
            ("parcel-b", 145.2),
        ]


def _write_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "parcel-a",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-117.0000, 32.8000],
                            [-117.0000, 32.8010],
                            [-116.9990, 32.8010],
                            [-116.9990, 32.8000],
                            [-117.0000, 32.8000],
                        ]
                    ],
                },
                "properties": {
                    "APN": "parcel-a",
                    "name": "A",
                    "zoning": "RS-1-7",
                    "land_use": "residential",
                    "xgb_risk_score": 8,
                    "has_flood": True,
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "parcel-b",
                    "name": "B",
                    "zoning": "RS-1-7",
                    "land_use": "residential",
                    "rule_risk_score": 12,
                    "in_mscp": True,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-117.0010, 32.8000],
                            [-117.0010, 32.8010],
                            [-117.0000, 32.8010],
                            [-117.0000, 32.8000],
                            [-117.0010, 32.8000],
                        ]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "id": "parcel-c",
                    "name": "C",
                    "zoning": "Commercial",
                    "land_use": "commercial",
                    "environmental_risk": 70,
                    "has_fault": True,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-117.0200, 32.8200],
                            [-117.0200, 32.8210],
                            [-117.0190, 32.8210],
                            [-117.0190, 32.8200],
                            [-117.0200, 32.8200],
                        ]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "id": "parcel-d",
                    "name": "D",
                    "zoning": "RS-1-7",
                    "land_use": "green",
                    "risk_score": 0.3,
                    "is_steep": True,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-117.0030, 32.7990],
                            [-117.0030, 32.8000],
                            [-117.0020, 32.8000],
                            [-117.0020, 32.7990],
                            [-117.0030, 32.7990],
                        ]
                    ],
                },
            },
        ],
    }
    path.write_text(json.dumps(payload))


def test_normalize_risk_value_handles_percentages_and_clamps():
    assert _normalize_risk_value(None) is None
    assert _normalize_risk_value(0.42) == pytest.approx(0.42)
    assert _normalize_risk_value(75) == pytest.approx(0.75)
    assert _normalize_risk_value(120) == pytest.approx(1.0)
    assert _normalize_risk_value(-5) == pytest.approx(0.0)


def test_build_planning_insight_prefers_residential_low_risk_language():
    summary = {
        "average_risk": 0.23,
        "high_risk_count": 1,
        "land_use_counts": {"residential": 28, "commercial": 6, "industrial": 0, "green": 8, "unknown": 0},
        "zoning_counts": {"RS-1-7": 28, "Commercial": 6},
        "dominant_zoning": "RS-1-7",
    }

    insight = _build_planning_insight(summary)

    assert insight.startswith("This parcel is located in a mostly residential, low-risk area.")


def test_build_planning_insight_flags_elevated_risk():
    summary = {
        "average_risk": 0.71,
        "high_risk_count": 9,
        "land_use_counts": {"residential": 4, "commercial": 2, "industrial": 0, "green": 0, "unknown": 0},
        "zoning_counts": {"RS-1-7": 4, "Commercial": 2},
        "dominant_zoning": "RS-1-7",
    }

    insight = _build_planning_insight(summary)

    assert insight == (
        "Nearby parcels show elevated environmental risk. "
        "Green/open-space allocation or additional environmental review may be appropriate."
    )


def test_nearby_service_uses_memory_fallback_when_redis_missing(tmp_path):
    geojson_path = tmp_path / "parcels_env_risk_clipped.geojson"
    _write_geojson(geojson_path)

    service = NearbyParcelsService(data_path=geojson_path, redis_store=None)
    response = service.nearby_parcels("parcel-a", radius_m=250, limit=10)

    assert response["center_parcel_id"] == "parcel-a"
    assert response["radius_m"] == 250
    assert response["count"] == 2
    assert response["source"] == "memory_fallback"
    assert response["parcel_ids"] == ["parcel-a", "parcel-b"]
    assert response["results"][0]["parcel_id"] == "parcel-a"
    assert response["results"][0]["distance_m"] == 0.0
    assert response["summary"]["dominant_zoning"] == "RS-1-7"
    assert response["summary"]["land_use_counts"]["residential"] == 2
    assert response["summary"]["hazard_counts"]["flood"] == 1
    assert response["summary"]["hazard_counts"]["mscp"] == 1
    assert response["summary"]["high_risk_count"] == 0
    assert "mostly residential" in response["summary"]["insight"]


def test_nearby_service_summary_uses_sample_features(tmp_path):
    geojson_path = tmp_path / "parcels_env_risk_clipped.geojson"
    _write_geojson(geojson_path)

    service = NearbyParcelsService(data_path=geojson_path, redis_store=None)
    summary = service.build_planning_summary(["parcel-a", "parcel-b", "parcel-c", "parcel-d"])

    assert summary["average_risk"] == pytest.approx(0.3)
    assert summary["high_risk_count"] == 1
    assert summary["dominant_zoning"] == "RS-1-7"
    assert summary["zoning_counts"]["RS-1-7"] == 3
    assert summary["land_use_counts"]["residential"] == 2
    assert summary["land_use_counts"]["commercial"] == 1
    assert summary["land_use_counts"]["green"] == 1
    assert summary["hazard_counts"]["flood"] == 1
    assert summary["hazard_counts"]["fault"] == 1
    assert summary["hazard_counts"]["liquefaction"] == 0
    assert summary["hazard_counts"]["steep_slope"] == 1
    assert summary["hazard_counts"]["mscp"] == 1


def test_nearby_service_uses_redis_geo_when_available(tmp_path):
    geojson_path = tmp_path / "parcels_env_risk_clipped.geojson"
    _write_geojson(geojson_path)
    fake_redis = FakeRedisStore()

    service = NearbyParcelsService(data_path=geojson_path, redis_store=fake_redis)
    response = service.nearby_parcels("parcel-a", radius_m=250, limit=10)

    assert response["source"] == "redis_geo"
    assert fake_redis.geoadded
    assert fake_redis.search_calls == [("parcels:geo", "parcel-a", 250, 10, True)]


def test_nearby_service_raises_clear_error_when_geojson_is_missing(tmp_path):
    missing_path = tmp_path / "missing.geojson"
    service = NearbyParcelsService(data_path=missing_path, redis_store=None)

    with pytest.raises(NearbyParcelLookupError) as excinfo:
        service.nearby_parcels("parcel-a", radius_m=250, limit=10)

    assert "parcels_env_risk_clipped.geojson" in str(excinfo.value)
