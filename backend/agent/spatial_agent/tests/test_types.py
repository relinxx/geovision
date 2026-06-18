from __future__ import annotations

import unittest

from ._helpers import BACKEND_DIR, make_sample_parcels  # noqa: F401

from agent.spatial_agent.spatial.types import OptimizationContext, ParcelRecord


class TestParcelRecord(unittest.TestCase):
    def test_normalization_and_clamping(self) -> None:
        parcel = ParcelRecord(
            parcel_id="x1",
            area_m2=10.0,
            centroid_x=0.0,
            centroid_y=0.0,
            risk_score_norm=2.3,
            suitability={"residential": 1.5, "commercial": -0.2},
            allowed_use_codes=("1", "x", -1, 2),
        )
        self.assertEqual(parcel.risk_score_norm, 1.0)
        self.assertEqual(parcel.suitability["residential"], 1.0)
        self.assertEqual(parcel.suitability["commercial"], 0.0)
        self.assertEqual(parcel.allowed_use_codes, (1, 2))

    def test_empty_parcel_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            ParcelRecord(
                parcel_id="",
                area_m2=10.0,
                centroid_x=0.0,
                centroid_y=0.0,
            )


class TestOptimizationContext(unittest.TestCase):
    def test_adjacency_is_normalized(self) -> None:
        parcels = make_sample_parcels()
        context = OptimizationContext(
            parcels=parcels,
            land_use_labels=("residential", "commercial", "industrial", "green"),
            adjacency={
                0: (1, 99, "2"),
                "bad": (0,),
                2: (2, 0),
            },
        )
        self.assertEqual(context.adjacency[0], (1, 2))
        self.assertEqual(context.adjacency[2], (0,))
        self.assertNotIn("bad", context.adjacency)

    def test_invalid_allowed_code_raises(self) -> None:
        bad = (
            ParcelRecord(
                parcel_id="p",
                area_m2=1.0,
                centroid_x=0.0,
                centroid_y=0.0,
                allowed_use_codes=(5,),
            ),
        )
        with self.assertRaises(ValueError):
            OptimizationContext(
                parcels=bad,
                land_use_labels=("residential", "commercial"),
            )


if __name__ == "__main__":
    unittest.main()
