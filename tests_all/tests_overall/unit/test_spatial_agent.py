"""
Unit tests for the Spatial Agent.

These tests focus on the spatial agent's internal behavior:

1. Converting GeoJSON parcels into ParcelRecord objects
2. Detecting parcel adjacency
3. Calculating objective functions
4. Running a small deterministic optimization

Important:
These are unit tests, not endpoint tests.
So we use very small fake parcels instead of real project GeoJSON files.
"""

import pytest

from agent.spatial_agent.spatial.config import NSGA2Config, SpatialConfig
from agent.spatial_agent.spatial.geo import (
    build_adjacency_from_geojson,
    build_parcels_from_geojson,
    infer_allowed_use_labels,
    normalize_risk_score,
)
from agent.spatial_agent.spatial.objectives import (
    environmental_risk_exposure,
    fragmentation_penalty,
    make_green_area_deviation,
    make_land_use_balance_penalty,
    zoning_violation_penalty,
)
from agent.spatial_agent.spatial.optimizer import SpatialOptimizer
from agent.spatial_agent.spatial.types import OptimizationContext, ParcelRecord


# These are the land-use labels used by your spatial optimizer.
# The index of each label becomes its use_code:
# 0 = residential
# 1 = commercial
# 2 = industrial
# 3 = green
LAND_USES = ("residential", "commercial", "industrial", "green")


def square_feature(parcel_id: str, x1: float, y1: float, x2: float, y2: float, **properties):
    """
    Build a small square GeoJSON feature.

    We use this helper so every test does not need to repeat the full GeoJSON
    structure again and again.
    """
    base_properties = {
        "APN": parcel_id,
        "environmental_risk": 0.25,
        "suitability_residential": 0.8,
        "suitability_commercial": 0.5,
        "suitability_industrial": 0.2,
        "suitability_green": 0.6,
    }

    # Allow individual tests to override default properties.
    base_properties.update(properties)

    return {
        "type": "Feature",
        "id": parcel_id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [x1, y1],
                    [x2, y1],
                    [x2, y2],
                    [x1, y2],
                    [x1, y1],
                ]
            ],
        },
        "properties": base_properties,
    }


@pytest.fixture
def sample_parcels():
    """
    Create a small deterministic parcel set.

    The optimizer can run on these 3 parcels very quickly.
    """
    return (
        ParcelRecord(
            parcel_id="p1",
            area_m2=100.0,
            centroid_x=0.0,
            centroid_y=0.0,
            risk_score_norm=0.2,
            suitability={
                "residential": 0.9,
                "commercial": 0.3,
                "industrial": 0.1,
                "green": 0.4,
            },
            allowed_use_codes=(0, 3),
        ),
        ParcelRecord(
            parcel_id="p2",
            area_m2=100.0,
            centroid_x=1.0,
            centroid_y=0.0,
            risk_score_norm=0.8,
            suitability={
                "residential": 0.2,
                "commercial": 0.4,
                "industrial": 0.5,
                "green": 0.9,
            },
            allowed_use_codes=(2, 3),
        ),
        ParcelRecord(
            parcel_id="p3",
            area_m2=100.0,
            centroid_x=2.0,
            centroid_y=0.0,
            risk_score_norm=0.5,
            suitability={
                "residential": 0.6,
                "commercial": 0.8,
                "industrial": 0.3,
                "green": 0.5,
            },
            allowed_use_codes=(0, 1),
        ),
    )


@pytest.fixture
def sample_context(sample_parcels):
    """
    Build an OptimizationContext with simple adjacency.

    Adjacency:
    p1 touches p2
    p2 touches p3

    So the graph is:

    p1 ---- p2 ---- p3
    """
    return OptimizationContext(
        parcels=sample_parcels,
        land_use_labels=LAND_USES,
        adjacency={
            0: (1,),
            1: (0, 2),
            2: (1,),
        },
    )


def test_normalize_risk_score_accepts_multiple_property_names():
    """
    Spatial optimization may receive risk scores from different backend modules.

    This test checks that all supported risk field names are understood.
    """
    assert normalize_risk_score({"risk_score_norm": 0.7}) == pytest.approx(0.7)
    assert normalize_risk_score({"environmental_risk": 0.4}) == pytest.approx(0.4)

    # xgb_risk_score and rule_risk_score are usually 0-100,
    # so they should be divided by 100.
    assert normalize_risk_score({"xgb_risk_score": 75}) == pytest.approx(0.75)
    assert normalize_risk_score({"rule_risk_score": 35}) == pytest.approx(0.35)


