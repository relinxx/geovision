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
    """The main health endpoint should return a stable OK response."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_health_alias_returns_ok(client):
    """The /api/health alias should also work."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


