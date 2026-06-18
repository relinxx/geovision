"""Rule-based explanation service for parcel-level plan assignments."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from services.risk_explainer import RiskExplainer

try:
    from agent.spatial_agent.spatial.geo import infer_allowed_use_labels
except Exception:  # pragma: no cover - defensive import guard
    infer_allowed_use_labels = None  # type: ignore[assignment]

try:
    from services.spatial_cache import normalize_target_mix
except Exception:  # pragma: no cover - defensive import guard
    normalize_target_mix = None  # type: ignore[assignment]


LAND_USE_LABELS = ("residential", "commercial", "industrial", "green")


def _as_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _normalize_risk(value: Any) -> Optional[float]:
    parsed = _as_float(value)
    if parsed is None or parsed < 0.0:
        return None
    if parsed <= 1.0:
        return parsed
    if parsed <= 100.0:
        return parsed / 100.0
    return None

def _risk_to_suitability_scores(risk_norm: float) -> Dict[str, float]:
    """
    Derive land-use suitability from normalized environmental risk.

    This mirrors SuitabilityAgent.predict():
    residential = max(0.0, 0.8 - risk)
    commercial  = max(0.0, 0.7 - risk * 0.8)
    industrial  = max(0.0, 0.6 - risk * 0.5)
    green       = min(1.0, 0.2 + risk)
    """
    risk = min(max(float(risk_norm), 0.0), 1.0)

    return {
        "residential": max(0.0, 0.8 - risk),
        "commercial": max(0.0, 0.7 - risk * 0.8),
        "industrial": max(0.0, 0.6 - risk * 0.5),
        "green": min(1.0, 0.2 + risk),
    }

def _score_label(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= 0.70:
        return "high"
    if score >= 0.40:
        return "moderate"
    return "low"


def _risk_label(risk: Optional[float]) -> str:
    if risk is None:
        return "unknown"
    if risk >= 0.70:
        return "high"
    if risk >= 0.40:
        return "moderate"
    return "low"


def _get_suitability_scores(parcel_properties: Mapping[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    field_candidates = {
        "residential": [
            "residential",
            "suitability_residential",
            "residential_suitability",
            "score_residential",
            "residential_score",
        ],
        "commercial": [
            "commercial",
            "suitability_commercial",
            "commercial_suitability",
            "score_commercial",
            "commercial_score",
        ],
        "industrial": [
            "industrial",
            "suitability_industrial",
            "industrial_suitability",
            "score_industrial",
            "industrial_score",
        ],
        "green": [
            "green",
            "suitability_green",
            "green_suitability",
            "score_green",
            "green_score",
        ],
    }

    found_explicit_score = False

    for label, candidate_keys in field_candidates.items():
        score = None

        for key in candidate_keys:
            score = _normalize_risk(parcel_properties.get(key))
            if score is not None:
                found_explicit_score = True
                break

        scores[label] = score if score is not None else 0.0

    if found_explicit_score:
        return scores

    risk = _normalize_risk(parcel_properties.get("environmental_risk"))
    if risk is None:
        risk = _normalize_risk(parcel_properties.get("xgb_risk_score"))
    if risk is None:
        risk = _normalize_risk(parcel_properties.get("rule_risk_score"))

    if risk is not None:
        return _risk_to_suitability_scores(risk)

    return scores


def _get_risk(parcel_properties: Mapping[str, Any]) -> Optional[float]:
    risk = _normalize_risk(parcel_properties.get("environmental_risk"))
    if risk is not None:
        return risk

    risk = _normalize_risk(parcel_properties.get("xgb_risk_score"))
    if risk is not None:
        return risk

    return _normalize_risk(parcel_properties.get("rule_risk_score"))


def _normalize_target_mix_safe(target_mix: Mapping[str, Any] | None) -> Dict[str, float]:
    raw = dict(target_mix or {})
    if not raw:
        return {}
    if normalize_target_mix is not None:
        try:
            return normalize_target_mix(raw)
        except Exception:
            pass

    filtered: Dict[str, float] = {}
    for key, value in raw.items():
        parsed = _as_float(value)
        if parsed is None or parsed < 0.0:
            continue
        normalized_key = str(key).strip().lower()
        if not normalized_key:
            continue
        filtered[normalized_key] = parsed
    total = sum(filtered.values())
    if total <= 0.0:
        return {}
    return {key: value / total for key, value in filtered.items()}


def _append_unique(items: list[str], message: str) -> None:
    if message and message not in items:
        items.append(message)


def explain_assignment(
    parcel_properties: Mapping[str, Any],
    assigned_use: str,
    target_mix: Mapping[str, float] | None = None,
    spatial_context: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Explain why a parcel received a specific land-use assignment.

    The explanation is intentionally rule-based and planner-friendly.

    Main goals:
    - Avoid generic repeated reasons.
    - Do not claim the assignment is a good fit when the assigned score is low.
    - Distinguish suitability-driven, risk-driven, zoning-driven, and target-driven assignments.
    - Produce different explanations for residential/commercial/industrial/green.
    """
    assigned = str(assigned_use).strip().lower()
    if assigned not in LAND_USE_LABELS:
        raise ValueError(f"Unsupported assigned use: {assigned_use}")

    properties = dict(parcel_properties or {})
    suitability_scores = _get_suitability_scores(properties)

    assigned_score = suitability_scores.get(assigned, 0.0)
    sorted_scores = sorted(
        suitability_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_suitability_use, best_score = sorted_scores[0]
    assigned_rank = next(
        index + 1
        for index, (label, _score) in enumerate(sorted_scores)
        if label == assigned
    )

    suitability_gap = best_score - assigned_score

    risk = _get_risk(properties)
    risk_level = _risk_label(risk)
    normalized_target_mix = _normalize_target_mix_safe(target_mix)
    target_pct = normalized_target_mix.get(assigned)

    reasons: list[str] = []
    warnings: list[str] = []

    use_title = assigned.replace("_", " ").title()
    assigned_upper = assigned.upper()

    # ------------------------------------------------------------------
    # 1. Suitability-specific explanation
    # ------------------------------------------------------------------
    if assigned_score >= 0.70:
        if assigned == "residential":
            _append_unique(
                reasons,
                f"Residential suitability is high ({assigned_score:.2f}), so the parcel is a strong candidate for housing-oriented development.",
            )
        elif assigned == "commercial":
            _append_unique(
                reasons,
                f"Commercial suitability is high ({assigned_score:.2f}), so the parcel is a strong candidate for activity-serving or business use.",
            )
        elif assigned == "industrial":
            _append_unique(
                reasons,
                f"Industrial suitability is high ({assigned_score:.2f}), so the parcel is relatively suitable for employment or production-oriented use.",
            )
        elif assigned == "green":
            _append_unique(
                reasons,
                f"Green/open-space suitability is high ({assigned_score:.2f}), so the parcel is a strong candidate for conservation, park, or buffer use.",
            )

    elif assigned_score >= 0.40:
        _append_unique(
            reasons,
            f"{use_title} suitability is moderate ({assigned_score:.2f}), so this assignment is acceptable but not a perfect parcel-level fit.",
        )

    elif assigned_score > 0.0:
        _append_unique(
            warnings,
            f"{use_title} suitability is weak for this parcel ({assigned_score:.2f}).",
        )
    else:
        _append_unique(
            warnings,
            f"{use_title} suitability is very low or unavailable for this parcel ({assigned_score:.2f}).",
        )

    # ------------------------------------------------------------------
    # 2. Compare assigned use against best suitability option
    # ------------------------------------------------------------------
    if assigned == best_suitability_use and assigned_score > 0.0:
        _append_unique(
            reasons,
            f"{use_title} is the best suitability option for this parcel.",
        )
    elif assigned != best_suitability_use:
        if suitability_gap >= 0.25:
            _append_unique(
                warnings,
                f"{use_title} was selected even though {best_suitability_use.title()} has a much higher suitability score ({best_score:.2f} vs {assigned_score:.2f}).",
            )
        elif suitability_gap >= 0.10 and assigned_score >= 0.30:
            _append_unique(
                warnings,
                f"{use_title} is not the top suitability option; {best_suitability_use.title()} scores slightly better ({best_score:.2f} vs {assigned_score:.2f}).",
            )
        elif assigned_score >= 0.40:
            _append_unique(
                reasons,
                f"{use_title} is close to the best suitability option, with only a small score difference from {best_suitability_use.title()}.",
            )
        else:
            _append_unique(
                warnings,
                f"{use_title} does not appear to be a strong suitability match compared with the best option, {best_suitability_use.title()}.",
            )

    # ------------------------------------------------------------------
    # 3. Environmental risk explanation
    # ------------------------------------------------------------------
    if risk is not None:
        risk_pct = risk * 100

        if assigned == "green":
            if risk >= 0.70:
                _append_unique(
                    reasons,
                    f"Environmental risk is high ({risk_pct:.0f}%), so assigning this parcel to green/open space helps avoid exposing development to hazards.",
                )
            elif risk >= 0.40:
                _append_unique(
                    reasons,
                    f"Environmental risk is moderate ({risk_pct:.0f}%), so green/open-space use can act as a safer buffer or lower-intensity use.",
                )
            else:
                _append_unique(
                    reasons,
                    f"Environmental risk is low ({risk_pct:.0f}%), so this green assignment is more likely driven by suitability, zoning, or target-mix balance than hazard avoidance.",
                )

        else:
            if risk >= 0.70:
                _append_unique(
                    warnings,
                    f"Environmental risk is high ({risk_pct:.0f}%), so assigning this parcel to built use requires careful planner review.",
                )
            elif risk >= 0.40:
                _append_unique(
                    warnings,
                    f"Environmental risk is moderate ({risk_pct:.0f}%), so {assigned} development may need mitigation or additional review.",
                )
            else:
                if assigned == "residential":
                    _append_unique(
                        reasons,
                        f"Environmental risk is low ({risk_pct:.0f}%), which makes residential development more feasible from a hazard-exposure perspective.",
                    )
                elif assigned == "commercial":
                    _append_unique(
                        reasons,
                        f"Environmental risk is low ({risk_pct:.0f}%), which makes commercial activity more feasible from a hazard-exposure perspective.",
                    )
                elif assigned == "industrial":
                    _append_unique(
                        reasons,
                        f"Environmental risk is low ({risk_pct:.0f}%), which reduces hazard-related concerns for industrial allocation.",
                    )

    # ------------------------------------------------------------------
    # 4. Hazard-factor explanation
    # ------------------------------------------------------------------
    active_hazard_labels: list[str] = []
    try:
        explained = RiskExplainer().explain(properties)
        active_hazard_labels = [
            item["label"]
            for item in explained.get("contributions", [])
            if item.get("active")
        ]
    except Exception:
        active_hazard_labels = []

    if active_hazard_labels:
        hazard_text = ", ".join(active_hazard_labels[:3])

        if assigned == "green":
            _append_unique(
                reasons,
                f"Active hazard or constraint factors support a lower-intensity open-space treatment: {hazard_text}.",
            )
        else:
            _append_unique(
                warnings,
                f"Active hazard or constraint factors require review before built development: {hazard_text}.",
            )

    # ------------------------------------------------------------------
    # 5. Zoning compatibility explanation
    # ------------------------------------------------------------------
    allowed_uses: list[str] = []
    zoning_signal_present = any(
        properties.get(key) not in (None, "")
        for key in (
            "allowed_uses",
            "ZONING_CODE",
            "GP_LAND_USE",
            "zoning_code",
            "gp_land_use",
        )
    )

    if zoning_signal_present and infer_allowed_use_labels is not None:
        try:
            inferred = infer_allowed_use_labels(properties, LAND_USE_LABELS)
            allowed_uses = [label for label in inferred if label in LAND_USE_LABELS]
        except Exception:
            allowed_uses = []

    if allowed_uses:
        if assigned in allowed_uses:
            if assigned == "residential":
                _append_unique(
                    reasons,
                    "Available zoning or land-use information appears compatible with residential use.",
                )
            elif assigned == "commercial":
                _append_unique(
                    reasons,
                    "Available zoning or land-use information appears compatible with commercial use.",
                )
            elif assigned == "industrial":
                _append_unique(
                    reasons,
                    "Available zoning or land-use information appears compatible with industrial use.",
                )
            elif assigned == "green":
                _append_unique(
                    reasons,
                    "Available zoning or land-use information appears compatible with green/open-space use.",
                )
        else:
            _append_unique(
                warnings,
                f"Available zoning information does not clearly allow {assigned} use.",
            )
    elif zoning_signal_present:
        _append_unique(
            warnings,
            "Zoning information is present, but the system could not confidently infer whether this assignment is allowed.",
        )

    # ------------------------------------------------------------------
    # 6. Target-mix explanation
    # ------------------------------------------------------------------
    # Only use this as a strong reason when the assignment is not already
    # strongly justified by suitability.
    if target_pct is not None and target_pct > 0.0:
        target_text = f"{target_pct * 100:.0f}%"

        if assigned_score < 0.40 or assigned != best_suitability_use:
            _append_unique(
                reasons,
                f"The selected scenario targets about {target_text} {assigned} land use, so this assignment may be helping satisfy the plan-level land-use mix.",
            )
        else:
            _append_unique(
                reasons,
                f"This assignment also supports the scenario target of about {target_text} {assigned} land use.",
            )

    # ------------------------------------------------------------------
    # 7. Explicit trade-off warning
    # ------------------------------------------------------------------
    if assigned_score < 0.30 and assigned != best_suitability_use:
        _append_unique(
            warnings,
            f"This looks like a plan-level trade-off rather than a parcel-level best-fit assignment because {assigned} suitability is low and {best_suitability_use.title()} is the stronger option.",
        )

    # ------------------------------------------------------------------
    # 8. Spatial compatibility / neighbour-aware explanation
    # ------------------------------------------------------------------
    spatial_summary: Dict[str, Any] | None = None
    if isinstance(spatial_context, Mapping) and spatial_context:
        spatial_summary = dict(spatial_context)

        for reason in spatial_summary.get("reasons") or []:
            _append_unique(reasons, str(reason))

        for warning in spatial_summary.get("warnings") or []:
            _append_unique(warnings, str(warning))

    # ------------------------------------------------------------------
    # 9. Build an honest headline
    # ------------------------------------------------------------------
    headline_reasons: list[str] = []

    if assigned == best_suitability_use and assigned_score >= 0.40:
        headline_reasons.append(f"{assigned} is the strongest suitability match")

    if assigned == "green" and risk is not None and risk >= 0.40:
        headline_reasons.append("green use reduces exposure to environmental constraints")

    if assigned != "green" and risk is not None and risk <= 0.35:
        headline_reasons.append("environmental risk is low enough for built use")

    if allowed_uses and assigned in allowed_uses:
        headline_reasons.append("zoning appears compatible")

    if target_pct is not None and target_pct > 0.0 and (
        assigned_score < 0.40 or assigned != best_suitability_use
    ):
        headline_reasons.append("the scenario needs this land-use category to meet the target mix")

    if spatial_summary and int(spatial_summary.get("neighbor_pairs_evaluated") or 0) > 0:
        if int(spatial_summary.get("conflict_pairs") or 0) > 0:
            headline_reasons.append("nearby land-use compatibility creates a review concern")
        elif int(spatial_summary.get("compatible_pairs") or 0) > 0:
            headline_reasons.append("nearby assignments support spatial compatibility")

    if assigned_score < 0.30 and assigned != best_suitability_use:
        headline = (
            f"This parcel was assigned as {assigned_upper}, but the explanation indicates a trade-off: "
            f"{use_title} suitability is low while {best_suitability_use.title()} is the better parcel-level fit."
        )
    elif headline_reasons:
        headline = (
            f"This parcel was assigned as {assigned_upper} mainly because "
            + ", ".join(headline_reasons)
            + "."
        )
    else:
        headline = (
            f"This parcel was assigned as {assigned_upper} based on the combined optimizer trade-off between suitability, risk, zoning, and target mix."
        )

    return {
    "assigned_use": assigned,
    "headline": headline,
    "reasons": reasons,
    "warnings": warnings,
    "risk_level": risk_level,
    "best_suitability_use": best_suitability_use,
    "spatial_context": spatial_summary,
    "scores": {
        "suitability": suitability_scores,
        "assigned_use_score": assigned_score,
        "best_use_score": best_score,
        "suitability_gap": suitability_gap,
        "suitability_rank": assigned_rank,
        "environmental_risk": risk,
        "allowed_uses": allowed_uses,
        "target_mix_for_assigned_use": target_pct,
    },
}