@pytest.mark.parametrize(
    "properties, expected_labels",
    [
        (
            {"allowed_uses": "residential, green"},
            ("residential", "green"),
        ),
        (
            {"allowed_uses": ["commercial", "industrial"]},
            ("commercial", "industrial"),
        ),
        (
            {"ZONING_CODE": "RS Residential"},
            ("residential",),
        ),
        (
            {"GP_LAND_USE": "Open Space / Park"},
            ("green",),
        ),
    ],
)
def test_infer_allowed_use_labels_from_properties(properties, expected_labels):
    """
    The optimizer should understand allowed uses from parcel properties.

    This matters because zoning should restrict what land use can be assigned
    to a parcel.
    """
    labels = infer_allowed_use_labels(properties, LAND_USES)

    assert labels == expected_labels


def test_build_parcels_from_geojson_extracts_core_spatial_fields():
    """
    build_parcels_from_geojson() converts frontend/backend GeoJSON features
    into ParcelRecord objects used by the optimizer.
    """
    features = [
        square_feature(
            "P-1",
            0,
            0,
            1,
            1,
            environmental_risk=0.65,
            allowed_uses="residential,green",
        )
    ]

    parcels = build_parcels_from_geojson(features, land_use_labels=LAND_USES)

    assert len(parcels) == 1

    parcel = parcels[0]

    assert parcel.parcel_id == "P-1"
    assert parcel.risk_score_norm == pytest.approx(0.65)
    assert parcel.suitability["residential"] == pytest.approx(0.8)
    assert parcel.suitability["green"] == pytest.approx(0.6)

    # residential = 0, green = 3
    assert parcel.allowed_use_codes == (0, 3)

    # Area and centroid should come from the polygon geometry.
    assert parcel.area_m2 > 0
    assert parcel.centroid_x == pytest.approx(0.5)
    assert parcel.centroid_y == pytest.approx(0.5)


def test_build_parcels_from_geojson_falls_back_to_feature_id_when_apn_missing():
    """
    Some GeoJSON features may not contain APN inside properties.

    In that case, the spatial agent should still create a stable parcel_id
    using the feature id.
    """
    feature = square_feature("feature-id-1", 0, 0, 1, 1)

    # Remove APN to simulate incomplete parcel properties.
    feature["properties"].pop("APN")

    parcels = build_parcels_from_geojson([feature], land_use_labels=LAND_USES)

    assert parcels[0].parcel_id == "feature-id-1"


def test_build_adjacency_from_geojson_detects_touching_neighbors():
    """
    Adjacent parcels should become neighbors in the adjacency map.

    Here:
    P-1 touches P-2
    P-2 touches P-3
    P-1 does not directly touch P-3
    """
    features = [
        square_feature("P-1", 0, 0, 1, 1),
        square_feature("P-2", 1, 0, 2, 1),
        square_feature("P-3", 2, 0, 3, 1),
    ]

    adjacency = build_adjacency_from_geojson(
        features,
        adjacency_predicate="touches",
    )

    assert adjacency[0] == (1,)
    assert adjacency[1] == (0, 2)
    assert adjacency[2] == (1,)


def test_zoning_violation_penalty_counts_invalid_assignments(sample_context):
    """
    zoning_violation_penalty should count parcels assigned to disallowed uses.

    chromosome = (0, 2, 3)

    Meaning:
    p1 -> residential: allowed
    p2 -> industrial: allowed
    p3 -> green: not allowed

    Therefore, penalty should be 1.
    """
    chromosome = (0, 2, 3)

    penalty = zoning_violation_penalty(chromosome, sample_context)

    assert penalty == pytest.approx(1.0)


def test_green_area_deviation_uses_area_not_parcel_count(sample_context):
    """
    Green target should be based on area.

    With equal parcel areas, assigning 1 out of 3 parcels to green gives:

    green fraction = 1 / 3

    If target is 0.30, deviation is:

    1/3 - 0.30
    """
    objective = make_green_area_deviation(target_fraction=0.30)
    chromosome = (0, 3, 1)

    value = objective(chromosome, sample_context)

    assert value == pytest.approx((1 / 3) - 0.30)


def test_environmental_risk_exposure_counts_only_built_uses(sample_context):
    """
    Environmental risk exposure should count risk on built uses only.

    Built uses:
    - residential
    - commercial
    - industrial

    Green should not contribute to built-risk exposure.

    chromosome = (0, 3, 1)

    Meaning:
    p1 -> residential, counted
    p2 -> green, ignored
    p3 -> commercial, counted

    Risk exposure:

    p1 risk contribution = 0.2 * 100
    p3 risk contribution = 0.5 * 100
    total parcel area = 300

    expected = 70 / 300
    """
    chromosome = (0, 3, 1)

    value = environmental_risk_exposure(chromosome, sample_context)

    assert value == pytest.approx(70.0 / 300.0)


def test_fragmentation_penalty_is_fraction_of_boundary_changes(sample_context):
    """
    Fragmentation penalty should be normalized between 0 and 1.

    There are two adjacency edges:
    - p1-p2
    - p2-p3

    In chromosome = (0, 3, 1), both neighboring pairs have different uses.

    So fragmentation should be 1.0.
    """
    chromosome = (0, 3, 1)

    value = fragmentation_penalty(chromosome, sample_context)

    assert value == pytest.approx(1.0)


