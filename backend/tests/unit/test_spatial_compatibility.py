from __future__ import annotations

from services.spatial_compatibility import (
    build_neighbor_pairs,
    make_spatial_compatibility_objective,
    normalize_land_use,
    normalize_risk_value,
    score_spatial_compatibility,
)
from agent.spatial_agent.spatial.types import OptimizationContext, ParcelRecord


def _feature(parcel_id: str, lon: float, lat: float, **properties):
    return {
        "type": "Feature",
        "id": parcel_id,
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": {
            "APN": parcel_id,
            "centroid": {"x": lon, "y": lat},
            **properties,
        },
    }


def test_normalize_land_use_accepts_common_variants():
    assert normalize_land_use("Residential") == "residential"
    assert normalize_land_use("RES") == "residential"
    assert normalize_land_use("housing") == "residential"
    assert normalize_land_use("retail") == "commercial"
    assert normalize_land_use("mixed_use") == "commercial"
    assert normalize_land_use("manufacturing") == "industrial"
    assert normalize_land_use("open_space") == "green"
    assert normalize_land_use("conservation") == "green"
    assert normalize_land_use("unmapped") == "unknown"


def test_normalize_risk_value_clamps_and_converts_percentages():
    assert normalize_risk_value(None) == 0.0
    assert normalize_risk_value("bad") == 0.0
    assert normalize_risk_value(0.42) == 0.42
    assert normalize_risk_value(42) == 0.42
    assert normalize_risk_value(125) == 1.0
    assert normalize_risk_value(-1) == 0.0


def test_build_neighbor_pairs_prevents_duplicate_and_self_pairs():
    features = {
        "a": _feature("a", -117.0, 32.0),
        "b": _feature("b", -117.0005, 32.0),
        "c": _feature("c", -117.01, 32.0),
    }

    pairs = build_neighbor_pairs(["a", "b", "c"], features, radius_m=100)

    assert len(pairs) == 1
    assert pairs[0][0:2] == ("a", "b")
    assert pairs[0][2] > 0


def test_no_neighbor_case_returns_neutral_summary():
    result = score_spatial_compatibility({}, [], {})

    assert result["score"] == 0.0
    assert result["summary"]["neighbor_pairs_evaluated"] == 0
    assert result["summary"]["compatible_pairs"] == 0
    assert result["summary"]["conflict_pairs"] == 0


def test_industrial_near_residential_counts_conflict_and_scores_lower_than_compatible_pair():
    features = {
        "a": _feature("a", -117.0, 32.0),
        "b": _feature("b", -117.0005, 32.0),
    }
    pairs = [("a", "b", 50.0)]

    conflict = score_spatial_compatibility(
        {"a": "industrial", "b": "residential"},
        pairs,
        features,
    )
    compatible = score_spatial_compatibility(
        {"a": "residential", "b": "residential"},
        pairs,
        features,
    )

    assert conflict["summary"]["industrial_residential_conflicts"] == 1
    assert conflict["summary"]["conflict_pairs"] == 1
    assert compatible["summary"]["compatible_pairs"] == 1
    assert conflict["score"] < compatible["score"]


def test_green_near_high_risk_parcel_counts_buffer_and_improves_score():
    features = {
        "a": _feature("a", -117.0, 32.0, environmental_risk=0.75),
        "b": _feature("b", -117.0005, 32.0),
    }
    pairs = [("a", "b", 50.0)]

    green_buffer = score_spatial_compatibility({"a": "green", "b": "residential"}, pairs, features)
    built_pair = score_spatial_compatibility({"a": "commercial", "b": "residential"}, pairs, features)

    assert green_buffer["summary"]["green_buffer_pairs"] == 1
    assert green_buffer["score"] > built_pair["score"]


def test_spatial_compatibility_objective_is_neutral_without_pairs():
    objective = make_spatial_compatibility_objective([], {}, weight=0.15)
    context = OptimizationContext(
        parcels=(
            ParcelRecord(parcel_id="a", area_m2=100.0, centroid_x=-117.0, centroid_y=32.0),
        ),
        land_use_labels=("residential", "commercial", "industrial", "green"),
    )

    assert objective((0,), context) == 0.0
