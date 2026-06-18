"""Objective functions for NSGA-II land-use optimization."""

from __future__ import annotations

from collections.abc import Mapping
import logging

from .types import Chromosome, ObjectiveFunction, OptimizationContext

logger = logging.getLogger(__name__)

_DEFAULT_GREEN_TARGET  = 0.30
_BUILT_USE_LABELS      = frozenset({"residential", "commercial", "industrial", "mixed"})


# ------------------------------------------------------------------
# Core objectives
# ------------------------------------------------------------------

def zoning_violation_penalty(
    chromosome: Chromosome,
    context: OptimizationContext,
) -> float:
    """Minimize assignment choices that violate parcel-level allowed uses."""
    if not context.parcels:
        return 0.0
    violations = sum(
        1
        for gene, parcel in zip(chromosome, context.parcels)
        if parcel.allowed_use_codes and gene not in parcel.allowed_use_codes
    )
    return float(violations)


def make_green_area_deviation(target_fraction: float = _DEFAULT_GREEN_TARGET) -> ObjectiveFunction:
    """
    Create an objective that penalizes deviation from a target green-area fraction.

    The target is configurable via `target_fraction` (default 0.30 = 30 %).
    Returns a named function so the API `objective_names` field shows a meaningful
    label instead of the generic closure name.

    Replaces the original `mean_suitability_loss` which:
      - used a misleading name (it measured green area, not suitability loss)
      - hardcoded 0.30 at module level with no way to override
      - used a shared global log counter (thread-unsafe across concurrent requests)
    """
    _target = float(target_fraction)

    def green_area_deviation(chromosome: Chromosome, context: OptimizationContext) -> float:
        if not context.parcels:
            return 0.0
        try:
            green_code = context.land_use_labels.index("green")
        except ValueError:
            return 0.0

        total_area = sum(max(p.area_m2, 0.0) for p in context.parcels)
        if total_area <= 0.0:
            return abs(_target)

        green_area = sum(
            max(p.area_m2, 0.0)
            for gene, p in zip(chromosome, context.parcels)
            if gene == green_code
        )
        return abs(green_area / total_area - _target)

    green_area_deviation.__name__ = "green_area_deviation"
    return green_area_deviation


def environmental_risk_exposure(
    chromosome: Chromosome,
    context: OptimizationContext,
) -> float:
    """Area-weighted mean environmental risk across built parcels, normalized to 0–1.

    Returns the fraction of risk-weighted built area relative to the worst case
    (all parcels built at maximum risk). This makes the score comparable to the
    other objectives which are also dimensionless (0–1 range).
    """
    if not context.parcels:
        return 0.0

    built_codes = {
        idx for idx, label in enumerate(context.land_use_labels)
        if label in _BUILT_USE_LABELS
    } or {
        idx for idx, label in enumerate(context.land_use_labels)
        if label != "green"
    }

    total_area = sum(max(p.area_m2, 0.0) for p in context.parcels)
    if total_area <= 0.0:
        return 0.0

    weighted_risk = sum(
        p.risk_score_norm * max(p.area_m2, 0.0)
        for gene, p in zip(chromosome, context.parcels)
        if gene in built_codes
    )
    return weighted_risk / total_area


def fragmentation_penalty(
    chromosome: Chromosome,
    context: OptimizationContext,
) -> float:
    """Fraction of adjacency edges that cross land-use boundaries, normalized 0–1.

    0.0 = perfectly clustered (all neighbors share the same use)
    1.0 = maximally fragmented (every adjacent pair has a different use)
    """
    if not context.adjacency:
        return 0.0
    total_edges = 0
    boundary_changes = 0
    for left_idx, neighbors in context.adjacency.items():
        if not (0 <= left_idx < len(chromosome)):
            continue
        for right_idx in neighbors:
            if right_idx > left_idx and 0 <= right_idx < len(chromosome):
                total_edges += 1
                if chromosome[left_idx] != chromosome[right_idx]:
                    boundary_changes += 1
    if total_edges == 0:
        return 0.0
    return float(boundary_changes) / float(total_edges)


def make_land_use_balance_penalty(target_mix: Mapping[str, float]) -> ObjectiveFunction:
    """Create an objective that penalizes deviation from a desired land-use ratio."""
    normalized: dict[str, float] = {
        str(k).strip().lower(): float(v)
        for k, v in target_mix.items()
        if float(v) >= 0.0
    }
    total = sum(normalized.values())
    if total <= 0.0:
        raise ValueError("target_mix must contain at least one positive value")
    normalized = {k: v / total for k, v in normalized.items()}

    def land_use_balance_penalty(chromosome: Chromosome, context: OptimizationContext) -> float:
        if not chromosome:
            return 0.0
        counts: dict[str, int] = {label: 0 for label in context.land_use_labels}
        for gene in chromosome:
            if 0 <= gene < len(context.land_use_labels):
                counts[context.land_use_labels[gene]] += 1
        scale       = float(len(chromosome))
        current_mix = {label: count / scale for label, count in counts.items()}
        return sum(
            abs(current_mix.get(label, 0.0) - normalized.get(label, 0.0))
            for label in context.land_use_labels
        )

    land_use_balance_penalty.__name__ = "land_use_balance_penalty"
    return land_use_balance_penalty



def mean_suitability_loss(
    chromosome: Chromosome,
    context: OptimizationContext,
) -> float:
    """
    Minimize mismatch between assigned land use and parcel-level suitability.

    0.0 = every parcel is assigned to a perfectly suitable use.
    1.0 = every parcel is assigned to a completely unsuitable use.
    """
    if not context.parcels:
        return 0.0

    total_area = sum(max(parcel.area_m2, 0.0) for parcel in context.parcels)

    if total_area <= 0.0:
        losses = []
        for gene, parcel in zip(chromosome, context.parcels):
            if 0 <= gene < len(context.land_use_labels):
                use_label = context.land_use_labels[gene]
                suitability = float(parcel.suitability.get(use_label, 0.0))
                losses.append(1.0 - min(max(suitability, 0.0), 1.0))

        return sum(losses) / len(losses) if losses else 0.0

    weighted_loss = 0.0

    for gene, parcel in zip(chromosome, context.parcels):
        if not (0 <= gene < len(context.land_use_labels)):
            continue

        use_label = context.land_use_labels[gene]
        suitability = float(parcel.suitability.get(use_label, 0.0))
        suitability = min(max(suitability, 0.0), 1.0)

        weighted_loss += (1.0 - suitability) * max(parcel.area_m2, 0.0)

    return weighted_loss / total_area

def default_objectives() -> tuple[ObjectiveFunction, ...]:
    """Default objective set for land-use optimization."""
    return (
        zoning_violation_penalty,
        mean_suitability_loss,
        make_green_area_deviation(_DEFAULT_GREEN_TARGET),
        environmental_risk_exposure,
        fragmentation_penalty,
    )