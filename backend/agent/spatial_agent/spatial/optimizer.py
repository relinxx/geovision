"""High-level optimizer facade for the Spatial Agent MVP."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import logging
import time
from typing import Any

from .config import SpatialConfig
from .nsga2 import NSGA2
from .objectives import default_objectives
from .types import (
    AdjacencyMap,
    Individual,
    ObjectiveFunction,
    OptimizationContext,
    OptimizationPlan,
    OptimizationResult,
    ParcelAssignment,
    ParcelRecord,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SpatialOptimizer:
    """Coordinator that prepares context, runs NSGA-II, and decodes plans."""

    config: SpatialConfig = field(default_factory=SpatialConfig)
    objective_functions: Iterable[ObjectiveFunction] = field(default_factory=default_objectives)

    def __post_init__(self) -> None:
        self.objective_functions = tuple(self.objective_functions)
        if not self.objective_functions:
            raise ValueError("SpatialOptimizer requires at least one objective function")
        logger.debug(
            "SpatialOptimizer initialized | objective_count=%d | land_use_labels=%s | nsga2=%s",
            len(self.objective_functions),
            self.config.land_use_labels,
            self.config.nsga2,
        )

    def optimize(
        self,
        parcels: Sequence[ParcelRecord],
        adjacency: Mapping[int, Sequence[int]] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        progress_every_generations: int = 10,
    ) -> OptimizationResult:
        """Optimize over typed parcel records and return top Pareto plans."""
        started_at = time.perf_counter()
        logger.debug(
            "Optimization started | parcel_count=%d | incoming_adjacency_size=%d | progress_every_generations=%d",
            len(parcels),
            len(adjacency or {}),
            progress_every_generations,
        )
        self._notify_progress(
            progress_callback,
            {
                "stage": "optimizer_context_started",
                "parcel_count": len(parcels),
                "elapsed_seconds": 0.0,
            },
        )

        context = OptimizationContext(
            parcels=tuple(parcels),
            land_use_labels=self.config.land_use_labels,
            adjacency=self._coerce_adjacency(adjacency),
        )
        adjacency_edge_count = sum(len(neighbors) for neighbors in context.adjacency.values()) // 2
        logger.debug(
            "Optimization context ready | parcel_count=%d | land_use_labels=%s | adjacency_nodes=%d | adjacency_edges=%d",
            len(context.parcels),
            context.land_use_labels,
            len(context.adjacency),
            adjacency_edge_count,
        )
        self._notify_progress(
            progress_callback,
            {
                "stage": "optimizer_context_ready",
                "parcel_count": len(context.parcels),
                "elapsed_seconds": time.perf_counter() - started_at,
            },
        )

        engine = NSGA2(
            config=self.config.nsga2,
            context=context,
            objectives=self.objective_functions,
            progress_callback=progress_callback,
            progress_every_generations=progress_every_generations,
        )
        logger.debug(
            "NSGA2 engine created | population_size=%d | generations=%d | mutation_rate=%.4f | crossover_rate=%.4f",
            self.config.nsga2.population_size,
            self.config.nsga2.generations,
            self.config.nsga2.mutation_rate,
            self.config.nsga2.crossover_rate,
        )
        population = engine.evolve()
        logger.debug("NSGA2 evolve completed | final_population=%d", len(population))

        pareto_front = [candidate for candidate in population if candidate.rank == 0]
        if not pareto_front:
            pareto_front = population
        logger.debug(
            "Pareto selection complete | pareto_count=%d | population_count=%d",
            len(pareto_front),
            len(population),
        )

        ordered = sorted(
            pareto_front,
            key=lambda candidate: candidate.crowding_distance,
            reverse=True,
        )
        selected = ordered[: self.config.nsga2.num_output_plans]
        logger.debug(
            "Plan candidates selected | requested=%d | selected=%d",
            self.config.nsga2.num_output_plans,
            len(selected),
        )

        plans = tuple(self._decode_plan(candidate, context) for candidate in selected)
        objective_names = tuple(
            self._objective_name(function, idx)
            for idx, function in enumerate(self.objective_functions)
        )
        logger.debug("Plans decoded | count=%d | objective_names=%s", len(plans), objective_names)

        self._notify_progress(
            progress_callback,
            {
                "stage": "optimizer_completed",
                "parcel_count": len(context.parcels),
                "plan_count": len(plans),
                "elapsed_seconds": time.perf_counter() - started_at,
            },
        )
        logger.debug(
            "Optimization completed | plan_count=%d | total_elapsed_seconds=%.4f",
            len(plans),
            time.perf_counter() - started_at,
        )

        return OptimizationResult(
            plans=plans,
            objective_names=objective_names,
            generations=self.config.nsga2.generations,
            population_size=self.config.nsga2.population_size,
        )

    def optimize_geojson_features(
        self,
        features: Iterable[Mapping[str, Any]],
        include_adjacency: bool = True,
        adjacency_predicate: str = "touches",
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        progress_every_generations: int = 10,
    ) -> OptimizationResult:
        """Optimize directly from GeoJSON parcel features."""
        started_at = time.perf_counter()
        logger.debug(
            "GeoJSON optimization started | include_adjacency=%s | adjacency_predicate=%s",
            include_adjacency,
            adjacency_predicate,
        )
        self._notify_progress(
            progress_callback,
            {
                "stage": "preprocess_started",
                "elapsed_seconds": 0.0,
            },
        )

        feature_list = list(features)
        logger.debug("GeoJSON features loaded | feature_count=%d", len(feature_list))
        self._notify_progress(
            progress_callback,
            {
                "stage": "preprocess_features_loaded",
                "feature_count": len(feature_list),
                "elapsed_seconds": time.perf_counter() - started_at,
            },
        )

        from .geo import build_adjacency_from_geojson, build_parcels_from_geojson

        parcel_started = time.perf_counter()
        parcels = build_parcels_from_geojson(
            feature_list, land_use_labels=self.config.land_use_labels,
        )
        self._notify_progress(progress_callback, {
            "stage": "preprocess_parcels_ready",
            "parcel_count": len(parcels),
            "elapsed_seconds": time.perf_counter() - started_at,
            "parcel_build_seconds": time.perf_counter() - parcel_started,
        })

        adjacency: AdjacencyMap | None = None
        if include_adjacency:
            adjacency_started = time.perf_counter()
            adjacency = build_adjacency_from_geojson(
                feature_list,
                adjacency_predicate=adjacency_predicate,
                progress_callback=progress_callback,
            )
            self._notify_progress(progress_callback, {
                "stage": "preprocess_adjacency_ready",
                "elapsed_seconds": time.perf_counter() - started_at,
                "adjacency_build_seconds": time.perf_counter() - adjacency_started,
            })
        else:
            self._notify_progress(progress_callback, {
                "stage": "preprocess_adjacency_skipped",
                "elapsed_seconds": time.perf_counter() - started_at,
            })

        logger.debug(
            "GeoJSON preprocessing ready | parcel_count=%d | adjacency_nodes=%d",
            len(parcels), len(adjacency or {}),
        )

        return self.optimize(
            parcels=parcels,
            adjacency=adjacency,
            progress_callback=progress_callback,
            progress_every_generations=progress_every_generations,
        )

    def _decode_plan(
        self,
        candidate: Individual,
        context: OptimizationContext,
    ) -> OptimizationPlan:
        assignments = tuple(
            ParcelAssignment(
                parcel_id=parcel.parcel_id,
                use_code=gene,
                use_label=context.land_use_labels[gene],
            )
            for gene, parcel in zip(candidate.chromosome, context.parcels)
        )
        return OptimizationPlan(
            chromosome=candidate.chromosome,
            objectives=candidate.objectives,
            assignments=assignments,
            rank=candidate.rank,
            crowding_distance=candidate.crowding_distance,
        )

    @staticmethod
    def _objective_name(function: ObjectiveFunction, index: int) -> str:
        name = getattr(function, "__name__", "") or f"objective_{index}"
        return str(name)

    @staticmethod
    def _coerce_adjacency(
        adjacency: Mapping[int, Sequence[int]] | None,
    ) -> AdjacencyMap:
        if adjacency is None:
            logger.debug("Adjacency coercion skipped | source=None")
            return {}

        coerced: AdjacencyMap = {}
        skipped_indices = 0
        skipped_neighbors = 0
        for raw_idx, raw_neighbors in adjacency.items():
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                skipped_indices += 1
                continue

            neighbors: set[int] = set()
            for raw_neighbor in raw_neighbors:
                try:
                    neighbor = int(raw_neighbor)
                except (TypeError, ValueError):
                    skipped_neighbors += 1
                    continue
                neighbors.add(neighbor)

            coerced[idx] = tuple(sorted(neighbors))

        logger.debug(
            "Adjacency coercion completed | input_nodes=%d | output_nodes=%d | skipped_indices=%d | skipped_neighbors=%d",
            len(adjacency),
            len(coerced),
            skipped_indices,
            skipped_neighbors,
        )
        return coerced

    @staticmethod
    def _notify_progress(
        progress_callback: Callable[[dict[str, Any]], None] | None,
        event: dict[str, Any],
    ) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(event)
        except Exception:
            logger.debug(
                "Progress callback raised exception and was ignored | event_stage=%s",
                event.get("stage"),
                exc_info=True,
            )
            return
