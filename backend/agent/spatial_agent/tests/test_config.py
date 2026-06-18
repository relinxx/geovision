from __future__ import annotations

import unittest

from ._helpers import BACKEND_DIR  # noqa: F401

from agent.spatial_agent.spatial.config import NSGA2Config, SpatialConfig


class TestNSGA2Config(unittest.TestCase):
    def test_defaults_are_valid(self) -> None:
        cfg = NSGA2Config()
        self.assertGreaterEqual(cfg.population_size, 2)
        self.assertGreaterEqual(cfg.generations, 1)
        self.assertGreaterEqual(cfg.num_output_plans, 1)

    def test_invalid_population_raises(self) -> None:
        with self.assertRaises(ValueError):
            NSGA2Config(population_size=1)

    def test_invalid_rates_raise(self) -> None:
        with self.assertRaises(ValueError):
            NSGA2Config(crossover_rate=1.1)
        with self.assertRaises(ValueError):
            NSGA2Config(mutation_rate=-0.01)


class TestSpatialConfig(unittest.TestCase):
    def test_land_use_labels_are_normalized(self) -> None:
        cfg = SpatialConfig(land_use_labels=(" Residential ", "COMMERCIAL"))
        self.assertEqual(cfg.land_use_labels, ("residential", "commercial"))

    def test_duplicate_labels_raise(self) -> None:
        with self.assertRaises(ValueError):
            SpatialConfig(land_use_labels=("residential", "Residential"))


if __name__ == "__main__":
    unittest.main()
