import json
from pathlib import Path

import pandas as pd
import pytest

from agent.environment_agent.agent import SuitabilityAgent, find_default_risk_data_path


# These are the exact columns that SuitabilityAgent.predict() should return.
# Keeping this list in one place makes the tests easier to read and update.
EXPECTED_OUTPUT_COLUMNS = [
    "parcel_id",
    "residential",
    "commercial",
    "industrial",
    "green",
    "environmental_risk",
]


def make_agent_without_precomputed_data() -> SuitabilityAgent:
    """
    Create a SuitabilityAgent without running __init__.

    This avoids loading real project GeoJSON files during unit tests.
    """
    agent = SuitabilityAgent.__new__(SuitabilityAgent)
    agent.risk_data = pd.DataFrame()
    return agent


def test_load_data_prefers_xgb_score_and_falls_back_to_rule_score(tmp_path: Path):
    """
    The agent should load risk scores from GeoJSON.

    Important behavior:
    - If xgb_risk_score exists, use it because it is the primary ML score.
    - If xgb_risk_score is missing, fall back to rule_risk_score.
    - Scores are stored as 0-100 internally and normalized to 0-1 during predict().
    """
    risk_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "APN": "A-1",
                    "xgb_risk_score": 40,
                    "rule_risk_score": 90,
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "APN": "B-2",
                    "rule_risk_score": 60,
                },
            },
        ],
    }

    risk_file = tmp_path / "risk.geojson"
    risk_file.write_text(json.dumps(risk_geojson), encoding="utf-8")

    agent = make_agent_without_precomputed_data()
    agent.load_data(risk_file)

    parcels_df = pd.DataFrame({"parcel_id": ["A-1", "B-2"]})
    result = agent.predict(parcels_df)

    # A-1 should use xgb_risk_score=40, not rule_risk_score=90.
    assert result.loc[0, "environmental_risk"] == pytest.approx(0.40)

    # B-2 has no xgb score, so rule_risk_score=60 is used as fallback.
    assert result.loc[1, "environmental_risk"] == pytest.approx(0.60)


def test_predict_returns_expected_columns_and_preserves_input_order():
    """
    The frontend depends on the response matching the original parcel order.

    This test makes sure that even when risk data is indexed by APN, the output
    remains aligned with the order of the incoming parcel DataFrame.
    """
    agent = make_agent_without_precomputed_data()

    agent.risk_data = pd.DataFrame(
        {
            "xgb_risk_score": [20, 80],
        },
        index=["A-1", "B-2"],
    )

    # Notice input order is B-2 first, then A-1.
    parcels_df = pd.DataFrame({"parcel_id": ["B-2", "A-1"]})
    result = agent.predict(parcels_df)

    assert list(result.columns) == EXPECTED_OUTPUT_COLUMNS
    assert result["parcel_id"].tolist() == ["B-2", "A-1"]
    assert result["environmental_risk"].tolist() == pytest.approx([0.80, 0.20])


def test_predict_clamps_precomputed_risk_scores_to_valid_range():
    """
    Precomputed risk scores should be safely normalized to the 0-1 range.

    This protects the frontend and optimizer from bad values such as:
    - negative risk scores
    - risk scores greater than 100
    """
    agent = make_agent_without_precomputed_data()

    agent.risk_data = pd.DataFrame(
        {
            "xgb_risk_score": [-20, 150],
        },
        index=["LOW-BAD", "HIGH-BAD"],
    )

    parcels_df = pd.DataFrame({"parcel_id": ["LOW-BAD", "HIGH-BAD"]})
    result = agent.predict(parcels_df)

    # -20 / 100 should be clipped to 0.0.
    assert result.loc[0, "environmental_risk"] == pytest.approx(0.0)

    # 150 / 100 should be clipped to 1.0.
    assert result.loc[1, "environmental_risk"] == pytest.approx(1.0)

    # All suitability scores should also remain inside 0-1.
    score_columns = ["residential", "commercial", "industrial", "green"]
    assert ((result[score_columns] >= 0.0) & (result[score_columns] <= 1.0)).all().all()


