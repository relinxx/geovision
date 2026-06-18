import unittest
from typing import cast

from main import ExplainAssignmentRequest, app, spatial_explain_assignment
from services.assignment_explainer import explain_assignment


class TestAssignmentExplainer(unittest.TestCase):
    def test_green_assignment_with_high_risk_and_hazards(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "12345",
                "residential": 0.22,
                "commercial": 0.18,
                "industrial": 0.11,
                "green": 0.83,
                "environmental_risk": 0.78,
                "has_flood": 1,
                "is_fire_zone": 1,
                "in_esa": 1,
                "ZONING_CODE": "Open Space",
            },
            assigned_use="green",
            target_mix={
                "residential": 0.35,
                "commercial": 0.20,
                "industrial": 0.15,
                "green": 0.30,
            },
        )

        self.assertEqual(result["assigned_use"], "green")
        self.assertEqual(result["best_suitability_use"], "green")
        self.assertEqual(result["risk_level"], "high")
        self.assertGreaterEqual(len(result["reasons"]), 4)
        self.assertIn("green", result["scores"]["allowed_uses"])
        self.assertAlmostEqual(result["scores"]["assigned_use_score"], 0.83)
        self.assertAlmostEqual(result["scores"]["environmental_risk"], 0.78)

    def test_built_use_with_low_risk_gets_positive_feasibility_reason(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "20001",
                "residential": 0.81,
                "commercial": 0.55,
                "industrial": 0.21,
                "green": 0.18,
                "environmental_risk": 0.12,
                "ZONING_CODE": "RS-1-7",
            },
            assigned_use="residential",
            target_mix={"residential": 0.4},
        )

        joined_reasons = " ".join(result["reasons"]).lower()
        self.assertEqual(result["best_suitability_use"], "residential")
        self.assertEqual(result["risk_level"], "low")
        self.assertIn("environmental risk is low", joined_reasons)
        self.assertIn("residential", result["scores"]["allowed_uses"])
        self.assertEqual(result["warnings"], [])

    def test_high_risk_built_use_creates_warning(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "20002",
                "residential": 0.48,
                "commercial": 0.42,
                "industrial": 0.66,
                "green": 0.61,
                "environmental_risk": 0.84,
                "has_flood": 1,
                "has_fault": 1,
            },
            assigned_use="industrial",
            target_mix={"industrial": 0.25},
        )

        joined_warnings = " ".join(result["warnings"]).lower()
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("environmental risk", joined_warnings)
        self.assertGreaterEqual(len(result["warnings"]), 1)

    def test_warns_when_another_use_is_much_higher(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "20003",
                "residential": 0.20,
                "commercial": 0.15,
                "industrial": 0.10,
                "green": 0.82,
                "environmental_risk": 0.40,
            },
            assigned_use="residential",
            target_mix={"residential": 0.35},
        )

        joined_warnings = " ".join(result["warnings"]).lower()
        self.assertEqual(result["best_suitability_use"], "green")
        self.assertIn("much higher suitability score", joined_warnings)

    def test_uses_xgb_risk_score_when_normalized_risk_missing(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "20004",
                "residential": 0.41,
                "commercial": 0.44,
                "industrial": 0.46,
                "green": 0.51,
                "xgb_risk_score": 82,
            },
            assigned_use="green",
            target_mix={},
        )

        self.assertAlmostEqual(result["scores"]["environmental_risk"], 0.82)
        self.assertEqual(result["risk_level"], "high")

    def test_handles_missing_scores_and_unknown_zoning_safely(self) -> None:
        result = explain_assignment(
            parcel_properties={"APN": "20005"},
            assigned_use="commercial",
            target_mix={},
        )

        self.assertEqual(result["assigned_use"], "commercial")
        self.assertEqual(result["scores"]["allowed_uses"], [])
        self.assertIsNone(result["scores"]["environmental_risk"])
        self.assertIn("commercial", result["scores"]["suitability"])

    def test_warns_when_zoning_does_not_clearly_allow_assigned_use(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "20006",
                "residential": 0.18,
                "commercial": 0.32,
                "industrial": 0.71,
                "green": 0.24,
                "ZONING_CODE": "RS-1-7",
            },
            assigned_use="industrial",
            target_mix={"industrial": 0.20},
        )

        joined_warnings = " ".join(result["warnings"]).lower()
        self.assertIn("does not clearly allow industrial", joined_warnings)


