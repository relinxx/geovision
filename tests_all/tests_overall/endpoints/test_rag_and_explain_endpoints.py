"""
Endpoint tests for zoning RAG, assignment explanation, and risk counterfactual.
"""

from __future__ import annotations

from agent.zoning_agent.rag_service import RetrievedChunk


class FakeRagService:
    """
    Fake RAG service so endpoint tests do not call ChromaDB/OpenAI.
    """

    def construct_query(self, question, parcel_ctx):
        return f"constructed: {question}"

    def get_jurisdiction_filter(self, parcel_ctx):
        return parcel_ctx.get("JURISDICTION") if parcel_ctx else None

    def get_zone_filter(self, parcel_ctx):
        return "Residential" if parcel_ctx and parcel_ctx.get("ZONING_CODE") == "RS-1-7" else None

    def retrieve(self, query, top_k, mmr, jurisdiction_filter=None, zone_filter=None):
        return [
            RetrievedChunk(
                id="chunk-1",
                text="Residential zoning rules.",
                score=0.95,
                metadata={
                    "source": "city-code.pdf",
                    "start_page": 10,
                    "end_page": 11,
                },
            )
        ]

    def answer(self, question, parcel_ctx, retrieved, history=None):
        return f"Answer for {parcel_ctx.get('APN')}: {question}"


def test_zoning_rag_placeholder_mode_when_rag_is_unavailable(client):
    """
    If RAG is unavailable, the endpoint should return placeholder mode instead
    of crashing.
    """
    response = client.post(
        "/api/rag/zoning/ask",
        json={
            "question": "What can I build here?",
            "apn": "123-ABC",
            "context": {
                "APN": "123-ABC",
                "ZONING_CODE": "RS-1-7",
                "JURISDICTION": "City of San Diego",
            },
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["placeholder"] is True
    assert data["apn"] == "123-ABC"
    assert data["citations"] == []
    assert "session_id" in data
    assert "What can I build here?" in data["answer"]


def test_zoning_rag_uses_rag_object_when_available(client, monkeypatch):
    """
    When main._rag exists, the endpoint should use retrieve() and answer().
    """
    import main

    monkeypatch.setattr(main, "_rag", FakeRagService())
    monkeypatch.setattr(main, "_rag_unavailable_reason", None)

    response = client.post(
        "/api/rag/zoning/ask",
        json={
            "question": "What can I build here?",
            "apn": "123-ABC",
            "context": {
                "APN": "123-ABC",
                "ZONING_CODE": "RS-1-7",
                "JURISDICTION": "City of San Diego",
            },
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["answer"] == "Answer for 123-ABC: What can I build here?"
    assert data["apn"] == "123-ABC"
    assert data["citations"] == [
        {"source": "city-code.pdf", "start_page": 10, "end_page": 11}
    ]


def test_zoning_rag_remembers_parcel_context_across_session(client, monkeypatch):
    """
    First request sends APN/context.
    Follow-up request only sends session_id.
    Backend should remember the selected parcel.
    """
    import main

    monkeypatch.setattr(main, "_rag", FakeRagService())
    monkeypatch.setattr(main, "_rag_unavailable_reason", None)

    first_response = client.post(
        "/api/rag/zoning/ask",
        json={
            "question": "What is this parcel?",
            "apn": "123-ABC",
            "context": {"APN": "123-ABC", "ZONING_CODE": "RS-1-7"},
        },
    )

    session_id = first_response.json()["session_id"]

    followup_response = client.post(
        "/api/rag/zoning/ask",
        json={
            "question": "And what about height limits?",
            "session_id": session_id,
        },
    )

    assert followup_response.status_code == 200

    data = followup_response.json()
    assert data["apn"] == "123-ABC"
    assert data["answer"] == "Answer for 123-ABC: And what about height limits?"


def test_zoning_rag_rejects_missing_question(client):
    """A RAG request without question should fail validation."""
    response = client.post("/api/rag/zoning/ask", json={"apn": "123-ABC"})

    assert response.status_code == 422


def test_spatial_explain_assignment_returns_planner_friendly_shape(client):
    """
    /spatial/explain-assignment should return explanation data that the frontend
    can show when a planner clicks a parcel.
    """
    response = client.post(
        "/api/spatial/explain-assignment",
        json={
            "assigned_use": "green",
            "target_mix": {"green": 0.30, "residential": 0.40},
            "parcel_properties": {
                "APN": "parcel-1",
                "environmental_risk": 0.85,
                "green": 0.9,
                "residential": 0.2,
                "has_flood": 1,
                "is_fire_zone": 1,
                "ZONING_CODE": "Open Space",
            },
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["parcel_id"] == "parcel-1"
    assert data["assigned_use"] == "green"
    assert "headline" in data
    assert "reasons" in data
    assert "warnings" in data
    assert "scores" in data


def test_spatial_explain_assignment_rejects_invalid_use(client):
    """assigned_use only allows residential/commercial/industrial/green."""
    response = client.post(
        "/api/spatial/explain-assignment",
        json={
            "assigned_use": "airport",
            "parcel_properties": {"APN": "parcel-1"},
            "target_mix": {},
        },
    )

    assert response.status_code == 422


def test_risk_counterfactual_returns_score_delta(client):
    """
    /risk/counterfactual should show how risk changes when hazard flags change.
    """
    response = client.post(
        "/api/risk/counterfactual",
        json={
            "parcel_id": "parcel-1",
            "parcel_properties": {
                "has_flood": 0,
                "has_fault": 0,
                "is_fire_zone": 1,
            },
            "changes": {
                "has_flood": 1,
                "unknown_field": 1,
            },
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["parcel_id"] == "parcel-1"
    assert data["original_score"] == 15.0
    assert data["counterfactual_score"] == 40.0
    assert data["delta"] == 25.0
    assert data["applied_changes"] == {"has_flood": {"from": 0, "to": 1}}