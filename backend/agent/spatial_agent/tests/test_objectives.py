from __future__ import annotations

import unittest

from ._helpers import BACKEND_DIR, make_sample_context  # noqa: F401

from agent.spatial_agent.spatial.objectives import (
    environmental_risk_exposure,
    fragmentation_penalty,
    make_green_area_deviation,
    make_land_use_balance_penalty,
    zoning_violation_penalty,
)

mean_suitability_loss = make_green_area_deviation(0.30)


class TestObjectives(unittest.TestCase):
    def setUp(self) -> None:
        self.context = make_sample_context()
        self.chromosome = (0, 3, 1)  # residential, green, commercial

    def test_mean_suitability_loss(self) -> None:
        # Green area ratio is 110/300 = 0.36666..., target is 0.3.
        value = mean_suitability_loss(self.chromosome, self.context)
        self.assertAlmostEqual(value, (110.0 / 300.0) - 0.3, places=6)

    def test_zoning_violation_penalty(self) -> None:
        valid = zoning_violation_penalty(self.chromosome, self.context)
        self.assertEqual(valid, 0.0)

        invalid = zoning_violation_penalty((2, 0, 1), self.context)
        self.assertAlmostEqual(invalid, 2.0, places=6)

    def test_land_use_balance_penalty_factory(self) -> None:
        objective = make_land_use_balance_penalty(
            {"residential": 0.5, "green": 0.5}
        )
        value = objective(self.chromosome, self.context)
        self.assertAlmostEqual(value, 2.0 / 3.0, places=6)


if __name__ == "__main__":
    unittest.main()
