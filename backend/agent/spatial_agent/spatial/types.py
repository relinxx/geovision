"""Typed datamodels used by the Spatial Agent optimizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, TypeAlias


Chromosome: TypeAlias = tuple[int, ...]
ObjectiveValues: TypeAlias = tuple[float, ...]
AdjacencyMap: TypeAlias = dict[int, tuple[int, ...]]
ObjectiveFunction: TypeAlias = Callable[[Chromosome, "OptimizationContext"], float]


@dataclass(frozen=True, slots=True)
class ParcelRecord:
    """A single parcel with scalar attributes required for optimization."""

    parcel_id: str
    area_m2: float
    centroid_x: float
    centroid_y: float
    risk_score_norm: float = 0.0
    suitability: Mapping[str, float] = field(default_factory=dict)
    allowed_use_codes: tuple[int, ...] = field(default_factory=tuple)
    properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.parcel_id:
            raise ValueError("parcel_id cannot be empty")
        if self.area_m2 < 0.0:
            raise ValueError("area_m2 cannot be negative")

        object.__setattr__(
            self,
            "risk_score_norm",
            min(max(float(self.risk_score_norm), 0.0), 1.0),
        )

        normalized_suitability = {
            str(key).strip().lower(): min(max(float(value), 0.0), 1.0)
            for key, value in self.suitability.items()
        }
        object.__setattr__(self, "suitability", normalized_suitability)

        normalized_codes_set: set[int] = set()
        for code in self.allowed_use_codes:
            try:
                parsed_code = int(code)
            except (TypeError, ValueError):
                continue
            if parsed_code >= 0:
                normalized_codes_set.add(parsed_code)
        normalized_codes = tuple(sorted(normalized_codes_set))
        object.__setattr__(self, "allowed_use_codes", normalized_codes)


@dataclass(frozen=True, slots=True)
class OptimizationContext:
    """Immutable context shared by all objective functions."""

    parcels: tuple[ParcelRecord, ...]
    land_use_labels: tuple[str, ...]
    adjacency: AdjacencyMap = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.parcels:
            raise ValueError("OptimizationContext requires at least one parcel")
        if not self.land_use_labels:
            raise ValueError("OptimizationContext requires land_use_labels")

        normalized_labels = tuple(label.strip().lower() for label in self.land_use_labels)
        if len(set(normalized_labels)) != len(normalized_labels):
            raise ValueError("land_use_labels must be unique")
        object.__setattr__(self, "land_use_labels", normalized_labels)

        parcel_count = len(self.parcels)
        normalized_adjacency: AdjacencyMap = {}
        for raw_idx, neighbors in self.adjacency.items():
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= parcel_count:
                continue

            valid_neighbors: set[int] = set()
            for neighbor in neighbors:
                try:
                    neighbor_idx = int(neighbor)
                except (TypeError, ValueError):
                    continue
                if 0 <= neighbor_idx < parcel_count and neighbor_idx != idx:
                    valid_neighbors.add(neighbor_idx)

            normalized_adjacency[idx] = tuple(sorted(valid_neighbors))

        object.__setattr__(self, "adjacency", normalized_adjacency)

        use_count = len(self.land_use_labels)
        for parcel in self.parcels:
            if parcel.allowed_use_codes and any(
                code >= use_count for code in parcel.allowed_use_codes
            ):
                raise ValueError(
                    "Parcel allowed_use_codes contain invalid land-use code"
                )


@dataclass(slots=True)
class Individual:
    """An evaluated candidate for NSGA-II ranking."""

    chromosome: Chromosome
    objectives: ObjectiveValues = field(default_factory=tuple)
    rank: int = 0
    crowding_distance: float = 0.0


@dataclass(frozen=True, slots=True)
class ParcelAssignment:
    """Decoded per-parcel output assignment."""

    parcel_id: str
    use_code: int
    use_label: str


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    """A single output plan from the Pareto frontier."""

    chromosome: Chromosome
    objectives: ObjectiveValues
    assignments: tuple[ParcelAssignment, ...]
    rank: int
    crowding_distance: float


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Top-level optimization response object."""

    plans: tuple[OptimizationPlan, ...]
    objective_names: tuple[str, ...]
    generations: int
    population_size: int
