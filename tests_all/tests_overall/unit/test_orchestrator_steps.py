"""
Unit tests for services.orchestrator_steps.

These tests verify each orchestration stage in isolation:

- environment stage
- zoning stage
- merge stage
- spatial stage

We mock heavy dependencies such as the real suitability agent, RAG service, and
spatial optimizer. The goal is to prove the step wrapper logic works without
running expensive models or external services.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from services import orchestrator_steps


class FakeSuitabilityAgent:
    """
    Fake environmental agent for run_environment_stage().

    It records the incoming DataFrame so we can assert that parcel IDs were
    passed correctly.
    """

    def __init__(self):
        self.received_df = None

    def predict(self, parcels_df):
        self.received_df = parcels_df.copy()
        return pd.DataFrame(
            {
                "parcel_id": parcels_df["parcel_id"].tolist(),
                "residential": [0.8 for _ in range(len(parcels_df))],
                "commercial": [0.4 for _ in range(len(parcels_df))],
                "industrial": [0.2 for _ in range(len(parcels_df))],
                "green": [0.6 for _ in range(len(parcels_df))],
                "environmental_risk": [0.25 for _ in range(len(parcels_df))],
            }
        )


def test_run_environment_stage_calls_suitability_agent_and_returns_records(monkeypatch):
    """
    The environment stage should:

    1. create a DataFrame from parcel IDs
    2. call the suitability agent
    3. return records in a simple dictionary shape
    """
    fake_agent = FakeSuitabilityAgent()
    monkeypatch.setattr(orchestrator_steps, "get_suitability_agent", lambda: fake_agent)

    result = orchestrator_steps.run_environment_stage(["p1", "p2"])

    assert result["stage"] == "environment"
    assert result["parcel_count"] == 2
    assert fake_agent.received_df["parcel_id"].tolist() == ["p1", "p2"]

    assert result["results"] == [
        {
            "parcel_id": "p1",
            "residential": 0.8,
            "commercial": 0.4,
            "industrial": 0.2,
            "green": 0.6,
            "environmental_risk": 0.25,
        },
        {
            "parcel_id": "p2",
            "residential": 0.8,
            "commercial": 0.4,
            "industrial": 0.2,
            "green": 0.6,
            "environmental_risk": 0.25,
        },
    ]


def test_run_environment_stage_propagates_agent_errors(monkeypatch):
    """
    If the suitability agent fails, the stage should not hide the error.

    The orchestrator service is responsible for marking the job as failed.
    """

    class BrokenAgent:
        def predict(self, parcels_df):
            raise RuntimeError("suitability model failed")

    monkeypatch.setattr(orchestrator_steps, "get_suitability_agent", lambda: BrokenAgent())

    with pytest.raises(RuntimeError, match="suitability model failed"):
        orchestrator_steps.run_environment_stage(["p1"])


class FakeRetrievedChunk:
    """
    Minimal object shaped like RetrievedChunk from RagService.
    """

    def __init__(self, text, metadata):
        self.text = text
        self.metadata = metadata


class FakeRagService:
    """
    Fake RAG service that returns shared zoning chunks.
    """

    def __init__(self, persist_dir):
        self.persist_dir = persist_dir

    def retrieve(self, query, top_k, mmr):
        assert query == "What are the zoning regulations, setbacks, FAR limits, and allowed uses?"
        assert top_k == 5
        assert mmr is True

        return [
            FakeRetrievedChunk(
                text="Residential zoning rules. " * 20,
                metadata={
                    "source": "city-code.pdf",
                    "jurisdiction": "City of San Diego",
                    "section": "131.0431",
                },
            ),
            FakeRetrievedChunk(
                text="Short commercial rule.",
                metadata={
                    "source": "county-code.pdf",
                    "jurisdiction": "San Diego County",
                    "section": "2000",
                },
            ),
        ]


def test_run_zoning_stage_returns_shared_regulations_for_each_parcel(
    monkeypatch,
    tmp_path,
):
    """
    The current zoning stage does one shared batched retrieval and attaches the
    same retrieved context to each parcel.
    """
    monkeypatch.setattr(
        orchestrator_steps,
        "resolve_rag_persist_dir",
        lambda backend_dir: tmp_path,
    )
    monkeypatch.setattr(orchestrator_steps, "RagService", FakeRagService)

    result = orchestrator_steps.run_zoning_stage(["p1", "p2"])

    assert result["stage"] == "zoning"
    assert result["parcel_count"] == 2
    assert len(result["results"]) == 2

    for parcel_result in result["results"]:
        assert parcel_result["parcel_id"] in {"p1", "p2"}
        assert parcel_result["regulations_found"] == 2
        assert len(parcel_result["regulations"]) == 2

        first_regulation = parcel_result["regulations"][0]
        assert first_regulation["source"] == "city-code.pdf"
        assert first_regulation["jurisdiction"] == "City of San Diego"
        assert first_regulation["section"] == "131.0431"

        # Long text should be shortened for response payloads.
        assert first_regulation["text_preview"].endswith("...")
        assert len(first_regulation["text_preview"]) <= 203


def test_run_zoning_stage_returns_placeholder_when_rag_service_cannot_start(
    monkeypatch,
    tmp_path,
):
    """
    If RAG cannot initialize, zoning stage should return placeholder results
    instead of crashing the whole orchestration pipeline.
    """

    class BrokenRagService:
        def __init__(self, persist_dir):
            raise RuntimeError("missing RAG credentials")

    monkeypatch.setattr(
        orchestrator_steps,
        "resolve_rag_persist_dir",
        lambda backend_dir: tmp_path,
    )
    monkeypatch.setattr(orchestrator_steps, "RagService", BrokenRagService)

    result = orchestrator_steps.run_zoning_stage(["p1", "p2"])

    assert result["stage"] == "zoning"
    assert result["parcel_count"] == 2
    assert "RAG placeholder mode" in result["note"]

    for parcel_result in result["results"]:
        assert parcel_result["placeholder"] is True
        assert parcel_result["regulations_found"] == 0
        assert parcel_result["regulations"] == []
        assert parcel_result["reason"] == "missing RAG credentials"


def test_run_zoning_stage_returns_empty_regulations_when_retrieve_fails(
    monkeypatch,
    tmp_path,
):
    """
    If RAG initializes but retrieval fails, the stage should still return a
    valid empty zoning result for each parcel.
    """

    class RetrieveFailsRagService:
        def __init__(self, persist_dir):
            pass

        def retrieve(self, query, top_k, mmr):
            raise RuntimeError("Chroma query failed")

    monkeypatch.setattr(
        orchestrator_steps,
        "resolve_rag_persist_dir",
        lambda backend_dir: tmp_path,
    )
    monkeypatch.setattr(orchestrator_steps, "RagService", RetrieveFailsRagService)

    result = orchestrator_steps.run_zoning_stage(["p1"])

    assert result["stage"] == "zoning"
    assert result["parcel_count"] == 1
    assert result["results"] == [
        {
            "parcel_id": "p1",
            "regulations_found": 0,
            "regulations": [],
        }
    ]


def test_merge_outputs_combines_environment_and_zoning_by_parcel_id():
    """
    merge_outputs() should join environment and zoning results using parcel_id.
    """
    env_data = {
        "results": [
            {
                "parcel_id": "p1",
                "residential": 0.9,
                "commercial": 0.4,
                "industrial": 0.1,
                "green": 0.5,
                "environmental_risk": 0.2,
            },
            {
                "parcel_id": "p2",
                "residential": 0.3,
                "commercial": 0.6,
                "industrial": 0.4,
                "green": 0.8,
                "environmental_risk": 0.7,
            },
        ]
    }
    zoning_data = {
        "results": [
            {
                "parcel_id": "p1",
                "regulations_found": 1,
                "regulations": [{"section": "131.0431"}],
            }
        ]
    }

    result = orchestrator_steps.merge_outputs(env_data, zoning_data)

    assert result["stage"] == "merge"
    assert result["parcel_count"] == 2

    merged_by_id = {
        item["parcel_id"]: item
        for item in result["unified_results"]
    }

    assert merged_by_id["p1"]["suitability"] == {
        "residential": 0.9,
        "commercial": 0.4,
        "industrial": 0.1,
        "green": 0.5,
        "environmental_risk": 0.2,
    }
    assert merged_by_id["p1"]["zoning"] == {
        "regulations_found": 1,
        "regulations": [{"section": "131.0431"}],
    }

    # p2 has no zoning result, so zoning defaults should be used.
    assert merged_by_id["p2"]["zoning"] == {
        "regulations_found": 0,
        "regulations": [],
    }


def test_merge_outputs_includes_parcels_that_exist_only_in_zoning_results():
    """
    If a parcel appears only in zoning results, it should still be included in
    unified_results with default suitability values.
    """
    result = orchestrator_steps.merge_outputs(
        env_data={"results": []},
        zoning_data={
            "results": [
                {
                    "parcel_id": "zoning-only",
                    "regulations_found": 1,
                    "regulations": [{"source": "zoning.pdf"}],
                }
            ]
        },
    )

    assert result["parcel_count"] == 1
    unified = result["unified_results"][0]

    assert unified["parcel_id"] == "zoning-only"
    assert unified["suitability"] == {
        "residential": 0.0,
        "commercial": 0.0,
        "industrial": 0.0,
        "green": 0.0,
        "environmental_risk": 0.0,
    }
    assert unified["zoning"]["regulations_found"] == 1


def test_run_spatial_stage_returns_empty_result_when_no_unified_data():
    """
    Spatial stage should gracefully handle empty merge output.
    """
    result = orchestrator_steps.run_spatial_stage({"unified_results": []})

    assert result == {
        "stage": "spatial",
        "parcel_count": 0,
        "plans": [],
        "objective_names": [],
        "note": "No merged parcel data available for spatial optimization.",
    }


class FakeSpatialOptimizer:
    """
    Fake optimizer for run_spatial_stage().

    It captures the ParcelRecord objects produced by the stage so tests can
    verify that unified data was converted correctly.
    """

    received_parcels = None

    def __init__(self, config):
        self.config = config

    def optimize(self, parcels):
        FakeSpatialOptimizer.received_parcels = parcels

        return SimpleNamespace(
            objective_names=("zoning_violation_penalty", "environmental_risk_exposure"),
            plans=[
                SimpleNamespace(
                    rank=0,
                    crowding_distance=1.5,
                    objectives=(0.1, 0.2),
                    assignments=[
                        SimpleNamespace(
                            parcel_id=parcels[0].parcel_id,
                            use_code=0,
                            use_label="residential",
                        ),
                        SimpleNamespace(
                            parcel_id=parcels[1].parcel_id,
                            use_code=3,
                            use_label="green",
                        ),
                    ],
                )
            ],
        )


def test_run_spatial_stage_converts_unified_data_and_serializes_optimizer_result(
    monkeypatch,
):
    """
    run_spatial_stage() should:

    1. convert unified parcel dictionaries into ParcelRecord objects
    2. call SpatialOptimizer.optimize()
    3. serialize plans into JSON-friendly dictionaries
    """
    monkeypatch.setattr(orchestrator_steps, "SpatialOptimizer", FakeSpatialOptimizer)

    unified_data = {
        "unified_results": [
            {
                "parcel_id": "p1",
                "suitability": {
                    "residential": 0.9,
                    "commercial": 0.3,
                    "industrial": 0.1,
                    "green": 0.4,
                    "environmental_risk": 0.2,
                },
            },
            {
                "parcel_id": "p2",
                "suitability": {
                    "residential": 0.2,
                    "commercial": 0.4,
                    "industrial": 0.5,
                    "green": 0.9,
                    "environmental_risk": 0.8,
                },
            },
        ]
    }

    result = orchestrator_steps.run_spatial_stage(unified_data)

    assert result["stage"] == "spatial"
    assert result["parcel_count"] == 2
    assert result["objective_names"] == [
        "zoning_violation_penalty",
        "environmental_risk_exposure",
    ]
    assert result["plans"] == [
        {
            "rank": 0,
            "crowding_distance": 1.5,
            "objectives": [0.1, 0.2],
            "assignments": [
                {"parcel_id": "p1", "use_code": 0, "use_label": "residential"},
                {"parcel_id": "p2", "use_code": 3, "use_label": "green"},
            ],
        }
    ]

    parcels = FakeSpatialOptimizer.received_parcels
    assert len(parcels) == 2
    assert parcels[0].parcel_id == "p1"
    assert parcels[0].risk_score_norm == 0.2
    assert parcels[0].suitability["residential"] == 0.9
    assert parcels[0].allowed_use_codes == ()


def test_run_spatial_stage_falls_back_to_zero_when_risk_value_is_invalid(
    monkeypatch,
):
    """
    environmental_risk is protected with a try/except in the current code.
    Invalid risk values should become 0.0 instead of crashing the stage.
    """
    monkeypatch.setattr(orchestrator_steps, "SpatialOptimizer", FakeSpatialOptimizer)

    unified_data = {
        "unified_results": [
            {
                "parcel_id": "bad-risk",
                "suitability": {
                    "residential": 0.5,
                    "commercial": 0.5,
                    "industrial": 0.5,
                    "green": 0.5,
                    "environmental_risk": "not-a-number",
                },
            },
            {
                "parcel_id": "normal",
                "suitability": {
                    "residential": 0.5,
                    "commercial": 0.5,
                    "industrial": 0.5,
                    "green": 0.5,
                    "environmental_risk": 0.4,
                },
            },
        ]
    }

    orchestrator_steps.run_spatial_stage(unified_data)

    parcels = FakeSpatialOptimizer.received_parcels
    assert parcels[0].parcel_id == "bad-risk"
    assert parcels[0].risk_score_norm == 0.0
    assert parcels[1].parcel_id == "normal"
    assert parcels[1].risk_score_norm == 0.4


def test_run_spatial_stage_propagates_optimizer_errors(monkeypatch):
    """
    If the optimizer fails, the stage should raise the error so the higher-level
    orchestrator can mark the job as failed.
    """

    class BrokenSpatialOptimizer:
        def __init__(self, config):
            pass

        def optimize(self, parcels):
            raise RuntimeError("optimizer failed")

    monkeypatch.setattr(orchestrator_steps, "SpatialOptimizer", BrokenSpatialOptimizer)

    unified_data = {
        "unified_results": [
            {
                "parcel_id": "p1",
                "suitability": {
                    "residential": 0.5,
                    "commercial": 0.5,
                    "industrial": 0.5,
                    "green": 0.5,
                    "environmental_risk": 0.5,
                },
            }
        ]
    }

    with pytest.raises(RuntimeError, match="optimizer failed"):
        orchestrator_steps.run_spatial_stage(unified_data)