class TestAssignmentExplainerRoute(unittest.TestCase):
    def test_spatial_explain_assignment_route_is_registered_and_returns_expected_shape(self) -> None:
        route_paths = {getattr(route, "path", None) for route in app.routes}
        self.assertIn("/spatial/explain-assignment", route_paths)
        self.assertIn("/api/spatial/explain-assignment", route_paths)

        payload = spatial_explain_assignment(
            ExplainAssignmentRequest(
                parcel_id="12345",
                assigned_use=cast(str, "green"),
                target_mix={
                    "residential": 0.35,
                    "commercial": 0.2,
                    "industrial": 0.15,
                    "green": 0.3,
                },
                parcel_properties={
                    "APN": "12345",
                    "residential": 0.22,
                    "commercial": 0.18,
                    "industrial": 0.11,
                    "green": 0.83,
                    "environmental_risk": 0.78,
                    "has_flood": 1,
                    "is_fire_zone": 1,
                    "in_esa": 1,
                    "ZONING_CODE": "Open Space",
                },
            )
        )

        self.assertEqual(payload["parcel_id"], "12345")
        self.assertEqual(payload["assigned_use"], "green")
        self.assertIn("headline", payload)
        self.assertIn("reasons", payload)
        self.assertIn("warnings", payload)
        self.assertIn("scores", payload)

    def test_low_score_assignment_is_explained_as_tradeoff_not_close_match(self) -> None:
        result = explain_assignment(
            parcel_properties={
                "APN": "3351200300",
                "residential": 0.72,
                "commercial": 0.0,
                "industrial": 0.15,
                "green": 0.35,
                "environmental_risk": 0.20,
                "is_steep": 1,
                "in_esa": 1,
            },
            assigned_use="commercial",
            target_mix={
                "residential": 0.35,
                "commercial": 0.25,
                "industrial": 0.10,
                "green": 0.30,
            },
        )

        joined_reasons = " ".join(result["reasons"]).lower()
        joined_warnings = " ".join(result["warnings"]).lower()

        self.assertEqual(result["assigned_use"], "commercial")
        self.assertEqual(result["best_suitability_use"], "residential")
        self.assertAlmostEqual(result["scores"]["assigned_use_score"], 0.0)
        self.assertAlmostEqual(result["scores"]["environmental_risk"], 0.20)

        self.assertIn("plan-level land-use mix", joined_reasons)
        self.assertIn("trade-off", joined_warnings)
        self.assertIn("residential is the stronger option", joined_warnings)

        # Most important: it should NOT falsely claim commercial is close to best.
        self.assertNotIn("close to the best suitability option", joined_reasons)    


if __name__ == "__main__":
    unittest.main()

    def test_spatial_explain_assignment_includes_neighbour_context_when_supplied(self) -> None:
        def feature(parcel_id: str, lon: float, lat: float, risk: float) -> dict:
            delta = 0.0001
            return {
                "type": "Feature",
                "id": parcel_id,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [lon - delta, lat - delta],
                            [lon + delta, lat - delta],
                            [lon + delta, lat + delta],
                            [lon - delta, lat + delta],
                            [lon - delta, lat - delta],
                        ]
                    ],
                },
                "properties": {
                    "APN": parcel_id,
                    "centroid": {"x": lon, "y": lat},
                    "environmental_risk": risk,
                    "residential": 0.8 if parcel_id == "parcel-2" else 0.2,
                    "commercial": 0.2,
                    "industrial": 0.7 if parcel_id == "parcel-1" else 0.1,
                    "green": 0.2,
                },
            }

        payload = spatial_explain_assignment(
            ExplainAssignmentRequest(
                parcel_id="parcel-1",
                assigned_use=cast(str, "industrial"),
                target_mix={"industrial": 0.2, "residential": 0.8},
                parcel_properties={
                    "APN": "parcel-1",
                    "residential": 0.2,
                    "commercial": 0.2,
                    "industrial": 0.7,
                    "green": 0.2,
                    "environmental_risk": 0.2,
                },
                use_spatial_compatibility=True,
                spatial_neighbor_radius_m=250,
                plan_assignments=[
                    {"parcel_id": "parcel-1", "use_label": "industrial"},
                    {"parcel_id": "parcel-2", "use_label": "residential"},
                ],
                plan_parcels=[
                    feature("parcel-1", -117.0, 32.0, 0.2),
                    feature("parcel-2", -117.0005, 32.0, 0.2),
                ],
            )
        )

        self.assertIsNotNone(payload["spatial_context"])
        self.assertEqual(payload["spatial_context"]["neighbor_pairs_evaluated"], 1)
        self.assertEqual(payload["spatial_context"]["industrial_residential_conflicts"], 1)
        joined_warnings = " ".join(payload["warnings"]).lower()
        self.assertIn("industrial-residential proximity", joined_warnings)

