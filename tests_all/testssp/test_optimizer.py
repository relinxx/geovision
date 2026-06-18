from __future__ import annotations

import importlib.util
import unittest

from ._helpers import BACKEND_DIR, make_sample_parcels  # noqa: F401

from agent.spatial_agent.spatial.config import NSGA2Config, SpatialConfig
from agent.spatial_agent.spatial.objectives import (
    make_green_area_deviation,
    zoning_violation_penalty,
)

mean_suitability_loss = make_green_area_deviation(0.30)
from agent.spatial_agent.spatial.optimizer import SpatialOptimizer


class TestOptimizer(unittest.TestCase):
    def test_optimize_returns_decoded_plans(self) -> None:
        optimizer = SpatialOptimizer(
            config=SpatialConfig(
                nsga2=NSGA2Config(
                    population_size=24,
                    generations=8,
                    num_output_plans=3,
                    random_seed=11,
                )
            ),
            objective_functions=[zoning_violation_penalty, mean_suitability_loss],
        )

        result = optimizer.optimize(parcels=make_sample_parcels())

        self.assertLessEqual(len(result.plans), 3)
        self.assertEqual(
            result.objective_names,
            ("zoning_violation_penalty", "mean_suitability_loss"),
        )
        self.assertGreater(len(result.plans), 0)
        for plan in result.plans:
            self.assertEqual(len(plan.assignments), 3)
            for assignment in plan.assignments:
                self.assertIsInstance(assignment.use_code, int)
                self.assertIn(assignment.use_label, optimizer.config.land_use_labels)

    @unittest.skipUnless(
        importlib.util.find_spec("shapely") is not None,
        "requires shapely",
    )
    def test_optimize_geojson_features(self) -> None:
        optimizer = SpatialOptimizer(
            config=SpatialConfig(
                nsga2=NSGA2Config(
                    population_size=16,
                    generations=4,
                    num_output_plans=2,
                    random_seed=3,
                )
            )
        )

        features = [
            {
                "type": "Feature",
                "id": "p1",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
                "properties": {
                    "environmental_risk": 0.2,
                    "suitability_residential": 0.8,
                    "suitability_commercial": 0.4,
                    "suitability_industrial": 0.2,
                    "suitability_green": 0.5,
                    "ZONING_CODE": "RS",
                },
            },
            {
                "type": "Feature",
                "id": "p2",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
                "properties": {
                    "environmental_risk": 0.7,
                    "suitability_residential": 0.1,
                    "suitability_commercial": 0.5,
                    "suitability_industrial": 0.8,
                    "suitability_green": 0.9,
                    "GP_LAND_USE": "Open Space",
                },
            },
        ]

        result = optimizer.optimize_geojson_features(features)
        self.assertGreater(len(result.plans), 0)
        self.assertLessEqual(len(result.plans), 2)

    def test_optimize_geojson_features_fallback_without_geometry(self) -> None:
        optimizer = SpatialOptimizer(
            config=SpatialConfig(
                nsga2=NSGA2Config(
                    population_size=16,
                    generations=4,
                    num_output_plans=2,
                    random_seed=3,
                )
            )
        )

        features = [
            {
                "type": "Feature",
                "id": "p1",
                "properties": {
                    "environmental_risk": 0.2,
                    "suitability_residential": 0.8,
                    "suitability_commercial": 0.4,
                    "suitability_industrial": 0.2,
                    "suitability_green": 0.5,
                    "allowed_uses": ["residential", "commercial"],
                },
            },
            {
                "type": "Feature",
                "id": "p2",
                "properties": {
                    "environmental_risk": 0.7,
                    "suitability_residential": 0.1,
                    "suitability_commercial": 0.5,
                    "suitability_industrial": 0.8,
                    "suitability_green": 0.9,
                    "allowed_uses": "industrial,green",
                },
            },
        ]

        result = optimizer.optimize_geojson_features(features, include_adjacency=True)
        self.assertGreater(len(result.plans), 0)
        self.assertLessEqual(len(result.plans), 2)
        self.assertEqual(len(result.objective_names), 4)


if __name__ == "__main__":
    unittest.main()
