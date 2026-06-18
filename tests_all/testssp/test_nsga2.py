from __future__ import annotations

import math
import unittest

from ._helpers import BACKEND_DIR  # noqa: F401

from agent.spatial_agent.spatial.config import NSGA2Config
from agent.spatial_agent.spatial.nsga2 import NSGA2
from agent.spatial_agent.spatial.types import OptimizationContext, ParcelRecord


def objective_sum(chromosome, _context) -> float:
    return float(sum(chromosome))


def objective_switches(chromosome, _context) -> float:
    return float(
        sum(
            1
            for index in range(1, len(chromosome))
            if chromosome[index] != chromosome[index - 1]
        )
    )


class TestNSGA2(unittest.TestCase):
    def test_evolve_returns_valid_population(self) -> None:
        context = OptimizationContext(
            parcels=(
                ParcelRecord(
                    parcel_id="p1",
                    area_m2=1.0,
                    centroid_x=0.0,
                    centroid_y=0.0,
                    allowed_use_codes=(0,),
                ),
                ParcelRecord(
                    parcel_id="p2",
                    area_m2=1.0,
                    centroid_x=1.0,
                    centroid_y=0.0,
                    allowed_use_codes=(1, 2),
                ),
                ParcelRecord(
                    parcel_id="p3",
                    area_m2=1.0,
                    centroid_x=2.0,
                    centroid_y=0.0,
                    allowed_use_codes=(0, 1, 2, 3),
                ),
                ParcelRecord(
                    parcel_id="p4",
                    area_m2=1.0,
                    centroid_x=3.0,
                    centroid_y=0.0,
                    allowed_use_codes=(3,),
                ),
            ),
            land_use_labels=("residential", "commercial", "industrial", "green"),
        )

        config = NSGA2Config(
            population_size=20,
            generations=8,
            mutation_rate=0.7,
            crossover_rate=0.9,
            random_seed=7,
        )
        engine = NSGA2(config, context, objectives=[objective_sum, objective_switches])
        population = engine.evolve()

        self.assertEqual(len(population), config.population_size)
        self.assertTrue(any(ind.rank == 0 for ind in population))
        for individual in population:
            self.assertEqual(len(individual.objectives), 2)
            self.assertFalse(math.isnan(individual.objectives[0]))
            self.assertFalse(math.isnan(individual.objectives[1]))
            for gene_index, gene in enumerate(individual.chromosome):
                self.assertIn(gene, context.parcels[gene_index].allowed_use_codes)


if __name__ == "__main__":
    unittest.main()