def test_land_use_balance_penalty_normalizes_target_mix(sample_context):
    """
    Target mix values may be given as percentages or weights.

    This test uses:

    residential = 70
    green = 30

    The objective should normalize them internally to:

    residential = 0.7
    green = 0.3
    """
    objective = make_land_use_balance_penalty(
        {
            "residential": 70,
            "green": 30,
        }
    )

    # Current mix:
    # residential = 2/3
    # green = 1/3
    chromosome = (0, 0, 3)

    value = objective(chromosome, sample_context)

    expected = abs((2 / 3) - 0.7) + abs((1 / 3) - 0.3)

    assert value == pytest.approx(expected)


def test_optimizer_returns_decoded_plans_with_valid_assignments(sample_parcels):
    """
    This is a small end-to-end unit test for the optimizer class.

    It runs NSGA-II with tiny settings so the test stays fast.
    Then it checks that the result is decoded into frontend-friendly plans.
    """
    optimizer = SpatialOptimizer(
        config=SpatialConfig(
            land_use_labels=LAND_USES,
            nsga2=NSGA2Config(
                population_size=12,
                generations=3,
                num_output_plans=2,
                random_seed=42,
            ),
        )
    )

    result = optimizer.optimize(parcels=sample_parcels)

    assert result.population_size == 12
    assert result.generations == 3
    assert len(result.plans) >= 1
    assert len(result.plans) <= 2

    assert result.objective_names == (
        "zoning_violation_penalty",
        "mean_suitability_loss",
        "green_area_deviation",
        "environmental_risk_exposure",
        "fragmentation_penalty",
    )

    for plan in result.plans:
        assert len(plan.assignments) == len(sample_parcels)
        assert len(plan.objectives) == len(result.objective_names)

        for assignment in plan.assignments:
            assert assignment.parcel_id in {"p1", "p2", "p3"}
            assert assignment.use_code in {0, 1, 2, 3}
            assert assignment.use_label in LAND_USES


def test_optimizer_respects_allowed_use_codes_in_generated_assignments(sample_parcels):
    """
    The optimizer should generate assignments from each parcel's allowed uses.

    This matters because zoning constraints should guide the search space,
    not only be punished afterward.
    """
    optimizer = SpatialOptimizer(
        config=SpatialConfig(
            land_use_labels=LAND_USES,
            nsga2=NSGA2Config(
                population_size=12,
                generations=2,
                num_output_plans=2,
                random_seed=7,
            ),
        )
    )

    result = optimizer.optimize(parcels=sample_parcels)

    allowed_by_parcel_id = {
        parcel.parcel_id: set(parcel.allowed_use_codes)
        for parcel in sample_parcels
    }

    for plan in result.plans:
        for assignment in plan.assignments:
            assert assignment.use_code in allowed_by_parcel_id[assignment.parcel_id]


def test_optimizer_progress_callback_receives_major_stages(sample_parcels):
    """
    The frontend can show progress while optimization is running.

    This test makes sure the optimizer emits useful progress stages.
    """
    events = []

    optimizer = SpatialOptimizer(
        config=SpatialConfig(
            land_use_labels=LAND_USES,
            nsga2=NSGA2Config(
                population_size=8,
                generations=2,
                num_output_plans=1,
                random_seed=1,
            ),
        )
    )

    optimizer.optimize(
        parcels=sample_parcels,
        progress_callback=events.append,
        progress_every_generations=1,
    )

    stages = {event["stage"] for event in events}

    assert "optimizer_context_started" in stages
    assert "optimizer_context_ready" in stages
    assert "nsga2_started" in stages
    assert "nsga2_completed" in stages
    assert "optimizer_completed" in stages


def test_optimizer_ignores_progress_callback_errors(sample_parcels):
    """
    A broken progress callback should not break optimization.

    This protects the backend from failing just because progress reporting
    has an issue.
    """

    def broken_callback(_event):
        raise RuntimeError("frontend progress listener failed")

    optimizer = SpatialOptimizer(
        config=SpatialConfig(
            land_use_labels=LAND_USES,
            nsga2=NSGA2Config(
                population_size=8,
                generations=2,
                num_output_plans=1,
                random_seed=1,
            ),
        )
    )

    result = optimizer.optimize(
        parcels=sample_parcels,
        progress_callback=broken_callback,
        progress_every_generations=1,
    )

    assert len(result.plans) == 1


def test_optimizer_rejects_empty_objective_list():
    """
    The optimizer cannot work without at least one objective function.

    This test makes that failure explicit.
    """
    with pytest.raises(ValueError, match="at least one objective"):
        SpatialOptimizer(objective_functions=[])