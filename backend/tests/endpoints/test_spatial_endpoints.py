"""
Endpoint tests for spatial generation and spatial optimization.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class FakeSpatialAgent:
    """
    Fake spatial generator.

    This keeps endpoint tests independent from GeoPandas and actual spatial
    generation internals.
    """

    def generate(self, parcels, generation_type, parameters):
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "generated-1",
                    "geometry": parcels[0]["geometry"],
                    "properties": {
                        "source_generation_type": generation_type,
                        "parameters": parameters,
                    },
                }
            ],
        }


class FakeSpatialOptimizer:
    """
    Fake optimizer for /spatial/optimize.

    The actual optimizer should be tested in unit tests.
    Endpoint tests only need predictable output shape.
    """

    def __init__(self, config, objective_functions):
        self.config = config
        self.objective_functions = objective_functions

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
                    "stage": "fake_optimizer_started",
                    "elapsed_seconds": 0.01,
                    "parcel_count": len(features),
                }
            )

        assignment = SimpleNamespace(
            parcel_id="parcel-1",
            use_code=0,
            use_label="residential",
        )

        plan = SimpleNamespace(
            rank=0,
            crowding_distance=1.0,
            objectives=[0.1, 0.2],
            assignments=[assignment],
        )

        return SimpleNamespace(
            objective_names=("zoning_violation_penalty", "environmental_risk_exposure"),
            plans=[plan],
        )


def test_spatial_optimize_returns_plan_payload(client, monkeypatch, sample_polygon_feature):
    """
    /spatial/optimize should format optimizer results into frontend-friendly JSON.
    """
    import main

    monkeypatch.setattr(main, "SpatialOptimizer", FakeSpatialOptimizer)

    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": [sample_polygon_feature],
            "target_mix": {"residential": 70, "green": 30},
            "num_output_plans": 1,
            "population_size": 10,
            "generations": 1,
            "include_adjacency": False,
            "debug": True,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["parcel_count"] == 1
    assert data["objective_names"] == [
        "zoning_violation_penalty",
        "environmental_risk_exposure",
    ]

    assert len(data["plans"]) == 1
    assert data["plans"][0]["assignments"] == [
        {
            "parcel_id": "parcel-1",
            "use_code": 0,
            "use_label": "residential",
        }
    ]

    # target_mix should be normalized.
    assert data["settings"]["target_mix"] == {
        "green": 0.3,
        "residential": 0.7,
    }

    # debug=True should include timeline stages.
    stages = {event["stage"] for event in data["debug_timeline"]}
    assert "request_received" in stages
    assert "fake_optimizer_started" in stages
    assert "request_completed" in stages


def test_spatial_optimize_allows_repairable_invalid_geometry(client, monkeypatch, sample_polygon_feature):
    """
    Some real parcel sources contain self-intersections. The request validator
    should not crash or reject repairable geometries before optimizer repair runs.
    """
    import main

    monkeypatch.setattr(main, "SpatialOptimizer", FakeSpatialOptimizer)

    invalid_feature = {
        **sample_polygon_feature,
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [0.0, 0.0],
                    [1.0, 1.0],
                    [1.0, 0.0],
                    [0.0, 1.0],
                    [0.0, 0.0],
                ]
            ],
        },
    }

    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": [invalid_feature],
            "target_mix": {"residential": 70, "green": 30},
            "num_output_plans": 1,
            "population_size": 10,
            "generations": 1,
            "include_adjacency": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["parcel_count"] == 1


def test_spatial_optimize_rejects_invalid_adjacency_predicate(client, sample_polygon_feature):
    """Only touches/intersects are allowed."""
    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": [sample_polygon_feature],
            "adjacency_predicate": "nearby",
            "population_size": 10,
            "generations": 1,
        },
    )

    assert response.status_code == 422


def test_spatial_optimize_rejects_empty_parcels(client):
    """Spatial optimization requires at least one parcel."""
    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": [],
            "population_size": 10,
            "generations": 1,
        },
    )

    assert response.status_code == 422


def test_spatial_optimize_interactive_mode_caps_settings(client, monkeypatch, sample_polygon_feature):
    """
    interactive_mode should reduce large optimizer settings for UI responsiveness.
    """
    import main

    monkeypatch.setattr(main, "SpatialOptimizer", FakeSpatialOptimizer)

    response = client.post(
        "/spatial/optimize",
        json={
            "parcels": [sample_polygon_feature],
            "population_size": 100,
            "generations": 100,
            "interactive_mode": True,
            "debug": True,
        },
    )

    assert response.status_code == 200

    data = response.json()

    # For <=20 parcels, current main.py caps to pop=24, gen=12.
    assert data["settings"]["population_size"] == 24
    assert data["settings"]["generations"] == 12
    assert "Interactive mode capped population/generations" in data["warnings"][0]


def test_spatial_optimize_rejects_invalid_spatial_neighbor_radius(
    sample_polygon_feature,
):
    """Spatial compatibility radius should be validated when sent by the frontend."""
    import main
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        main.SpatialOptimizeRequest(
            **{
            "parcels": [sample_polygon_feature],
            "population_size": 10,
            "generations": 1,
            "use_spatial_compatibility": True,
            "spatial_neighbor_radius_m": 6000,
            }
        )


