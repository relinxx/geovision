from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError


class FakeNearbyParcelsService:
    def nearby_parcels(self, parcel_id: str, radius_m: float, limit: int):
        if parcel_id == "missing":
            raise KeyError(parcel_id)
        return {
            "center_parcel_id": parcel_id,
            "radius_m": radius_m,
            "count": 2,
            "parcel_ids": [parcel_id, "parcel-b"],
            "results": [
                {"parcel_id": parcel_id, "distance_m": 0.0},
                {"parcel_id": "parcel-b", "distance_m": 145.2},
            ],
            "summary": {
                "average_risk": 0.23,
                "high_risk_count": 1,
                "dominant_zoning": "RS-1-7",
                "zoning_counts": {"RS-1-7": 2},
                "land_use_counts": {
                    "residential": 2,
                    "commercial": 0,
                    "industrial": 0,
                    "green": 0,
                    "unknown": 0,
                },
                "hazard_counts": {
                    "flood": 0,
                    "fault": 0,
                    "liquefaction": 0,
                    "steep_slope": 0,
                    "fire": 0,
                    "esa": 0,
                    "mscp": 0,
                },
                "insight": "This parcel is located in a mostly residential, low-risk area.",
            },
            "source": "memory_fallback",
        }


def test_nearby_parcels_request_rejects_invalid_radius():
    import main

    try:
        main.NearbyParcelsRequest(parcel_id="parcel-a", radius_m=0, limit=150)
        assert False, "Expected validation error"
    except ValidationError as exc:
        assert "radius_m" in str(exc)


def test_nearby_parcels_routes_registered():
    import main

    route_paths = {route.path for route in main.app.routes}
    assert "/spatial/nearby-parcels" in route_paths
    assert "/api/spatial/nearby-parcels" in route_paths


def test_nearby_parcels_returns_expected_shape(monkeypatch):
    import main

    monkeypatch.setattr(main, "get_nearby_parcels_service", lambda: FakeNearbyParcelsService())
    monkeypatch.setattr(main, "_nearby_parcels_service", None)
    body = main.NearbyParcelsRequest(parcel_id="parcel-a", radius_m=250, limit=150)

    response = main.spatial_nearby_parcels(body)

    assert response["center_parcel_id"] == "parcel-a"
    assert response["radius_m"] == 250.0
    assert response["count"] == 2
    assert response["parcel_ids"] == ["parcel-a", "parcel-b"]
    assert response["results"][0]["distance_m"] == 0.0
    assert response["summary"]["dominant_zoning"] == "RS-1-7"
    assert response["source"] == "memory_fallback"


def test_nearby_parcels_unknown_parcel_returns_404(monkeypatch):
    import main

    monkeypatch.setattr(main, "get_nearby_parcels_service", lambda: FakeNearbyParcelsService())
    monkeypatch.setattr(main, "_nearby_parcels_service", None)
    body = main.NearbyParcelsRequest(parcel_id="missing", radius_m=250, limit=150)

    try:
        main.spatial_nearby_parcels(body)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "missing" in str(exc.detail)
