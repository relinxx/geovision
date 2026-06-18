"""
Risk Explainer — hazard-flag attribution and counterfactual scoring.

Uses the same RISK_WEIGHTS as the training pipeline but applied directly to
GeoJSON parcel properties (no ML model required at inference time).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

RISK_WEIGHTS: Dict[str, float] = {
    "has_flood":        0.25,
    "has_fault":        0.20,
    "has_liquefaction": 0.15,
    "is_steep":         0.15,
    "is_fire_zone":     0.15,
    "in_esa":           0.05,
    "in_mscp":          0.05,
}

_FACTOR_LABELS: Dict[str, str] = {
    "has_flood":        "100-Year Floodplain",
    "has_fault":        "Active Fault Zone",
    "has_liquefaction": "Liquefaction Risk",
    "is_steep":         "Steep Slope (>25%)",
    "is_fire_zone":     "Fire Hazard Severity",
    "in_esa":           "Environmentally Sensitive Area",
    "in_mscp":          "MSCP Habitat Coverage",
}


class RiskExplainer:
    """Attribute environmental risk to individual hazard flags."""

    def explain(self, parcel_props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompose risk score into per-factor contributions.

        Parameters
        ----------
        parcel_props : dict
            GeoJSON feature properties (may include has_flood, has_fault, etc.)

        Returns
        -------
        dict with:
            contributions  — list of {factor, label, weight, active, contribution_pct}
            total_rule_score (0–100)
            xgb_risk_score  — from precomputed field if present
        """
        raw_total = 0.0
        contributions = []

        for flag, weight in RISK_WEIGHTS.items():
            active = int(parcel_props.get(flag, 0)) == 1
            contribution = weight if active else 0.0
            raw_total += contribution
            contributions.append({
                "factor":           flag,
                "label":            _FACTOR_LABELS[flag],
                "weight":           weight,
                "active":           active,
                "contribution_pct": round(contribution * 100, 1),
            })

        # Sort descending by contribution
        contributions.sort(key=lambda x: x["contribution_pct"], reverse=True)

        return {
            "contributions":    contributions,
            "total_rule_score": round(raw_total * 100, 2),
            "xgb_risk_score":   parcel_props.get("xgb_risk_score"),
        }

    def counterfactual(
        self,
        parcel_props: Dict[str, Any],
        changes: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute what the risk score would be if the specified flags were changed.

        Parameters
        ----------
        parcel_props : dict  — current GeoJSON properties
        changes : dict       — flag overrides, e.g. {"has_flood": 0, "is_steep": 1}

        Returns
        -------
        dict with:
            original_score (0–100)
            counterfactual_score (0–100)
            delta  — difference (positive = risk increased)
            applied_changes — which flags were toggled
        """
        # Original
        original = sum(
            RISK_WEIGHTS[flag]
            for flag in RISK_WEIGHTS
            if int(parcel_props.get(flag, 0)) == 1
        )

        # Modified
        modified_props = {**parcel_props, **{k: v for k, v in changes.items() if k in RISK_WEIGHTS}}
        modified = sum(
            RISK_WEIGHTS[flag]
            for flag in RISK_WEIGHTS
            if int(modified_props.get(flag, 0)) == 1
        )

        applied = {
            k: {"from": int(parcel_props.get(k, 0)), "to": int(v)}
            for k, v in changes.items()
            if k in RISK_WEIGHTS
        }

        return {
            "original_score":      round(original * 100, 2),
            "counterfactual_score": round(modified * 100, 2),
            "delta":               round((modified - original) * 100, 2),
            "applied_changes":     applied,
        }
