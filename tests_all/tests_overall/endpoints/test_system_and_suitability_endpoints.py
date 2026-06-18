"""
Endpoint tests for health and suitability prediction.
"""

from __future__ import annotations

import pandas as pd


class FakeSuitabilityAgent:
    """
    Fake environmental/suitability model.

    We do this because endpoint tests should not test the real model.
    The real model should be tested in unit tests.
    """

    def predict(self, ordered_df):
        return pd.DataFrame(
            {
                "parcel_id": ordered_df["parcel_id"].tolist(),
                "residential": [0.75 for _ in range(len(ordered_df))],
                "commercial": [0.45 for _ in range(len(ordered_df))],
                "industrial": [0.20 for _ in range(len(ordered_df))],
                "green": [0.60 for _ in range(len(ordered_df))],
                "environmental_risk": [0.25 for _ in range(len(ordered_df))],
            }
        )


def test_health_endpoint_returns_ok(client):
    """The /api/health endpoint should return a stable OK response."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_legacy_alias_returns_ok(client):
    """The legacy /health alias should also work."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_suitability_returns_geojson_with_scores(client, monkeypatch, sample_polygon_feature):
    """
    /predict_suitability should return GeoJSON with suitability scores merged
    into the feature properties.
    """
    import main

    monkeypatch.setattr(main, "get_suitability_agent", lambda: FakeSuitabilityAgent())

    response = client.post(
        "/api/predict_suitability",
        json={"parcels": [sample_polygon_feature]},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1

    feature = data["features"][0]
    props = feature["properties"]

    assert feature["id"] == "parcel-1"
    assert feature["geometry"] == sample_polygon_feature["geometry"]

    assert props["residential"] == 0.75
    assert props["commercial"] == 0.45
    assert props["industrial"] == 0.20
    assert props["green"] == 0.60
    assert props["environmental_risk"] == 0.25


def test_predict_suitability_rejects_empty_parcel_list(client):
    """No parcels should return a clear 400 error."""
    response = client.post("/api/predict_suitability", json={"parcels": []})

    assert response.status_code == 400
    assert response.json()["detail"] == "No parcels provided"


def test_predict_suitability_rejects_missing_parcels_field(client):
    """The request body must contain a parcels field."""
    response = client.post("/api/predict_suitability", json={})

    assert response.status_code == 422
    assert "detail" in response.json()
    