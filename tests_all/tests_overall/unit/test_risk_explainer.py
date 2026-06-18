"""
Unit tests for services.risk_explainer.

These tests check the real scoring logic directly, without going through the
FastAPI endpoint. The endpoint test only proves the route works; these tests
prove the RiskExplainer service itself is calculating the right values.
"""

import pytest

from services.risk_explainer import RISK_WEIGHTS, RiskExplainer


def test_explain_returns_zero_score_when_no_hazard_flags_are_active():
    """
    If no hazard flag is active, the rule-based risk score should be 0.

    This is the safest baseline case for a parcel with no known hazards.
    """
    explainer = RiskExplainer()

    result = explainer.explain({"APN": "parcel-1"})

    assert result["total_rule_score"] == 0.0
    assert result["xgb_risk_score"] is None
    assert len(result["contributions"]) == len(RISK_WEIGHTS)

    # Every known factor should be present but inactive.
    for contribution in result["contributions"]:
        assert contribution["factor"] in RISK_WEIGHTS
        assert contribution["active"] is False
        assert contribution["contribution_pct"] == 0.0


def test_explain_calculates_score_from_active_hazard_flags():
    """
    The total rule score should be the sum of active hazard weights * 100.

    has_flood = 25%
    is_fire_zone = 15%
    in_esa = 5%

    Total = 45%
    """
    explainer = RiskExplainer()

    result = explainer.explain(
        {
            "has_flood": 1,
            "is_fire_zone": 1,
            "in_esa": 1,
        }
    )

    assert result["total_rule_score"] == 45.0

    active_factors = {
        item["factor"]: item
        for item in result["contributions"]
        if item["active"]
    }

    assert active_factors["has_flood"]["contribution_pct"] == 25.0
    assert active_factors["is_fire_zone"]["contribution_pct"] == 15.0
    assert active_factors["in_esa"]["contribution_pct"] == 5.0


def test_explain_sorts_contributions_by_largest_contribution_first():
    """
    Active high-impact factors should appear before lower-impact factors.

    This matters for the UI because planners should see the biggest reason for
    risk first.
    """
    explainer = RiskExplainer()

    result = explainer.explain(
        {
            "in_esa": 1,       # 5%
            "has_flood": 1,    # 25%
            "has_fault": 1,    # 20%
        }
    )

    contributions = result["contributions"]

    assert contributions[0]["factor"] == "has_flood"
    assert contributions[0]["contribution_pct"] == 25.0
    assert contributions[1]["factor"] == "has_fault"
    assert contributions[1]["contribution_pct"] == 20.0


def test_explain_preserves_precomputed_xgb_risk_score():
    """
    The rule-based explanation may be shown alongside the ML/XGBoost risk score.

    The service should not modify or recalculate xgb_risk_score; it should just
    pass it through from the parcel properties.
    """
    explainer = RiskExplainer()

    result = explainer.explain(
        {
            "has_flood": 1,
            "xgb_risk_score": 72.5,
        }
    )

    assert result["total_rule_score"] == 25.0
    assert result["xgb_risk_score"] == 72.5


def test_explain_treats_string_one_as_active_flag():
    """
    GeoJSON/CSV data sometimes stores boolean flags as strings.

    The current implementation converts values using int(...), so "1" should
    behave the same as integer 1.
    """
    explainer = RiskExplainer()

    result = explainer.explain({"has_flood": "1"})

    assert result["total_rule_score"] == 25.0


@pytest.mark.parametrize(
    "changes, expected_counterfactual, expected_delta",
    [
        ({"has_flood": 1}, 40.0, 25.0),       # add flood risk to existing fire risk
        ({"is_fire_zone": 0}, 0.0, -15.0),    # remove existing fire risk
        ({"has_fault": 1, "in_mscp": 1}, 40.0, 25.0),  # add multiple flags
    ],
)
def test_counterfactual_calculates_score_changes(
    changes,
    expected_counterfactual,
    expected_delta,
):
    """
    counterfactual() should show how risk changes when hazard flags are toggled.
    """
    explainer = RiskExplainer()

    original_props = {
        "is_fire_zone": 1,  # original score = 15
        "has_flood": 0,
        "has_fault": 0,
        "in_mscp": 0,
    }

    result = explainer.counterfactual(original_props, changes)

    assert result["original_score"] == 15.0
    assert result["counterfactual_score"] == expected_counterfactual
    assert result["delta"] == expected_delta


def test_counterfactual_ignores_unknown_change_fields():
    """
    Unknown fields should not affect the risk score.

    This protects the endpoint from frontend/UI fields accidentally being sent
    inside the changes object.
    """
    explainer = RiskExplainer()

    result = explainer.counterfactual(
        parcel_props={"is_fire_zone": 1},
        changes={
            "unknown_field": 1,
            "another_fake_field": 0,
        },
    )

    assert result["original_score"] == 15.0
    assert result["counterfactual_score"] == 15.0
    assert result["delta"] == 0.0
    assert result["applied_changes"] == {}


def test_counterfactual_reports_only_valid_applied_changes():
    """
    applied_changes should contain only real risk flags and should show
    before/after values.
    """
    explainer = RiskExplainer()

    result = explainer.counterfactual(
        parcel_props={
            "has_flood": 0,
            "has_fault": 1,
        },
        changes={
            "has_flood": 1,
            "has_fault": 0,
            "not_a_risk_flag": 1,
        },
    )

    assert result["applied_changes"] == {
        "has_flood": {"from": 0, "to": 1},
        "has_fault": {"from": 1, "to": 0},
    }


def test_counterfactual_does_not_mutate_original_properties():
    """
    counterfactual() should calculate a what-if scenario without changing the
    original parcel properties dictionary.
    """
    explainer = RiskExplainer()

    parcel_props = {"has_flood": 0, "is_fire_zone": 1}

    explainer.counterfactual(parcel_props, {"has_flood": 1})

    assert parcel_props == {"has_flood": 0, "is_fire_zone": 1}