"""
Manual-flow backend regression test for GeoVision Feature 3:
Spatial Compatibility-Aware / Neighbour-Aware Plan Generation.

Place this file in:
    backend/tests/endpoints/test_spatial_compatibility_flow.py

Run:
    cd backend
    pytest -q tests/endpoints/test_spatial_compatibility_flow.py

What this verifies automatically:
- /spatial/optimize accepts use_spatial_compatibility fields.
- Nearby parcel pairs are built from selected parcel geometries.
- The optimizer receives an extra spatial compatibility objective.
- Response settings report spatial_neighbor_pairs > 0.
- Each generated plan includes spatial compatibility score, summary, and warnings.

What this does NOT verify:
- Browser UI toggle rendering.
- Plan Gallery visual card rendering.
Those are covered by the manual checklist file.
"""

from __future__ import annotations

from types import SimpleNamespace


class Feature3FakeSpatialOptimizer:
    """Small fake optimizer so the endpoint test is fast and deterministic."""

    def __init__(self, config, objective_functions):
        self.config = config
        self.objective_functions = tuple(objective_functions)

    def optimize_geojson_features(
        self,
        features,
        include_adjacency,
        adjacency_predicate,
        progress_callback=None,
        progress_every_generations=10,
    ):
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "feature3_fake_optimizer_started",
                    "parcel_count": len(features),
                }
            )

        # Deliberately create one industrial-residential nearby conflict so
        # spatial_compatibility_warnings should not be empty.
        assignments = [
            SimpleNamespace(parcel_id="parcel-a", use_code=2, use_label="industrial"),
            SimpleNamespace(parcel_id="parcel-b", use_code=0, use_label="residential"),
            SimpleNamespace(parcel_id="parcel-c", use_code=3, use_label="green"),
        ]

        objective_names = tuple(
            getattr(function, "__name__", f"objective_{index}")
            for index, function in enumerate(self.objective_functions)
        )

        plan = SimpleNamespace(
            rank=0,
            crowding_distance=1.0,
            objectives=[0.1 for _ in objective_names],
            assignments=assignments,
        )

        return SimpleNamespace(objective_names=objective_names, plans=[plan])


def _parcel(parcel_id: str, lon: float, lat: float, risk: float = 0.2) -> dict:
    """Create a tiny valid parcel polygon with centroid metadata."""
    delta = 0.00008
    return {
        "type": "Feature",
        "id": parcel_id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [lon - delta, lat - delta],
                    [lon + delta, lat - delta],
                    [lon + delta, lat + delta],
                    [lon - delta, lat + delta],
                    [lon - delta, lat - delta],
                ]
            ],
        },
        "properties": {
            "APN": parcel_id,
            "centroid": {"x": lon, "y": lat},
            "environmental_risk": risk,
            "ZONING_CODE": "RS-1-7",
            "residential": 0.7,
            "commercial": 0.4,
            "industrial": 0.2,
            "green": 0.6,
        },
    }


def test_feature3_optimize_response_contains_spatial_compatibility_payload(
    client,
    monkeypatch,
):
    """
    This is the automated backend version of the manual browser test:

    1. Select multiple nearby parcels.
    2. Enable spatial compatibility.
    3. Choose 250m.
    4. Generate plans.
    5. Check response has spatial compatibility fields.
    6. Check settings.spatial_neighbor_pairs > 0.
    """
    import main

    monkeypatch.setattr(main, "SpatialOptimizer", Feature3FakeSpatialOptimizer)

    # These coordinates are close enough that 250m should produce neighbour pairs.
    parcels = [
        _parcel("parcel-a", -117.00000, 32.00000, risk=0.2),
        _parcel("parcel-b", -117.00045, 32.00000, risk=0.2),
        _parcel("parcel-c", -117.00090, 32.00000, risk=0.8),
    ]

    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": parcels,
            "target_mix": {
                "residential": 34,
                "commercial": 0,
                "industrial": 33,
                "green": 33,
            },
            "num_output_plans": 1,
            "population_size": 10,
            "generations": 1,
            "include_adjacency": False,
            "debug": True,
            "use_spatial_compatibility": True,
            "spatial_neighbor_radius_m": 250,
            "spatial_compatibility_weight": 0.15,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["settings"]["use_spatial_compatibility"] is True
    assert data["settings"]["spatial_neighbor_radius_m"] == 250
    assert data["settings"]["spatial_compatibility_weight"] == 0.15

    # This is the key manual-test condition you wanted to confirm.
    assert data["settings"]["spatial_neighbor_pairs"] > 0

    assert "spatial_compatibility_penalty" in data["objective_names"]
    assert len(data["plans"]) == 1

    plan = data["plans"][0]
    assert "spatial_compatibility_score" in plan
    assert 0.0 <= plan["spatial_compatibility_score"] <= 1.0

    summary = plan["spatial_compatibility_summary"]
    assert summary["neighbor_pairs_evaluated"] > 0
    assert summary["industrial_residential_conflicts"] >= 1
    assert summary["conflict_pairs"] >= 1

    warnings = plan["spatial_compatibility_warnings"]
    assert any("industrial-residential" in warning for warning in warnings)

    stages = {event["stage"] for event in data["debug_timeline"]}
    assert "spatial_compatibility_neighbors_ready" in stages


def test_feature3_disabled_keeps_old_response_shape(client, monkeypatch):
    """When the toggle is off, spatial plan fields should not be forced onto plans."""
    import main

    monkeypatch.setattr(main, "SpatialOptimizer", Feature3FakeSpatialOptimizer)

    parcels = [
        _parcel("parcel-a", -117.00000, 32.00000),
        _parcel("parcel-b", -117.00045, 32.00000),
    ]

    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": parcels,
            "target_mix": {"residential": 50, "green": 50},
            "num_output_plans": 1,
            "population_size": 10,
            "generations": 1,
            "include_adjacency": False,
            "debug": True,
            "use_spatial_compatibility": False,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["settings"]["use_spatial_compatibility"] is False
    assert data["settings"]["spatial_neighbor_pairs"] == 0
    assert "spatial_compatibility_penalty" not in data["objective_names"]

    plan = data["plans"][0]
    assert "spatial_compatibility_score" not in plan
    assert "spatial_compatibility_summary" not in plan
    assert "spatial_compatibility_warnings" not in plan
