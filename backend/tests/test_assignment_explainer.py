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


class TestAssignmentExplainerRoute(unittest.TestCase):
    def test_spatial_explain_assignment_route_is_registered_and_returns_expected_shape(self) -> None:
        route_paths = {getattr(route, "path", None) for route in app.routes}
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


if __name__ == "__main__":
    unittest.main()

