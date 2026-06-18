"""
Endpoint tests for saved maps routes.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class FakeSavedMapService:
    """In-memory fake service for saved maps endpoint tests."""

    def __init__(self):
        self._next_id = 1
        self._rows: dict[int, dict] = {}

    def create_saved_map(self, user_id: int, payload):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        row = {
            "id": self._next_id,
            "user_id": user_id,
            "name": payload.name,
            "description": payload.description,
            "parcel_count": len(payload.input_parcels) if isinstance(payload.input_parcels, list) else 0,
            "plan_count": len(payload.optimization_result.get("plans", []))
            if isinstance(payload.optimization_result, dict)
            else 0,
            "selected_plan_rank": payload.selected_plan_rank,
            "input_parcels": payload.input_parcels,
            "optimization_result": payload.optimization_result,
            "created_at": now,
            "updated_at": now,
        }
        self._rows[self._next_id] = row
        self._next_id += 1
        return row

    def list_saved_maps(self, user_id: int, limit: int, offset: int):
        rows = [row for row in self._rows.values() if int(row["user_id"]) == int(user_id)]
        rows.sort(key=lambda item: item["id"], reverse=True)
        items = rows[offset : offset + limit]
        metadata = []
        for row in items:
            metadata.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "parcel_count": row["parcel_count"],
                    "plan_count": row["plan_count"],
                    "selected_plan_rank": row["selected_plan_rank"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return {"items": metadata, "total": len(rows), "limit": limit, "offset": offset}

    def get_saved_map(self, user_id: int, saved_map_id: int):
        row = self._rows.get(int(saved_map_id))
        if not row or int(row["user_id"]) != int(user_id):
            return None
        return row

    def update_saved_map(self, user_id: int, saved_map_id: int, payload):
        row = self.get_saved_map(user_id=user_id, saved_map_id=saved_map_id)
        if not row:
            return None
        update = payload.model_dump(exclude_unset=True)
        row.update(update)
        row["updated_at"] = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
        return row

    def delete_saved_map(self, user_id: int, saved_map_id: int):
        row = self.get_saved_map(user_id=user_id, saved_map_id=saved_map_id)
        if not row:
            return False
        self._rows.pop(int(saved_map_id), None)
        return True


@pytest.fixture
def fake_saved_maps_dependencies(client, monkeypatch):
    import main
    import routers.saved_maps as saved_maps_router
    import routers.auth as auth_router
    import services.saved_map_service as saved_map_service_module
    from schemas.auth import UserResponse

    fake_user = UserResponse(
        id=7,
        email="planner@example.com",
        username="planner",
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    )
    fake_service = FakeSavedMapService()

    main.app.dependency_overrides[saved_maps_router.get_current_user] = lambda: fake_user
    main.app.dependency_overrides[auth_router.get_current_user] = lambda: fake_user
    main.app.dependency_overrides[saved_map_service_module.get_saved_map_service] = (
        lambda: fake_service
    )
    return fake_service


def _sample_create_payload():
    return {
        "name": "Downtown Green Priority Scenario",
        "description": "Generated with 30% green target.",
        "input_parcels": [
            {
                "type": "Feature",
                "id": "parcel-1",
                "geometry": {"type": "Polygon", "coordinates": []},
                "properties": {"APN": "parcel-1"},
            }
        ],
        "optimization_result": {
            "parcel_count": 1,
            "objective_names": ["zoning_violation_penalty", "environmental_risk_exposure"],
            "plans": [
                {
                    "rank": 0,
                    "objectives": [0.1, 0.2],
                    "assignments": [
                        {
                            "parcel_id": "parcel-1",
                            "use_code": 0,
                            "use_label": "residential",
                        }
                    ],
                }
            ],
            "settings": {"target_mix": {"residential": 0.7, "green": 0.3}},
        },
        "selected_plan_rank": 0,
    }


def test_saved_map_returns_404_when_missing(client, fake_saved_maps_dependencies):
    response = client.get("/saved-maps/99999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
