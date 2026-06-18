"""
Endpoint tests for orchestrator job routes.
"""

from __future__ import annotations

import pytest


class FakeOrchestratorService:
    """Fake async orchestrator service used instead of real background jobs."""

    def __init__(self, completed_job):
        self.completed_job = completed_job
        self.created_with = None

    async def create_job(self, parcel_ids, enable_spatial):
        self.created_with = {
            "parcel_ids": parcel_ids,
            "enable_spatial": enable_spatial,
        }
        return "job-123"

    async def get_job_status(self, job_id):
        if job_id == "missing-job":
            return None
        return self.completed_job

    async def get_job_result(self, job_id):
        if job_id == "missing-job":
            raise ValueError("Job missing-job not found")

        if job_id == "running-job":
            raise ValueError("Job running-job is not completed yet")

        return {
            "merged_geojson": {
                "type": "FeatureCollection",
                "features": [],
            }
        }


@pytest.fixture
def fake_orchestrator(monkeypatch, fake_completed_job):
    """Patch router-level service factory."""
    import routers.orchestrator as orchestrator_router

    service = FakeOrchestratorService(fake_completed_job)
    monkeypatch.setattr(orchestrator_router, "get_orchestrator_service", lambda: service)
    return service


def test_create_orchestration_plan_returns_job_id(client, fake_orchestrator):
    """Creating orchestration plan should return a job ID."""
    response = client.post(
        "/orchestrator/plan",
        json={
            "parcel_ids": ["p1", "p2"],
            "enable_spatial": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-123", "status": "created"}
    assert fake_orchestrator.created_with == {
        "parcel_ids": ["p1", "p2"],
        "enable_spatial": True,
    }


def test_create_orchestration_plan_rejects_empty_parcel_ids(client, fake_orchestrator):
    """At least one parcel ID is required."""
    response = client.post(
        "/orchestrator/plan",
        json={
            "parcel_ids": [],
            "enable_spatial": True,
        },
    )

    assert response.status_code == 422


def test_get_job_status_returns_progress_and_steps(client, fake_orchestrator):
    """Status endpoint should return progress and step statuses."""
    response = client.get("/orchestrator/status/job-123")

    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == "job-123"
    assert data["status"] == "completed"
    assert data["progress"] == 100
    assert data["steps"]["environment"] == "completed"
    assert data["steps"]["zoning"] == "completed"


def test_get_job_status_returns_404_for_missing_job(client, fake_orchestrator):
    """Unknown job should return 404."""
    response = client.get("/orchestrator/status/missing-job")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_job_result_returns_completed_result(client, fake_orchestrator):
    """Completed job should return final result."""
    response = client.get("/orchestrator/result/job-123")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["merged_geojson"]["type"] == "FeatureCollection"


def test_get_job_result_returns_400_when_job_not_completed(client, fake_orchestrator):
    """Existing but unfinished job should return 400."""
    response = client.get("/orchestrator/result/running-job")

    assert response.status_code == 400
    assert "not completed" in response.json()["detail"]


def test_get_job_result_returns_404_for_missing_job(client, fake_orchestrator):
    """Missing job result should return 404."""
    response = client.get("/orchestrator/result/missing-job")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]