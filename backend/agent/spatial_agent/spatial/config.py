"""Configuration models for Spatial Agent NSGA-II optimization."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_LAND_USE_LABELS: tuple[str, ...] = (
    "residential",
    "commercial",
    "industrial",
    "green",
)


@dataclass(frozen=True, slots=True)
class NSGA2Config:
    """Tunable parameters for the NSGA-II search."""

    population_size: int = 80
    generations: int = 100
    crossover_rate: float = 0.9
    mutation_rate: float = 0.05
    tournament_size: int = 2
    random_seed: int | None = 42
    num_output_plans: int = 5

    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size must be >= 2")
        if self.generations < 1:
            raise ValueError("generations must be >= 1")
        if not 0.0 <= self.crossover_rate <= 1.0:
            raise ValueError("crossover_rate must be in [0, 1]")
        if not 0.0 <= self.mutation_rate <= 1.0:
            raise ValueError("mutation_rate must be in [0, 1]")
        if self.tournament_size < 2:
            raise ValueError("tournament_size must be >= 2")
        if self.tournament_size > self.population_size:
            raise ValueError("tournament_size cannot exceed population_size")
        if self.num_output_plans < 1:
            raise ValueError("num_output_plans must be >= 1")


@dataclass(frozen=True, slots=True)
class SpatialConfig:
    """Top-level config for the Spatial Agent optimizer package."""

    land_use_labels: tuple[str, ...] = field(
        default_factory=lambda: DEFAULT_LAND_USE_LABELS
    )
    nsga2: NSGA2Config = field(default_factory=NSGA2Config)

    def __post_init__(self) -> None:
        normalized = tuple(
            label.strip().lower()
            for label in self.land_use_labels
            if label and label.strip()
        )
        if not normalized:
            raise ValueError("land_use_labels cannot be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("land_use_labels must be unique")
        object.__setattr__(self, "land_use_labels", normalized)
