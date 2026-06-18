"""
Endpoint tests for Planner's Copilot streaming route.
"""

from __future__ import annotations


class FakeCopilotOrchestrator:
    """Fake streaming orchestrator for SSE endpoint testing."""

    async def stream(self, query, parcel_ids, parcel_features, history):
        yield 'data: {"type":"agent_start","agent":"test"}\n\n'
        yield f'data: {{"type":"final","text":"answer for {query}"}}\n\n'


def test_copilot_query_streams_server_sent_events(client, monkeypatch):
    """
    /copilot/query should return a text/event-stream response.
    """
    import main

    monkeypatch.setattr(main, "_get_copilot", lambda: FakeCopilotOrchestrator())

    response = client.post(
        "/api/copilot/query",
        json={
            "query": "Compare these parcels",
            "parcel_ids": ["p1"],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "agent_start" in response.text
    assert "answer for Compare these parcels" in response.text


def test_copilot_query_rejects_empty_query(client):
    """Copilot query must not be empty."""
    response = client.post("/api/copilot/query", json={"query": ""})

    assert response.status_code == 422