"""NSGA-II engine for integer-encoded land-use optimization."""

from __future__ import annotations

import logging
import math
import random
import time
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np

from .config import NSGA2Config
from .types import Chromosome, Individual, ObjectiveFunction, OptimizationContext

logger = logging.getLogger(__name__)


class NSGA2:
    """Minimal, typed NSGA-II implementation for integer chromosome search."""

    def __init__(
        self,
        config: NSGA2Config,
        context: OptimizationContext,
        objectives: Iterable[ObjectiveFunction],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        progress_every_generations: int = 10,
    ) -> None:
        self.config    = config
        self.context   = context
        self.objectives = tuple(objectives)
        if not self.objectives:
            raise ValueError("At least one objective function is required")

        self._progress_callback        = progress_callback
        self._progress_every_generations = max(1, int(progress_every_generations))
        self._rng        = random.Random(self.config.random_seed)
        self._use_count  = len(self.context.land_use_labels)

        # Per-instance log counter — avoids shared global state across concurrent requests
        self._objective_log_counts: dict[str, int] = {}

        default_allowed = tuple(range(self._use_count))
        self._allowed_codes_by_gene: tuple[tuple[int, ...], ...] = tuple(
            parcel.allowed_use_codes or default_allowed
            for parcel in self.context.parcels
        )
        self._last_offspring_stats: dict[str, int] = {}
        self._last_survivor_stats: dict[str, Any]  = {}

        logger.debug(
            "NSGA2 initialized | parcels=%d | use_count=%d | objective_count=%d | population_size=%d | generations=%d | seed=%s",
            len(self.context.parcels), self._use_count, len(self.objectives),
            self.config.population_size, self.config.generations, self.config.random_seed,
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def evolve(self) -> list[Individual]:
        """Run NSGA-II and return the final ranked population."""
        started_at = time.perf_counter()
        self._emit_progress({
            "stage": "nsga2_started", "generation": 0,
            "total_generations": self.config.generations,
            "elapsed_seconds": 0.0, "population_size": self.config.population_size,
        })

        population = self._initialize_population()
        self._evaluate_population(population)
        self._rank_population(population)

        self._emit_progress({
            "stage": "nsga2_initialized", "generation": 0,
            "total_generations": self.config.generations,
            "elapsed_seconds": time.perf_counter() - started_at,
            "population_size": len(population),
        })

        for generation_index in range(self.config.generations):
            generation = generation_index + 1
            offspring  = self._create_offspring(population)
            self._evaluate_population(offspring)
            population = self._select_survivors(population + offspring)

            if (
                generation == 1
                or generation == self.config.generations
                or generation % self._progress_every_generations == 0
            ):
                self._emit_progress({
                    "stage": "nsga2_generation",
                    "generation": generation,
                    "total_generations": self.config.generations,
                    "progress_ratio": generation / float(self.config.generations),
                    "elapsed_seconds": time.perf_counter() - started_at,
                })

        self._rank_population(population)
        self._emit_progress({
            "stage": "nsga2_completed",
            "generation": self.config.generations,
            "total_generations": self.config.generations,
            "elapsed_seconds": time.perf_counter() - started_at,
            "population_size": len(population),
        })
        return self._sort_population(population)

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def _emit_progress(self, event: dict[str, Any]) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(event)
        except Exception:
            logger.debug("Progress callback failed | stage=%s", event.get("stage"), exc_info=True)

    # ------------------------------------------------------------------
    # Population initialisation & evaluation
    # ------------------------------------------------------------------

    def _initialize_population(self) -> list[Individual]:
        return [Individual(chromosome=self._random_chromosome())
                for _ in range(self.config.population_size)]

    def _random_chromosome(self) -> Chromosome:
        return tuple(self._rng.choice(allowed) for allowed in self._allowed_codes_by_gene)

    def _evaluate_population(self, population: list[Individual]) -> None:
        for index, individual in enumerate(population):
            values: list[float] = []
            for objective in self.objectives:
                try:
                    values.append(float(objective(individual.chromosome, self.context)))
                except Exception:
                    logger.exception(
                        "Objective evaluation failed | objective=%s | individual_index=%d",
                        getattr(objective, "__name__", str(objective)), index,
                    )
                    raise
            individual.objectives = tuple(values)

    # ------------------------------------------------------------------
    # Non-dominated sort — fully vectorized with NumPy
    # ------------------------------------------------------------------

    def _rank_population(self, population: list[Individual]) -> list[list[Individual]]:
        fronts = self._fast_non_dominated_sort(population)
        for rank, front in enumerate(fronts):
            for ind in front:
                ind.rank = rank
            self._assign_crowding_distance(front)
        return fronts

    def _fast_non_dominated_sort(self, population: list[Individual]) -> list[list[Individual]]:
        """
        Non-dominated sort using vectorized NumPy operations.

        Replaces the original O(n²) Python nested-loop implementation.

        Approach:
          1. Build objective matrix  obj  of shape (n, m).
          2. Compute dominates_mat[i, j] = True iff i dominates j,
             using two broadcast comparisons over the full matrix — no Python loops.
          3. dominated_count[j] = how many individuals dominate j (column sums).
          4. Extract fronts iteratively: individuals with dominated_count == 0
             form the current front; then decrement counts for what that front
             dominated, repeat.

        Memory: (n, n, m) bool array during broadcast — for n=100, m=4 that is
        40 000 bools ≈ 40 KB.  Perfectly fine for typical population sizes.
        """
        n = len(population)
        if n == 0:
            return []
        if n == 1:
            return [population[:]]

        # --- build objective matrix ---
        obj = np.array([ind.objectives for ind in population], dtype=np.float64)  # (n, m)

        # --- vectorized pairwise dominance ---
        # obj[:, None, :] → (n, 1, m)  broadcast against  obj[None, :, :] → (1, n, m)
        # no_worse[i, j, k]       = obj[i][k] <= obj[j][k]
        # strictly_better[i, j, k] = obj[i][k] <  obj[j][k]
        no_worse        = (obj[:, None, :] <= obj[None, :, :]).all(axis=2)   # (n, n)
        strictly_better = (obj[:, None, :] <  obj[None, :, :]).any(axis=2)  # (n, n)
        dominates_mat   = no_worse & strictly_better                          # (n, n)
        np.fill_diagonal(dominates_mat, False)

        # dominated_count[j] = how many individuals dominate j
        dominated_count = dominates_mat.sum(axis=0).astype(np.int32)  # (n,)

        fronts: list[list[Individual]] = []
        remaining = np.ones(n, dtype=bool)

        while remaining.any():
            front_mask = (dominated_count == 0) & remaining
            if not front_mask.any():
                # Numerical tie-break: add remaining as a final degenerate front
                fronts.append([population[i] for i in np.where(remaining)[0]])
                break

            front_idx = np.where(front_mask)[0]
            fronts.append([population[i] for i in front_idx])
            remaining[front_idx] = False

            # Decrement: for each j still remaining, subtract how many front
            # members dominate it.  dominates_mat[front_idx, :] is (|front|, n).
            dominated_count -= dominates_mat[front_idx, :].sum(axis=0)
            # Sentinel: prevent extracted individuals from re-entering a front
            dominated_count[front_idx] = n + 1

        logger.debug(
            "Non-dominated sort completed | front_count=%d | front_sizes=%s",
            len(fronts), tuple(len(f) for f in fronts),
        )
        return fronts

    @staticmethod
    def _dominates(left: Individual, right: Individual) -> bool:
        """Kept for potential external use; internal sort is now vectorized."""
        no_worse        = all(lv <= rv for lv, rv in zip(left.objectives, right.objectives))
        strictly_better = any(lv <  rv for lv, rv in zip(left.objectives, right.objectives))
        return no_worse and strictly_better

    def _assign_crowding_distance(self, front: list[Individual]) -> None:
        if not front:
            return
        for ind in front:
            ind.crowding_distance = 0.0
        if len(front) <= 2:
            for ind in front:
                ind.crowding_distance = math.inf
            return

        obj_count = len(front[0].objectives)
        for obj_idx in range(obj_count):
            front.sort(key=lambda c: c.objectives[obj_idx])
            front[0].crowding_distance  = math.inf
            front[-1].crowding_distance = math.inf
            min_val = front[0].objectives[obj_idx]
            max_val = front[-1].objectives[obj_idx]
            span = max_val - min_val
            if span == 0.0:
                continue
            for k in range(1, len(front) - 1):
                if math.isinf(front[k].crowding_distance):
                    continue
                front[k].crowding_distance += (
                    front[k + 1].objectives[obj_idx] - front[k - 1].objectives[obj_idx]
                ) / span

    # ------------------------------------------------------------------
    # Offspring creation
    # ------------------------------------------------------------------

    def _create_offspring(self, population: list[Individual]) -> list[Individual]:
        offspring: list[Individual] = []
        crossover_events = mutation_changes = repair_changes = mating_rounds = 0

        while len(offspring) < self.config.population_size:
            mating_rounds += 1
            pa = self._tournament_select(population)
            pb = self._tournament_select(population)

            ca, cb = self._crossover(pa.chromosome, pb.chromosome)
            if ca != pa.chromosome or cb != pb.chromosome:
                crossover_events += 1

            ma, mb = self._mutate(ca), self._mutate(cb)
            mutation_changes += self._count_gene_changes(ca, ma) + self._count_gene_changes(cb, mb)

            ra, rb = self._repair_chromosome(ma), self._repair_chromosome(mb)
            repair_changes += self._count_gene_changes(ma, ra) + self._count_gene_changes(mb, rb)

            offspring.append(Individual(chromosome=ra))
            if len(offspring) < self.config.population_size:
                offspring.append(Individual(chromosome=rb))

        self._last_offspring_stats = {
            "offspring_size": len(offspring), "mating_rounds": mating_rounds,
            "crossover_events": crossover_events, "mutation_gene_changes": mutation_changes,
            "repair_gene_changes": repair_changes,
        }
        return offspring

    def _tournament_select(self, population: list[Individual]) -> Individual:
        participants = [self._rng.choice(population) for _ in range(self.config.tournament_size)]
        winner = participants[0]
        for contender in participants[1:]:
            winner = self._better_individual(winner, contender)
        return winner

    def _better_individual(self, left: Individual, right: Individual) -> Individual:
        if left.rank != right.rank:
            return left if left.rank < right.rank else right
        if left.crowding_distance != right.crowding_distance:
            return left if left.crowding_distance > right.crowding_distance else right
        return left if self._rng.random() < 0.5 else right

    def _crossover(self, left: Chromosome, right: Chromosome) -> tuple[Chromosome, Chromosome]:
        if len(left) < 2 or self._rng.random() > self.config.crossover_rate:
            return left, right
        split   = self._rng.randint(1, len(left) - 1)
        child_a = left[:split]  + right[split:]
        child_b = right[:split] + left[split:]
        return child_a, child_b

    def _mutate(self, chromosome: Chromosome) -> Chromosome:
        genes = list(chromosome)
        for gene_idx, current in enumerate(genes):
            if self._rng.random() > self.config.mutation_rate:
                continue
            allowed = self._allowed_codes_by_gene[gene_idx]
            if len(allowed) == 1:
                genes[gene_idx] = allowed[0]
                continue
            candidates = [c for c in allowed if c != current]
            genes[gene_idx] = self._rng.choice(candidates or list(allowed))
        return tuple(genes)

    def _repair_chromosome(self, chromosome: Chromosome) -> Chromosome:
        repaired = list(chromosome)
        for gene_idx, gene in enumerate(chromosome):
            allowed = self._allowed_codes_by_gene[gene_idx]
            if gene not in allowed:
                repaired[gene_idx] = self._rng.choice(allowed)
        return tuple(repaired)

    def _select_survivors(self, combined: list[Individual]) -> list[Individual]:
        fronts    = self._rank_population(combined)
        survivors: list[Individual] = []
        for front in fronts:
            if len(survivors) + len(front) <= self.config.population_size:
                survivors.extend(front)
                continue
            remaining_slots = self.config.population_size - len(survivors)
            survivors.extend(
                sorted(front, key=lambda c: c.crowding_distance, reverse=True)[:remaining_slots]
            )
            break
        self._last_survivor_stats = {
            "combined_population": len(combined),
            "survivor_count": len(survivors),
            "front_count": len(fronts),
            "front_sizes": tuple(len(f) for f in fronts),
        }
        return survivors

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_population(population: list[Individual]) -> list[Individual]:
        return sorted(
            population,
            key=lambda ind: (ind.rank, -ind.crowding_distance, ind.objectives),
        )

    @staticmethod
    def _count_gene_changes(left: Chromosome, right: Chromosome) -> int:
        return sum(1 for l, r in zip(left, right) if l != r)

    @staticmethod
    def _objective_ranges(population: list[Individual]) -> tuple[tuple[float, float], ...]:
        if not population or not population[0].objectives:
            return ()
        n_obj = len(population[0].objectives)
        return tuple(
            (min(ind.objectives[i] for ind in population),
             max(ind.objectives[i] for ind in population))
            for i in range(n_obj)
        )