def test_predict_uses_feature_based_fallback_when_apn_is_missing_from_lookup():
    """
    If a parcel is not found in the precomputed APN lookup, the agent should
    estimate risk from available environmental features.

    Here we use extreme feature values to make the expected result obvious:
    - AQI = 150
    - impervious = 100
    - clay = 100
    - sand = 0

    Based on the current formula, this should produce environmental_risk = 1.0.
    """
    agent = make_agent_without_precomputed_data()

    parcels_df = pd.DataFrame(
        [
            {
                "parcel_id": "MISSING-APN",
                "aqi_mean": 150,
                "impervious_mean": 100,
                "soil_clay_pct": 100,
                "soil_sand_pct": 0,
            }
        ]
    )

    result = agent.predict(parcels_df)

    assert result.loc[0, "environmental_risk"] == pytest.approx(1.0)
    assert result.loc[0, "residential"] == pytest.approx(0.0)
    assert result.loc[0, "commercial"] == pytest.approx(0.0)
    assert result.loc[0, "industrial"] == pytest.approx(0.1)
    assert result.loc[0, "green"] == pytest.approx(1.0)


def test_predict_uses_neutral_scores_when_no_risk_or_features_exist():
    """
    If the parcel is missing from the precomputed lookup and has no usable
    fallback features, the agent should return safe neutral suitability scores.

    This is important because missing GIS data should not crash the endpoint.
    """
    agent = make_agent_without_precomputed_data()

    parcels_df = pd.DataFrame({"parcel_id": ["UNKNOWN-1"]})
    result = agent.predict(parcels_df)

    assert result.loc[0, "environmental_risk"] == pytest.approx(0.0)
    assert result.loc[0, "residential"] == pytest.approx(0.5)
    assert result.loc[0, "commercial"] == pytest.approx(0.5)
    assert result.loc[0, "industrial"] == pytest.approx(0.5)
    assert result.loc[0, "green"] == pytest.approx(0.5)


def test_suitability_scores_follow_expected_risk_heuristics():
    """
    This test locks the current planning heuristic behavior.

    For a 50/100 risk score, the current formula should produce:
    - residential = max(0, 0.8 - 0.5) = 0.3
    - commercial  = max(0, 0.7 - 0.5 * 0.8) = 0.3
    - industrial  = max(0, 0.6 - 0.5 * 0.5) = 0.35
    - green       = min(1, 0.2 + 0.5) = 0.7
    """
    agent = make_agent_without_precomputed_data()

    agent.risk_data = pd.DataFrame(
        {"xgb_risk_score": [50]},
        index=["P-50"],
    )

    parcels_df = pd.DataFrame({"parcel_id": ["P-50"]})
    result = agent.predict(parcels_df)

    assert result.loc[0, "environmental_risk"] == pytest.approx(0.50)
    assert result.loc[0, "residential"] == pytest.approx(0.30)
    assert result.loc[0, "commercial"] == pytest.approx(0.30)
    assert result.loc[0, "industrial"] == pytest.approx(0.35)
    assert result.loc[0, "green"] == pytest.approx(0.70)


def test_find_default_risk_data_path_returns_first_available_candidate(tmp_path: Path):
    """
    find_default_risk_data_path() should return the preferred clipped GeoJSON
    if it exists inside environment_agent/data/outputs/.

    This test only checks path discovery. It does not load or validate the file.
    """
    fake_agent_dir = tmp_path / "backend" / "agent" / "environment_agent"
    output_dir = fake_agent_dir / "data" / "outputs"
    output_dir.mkdir(parents=True)

    preferred_file = output_dir / "parcels_env_risk_clipped.geojson"
    preferred_file.write_text(
        '{"type":"FeatureCollection","features":[]}',
        encoding="utf-8",
    )

    found_path = find_default_risk_data_path(base_dir=fake_agent_dir)

    assert found_path == preferred_file
    