"""
Environmental Suitability Agent Module

Provides the SuitabilityAgent class, which serves pre-computed environmental
risk scores from GeoJSON files. The agent:

1. Loads pre-computed risk scores (XGBoost ML model or rule-based fallback)
2. Maps risk scores to land-use suitability scores (residential, commercial, etc.)
3. Provides predictions for parcel suitability analysis

Risk scores are computed offline by the training pipeline (main.py) which uses
XGBoost to predict environmental risk based on hazard flags (flood, fault, etc.).

Optimization notes (see CHANGELOG.md for full history):
    - predict() is now fully vectorized with NumPy — no more iterrows() loop.
      Single-pass DataFrame lookup + array math regardless of batch size.
    - Feature-based fallback still applied row-by-row only for missing parcels
      (typically a tiny fraction of the input).
"""
import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, Optional, Iterable

import numpy as np
import pandas as pd


def find_default_risk_data_path(base_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Locate the best available precomputed environmental risk GeoJSON.

    Search order:
    1. environment_agent/data/outputs/parcels_env_risk_clipped.geojson
    2. environment_agent/data/outputs/parcels_env_risk.geojson
    3. frontend/public/parcels_env_risk_clipped.geojson
    4. frontend/public/parcels_env_risk.geojson
    """
    agent_dir = base_dir or Path(__file__).resolve().parent
    repo_root = agent_dir.parent.parent.parent

    candidates: Iterable[Path] = (
        agent_dir / "data" / "outputs" / "parcels_env_risk_clipped.geojson",
        agent_dir / "data" / "outputs" / "parcels_env_risk.geojson",
        repo_root / "frontend" / "public" / "parcels_env_risk_clipped.geojson",
        repo_root / "frontend" / "public" / "parcels_env_risk.geojson",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


class SuitabilityAgent:
    """
    Environmental Suitability Agent.

    Provides environmental risk-based suitability predictions for land-use planning.
    Uses pre-computed risk scores stored in GeoJSON format, with XGBoost ML model
    as primary source and rule-based scores as fallback.

    Attributes:
        risk_data (pd.DataFrame): DataFrame indexed by APN for O(1) lookups.
    """

    def __init__(self, model_path: Path = None):
        self.risk_data = pd.DataFrame()

        resolved_model_path: Optional[Path] = model_path
        if resolved_model_path is not None and not resolved_model_path.exists():
            logging.warning(
                "Configured risk data path does not exist: %s. Attempting fallback lookup.",
                resolved_model_path,
            )
            resolved_model_path = None

        if resolved_model_path is None:
            resolved_model_path = find_default_risk_data_path()

        if resolved_model_path is not None:
            self.load_data(resolved_model_path)
        else:
            logging.warning(
                "No precomputed risk GeoJSON found. SuitabilityAgent will use feature-based fallback scoring."
            )

    def load_data(self, path: Path) -> None:
        """
        Load risk score data from GeoJSON file into an APN-indexed DataFrame.

        Prioritizes xgb_risk_score (ML model) over rule_risk_score (fallback only).
        """
        if not path.exists():
            logging.warning("Risk data not found at %s", path)
            return

        logging.info("Loading risk data from %s", path)
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            records = []
            for feature in data.get("features", []):
                props = feature.get("properties", {}) or {}

                apn = props.get("APN") or props.get("apn")
                if apn is None:
                    continue
                apn_str = str(apn).strip()
                if not apn_str:
                    continue

                risk_score = props.get("xgb_risk_score")
                if risk_score is None:
                    risk_score = props.get("rule_risk_score")
                    if risk_score is not None:
                        logging.warning(
                            "Using rule_risk_score fallback for APN %s (xgb_risk_score missing).",
                            apn_str,
                        )

                if risk_score is None:
                    continue

                records.append({"APN": apn_str, "xgb_risk_score": risk_score})

            if not records:
                logging.warning("No valid APN/risk records found in risk data")
                return

            df = pd.DataFrame.from_records(records)
            df["APN"] = df["APN"].astype(str)
            df.set_index("APN", inplace=True)
            self.risk_data = df

        except Exception as e:
            logging.error("Failed to load risk data: %s", e)

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(result) or math.isinf(result):
            return None
        return result

    def _feature_based_risk(self, row: pd.Series) -> Optional[float]:
        """
        Estimate normalized risk (0–1) from available parcel features.
        Used only when a parcel APN is absent from the precomputed lookup.
        """
        def first_numeric(*keys: str) -> Optional[float]:
            for key in keys:
                if key in row:
                    numeric = self._coerce_float(row.get(key))
                    if numeric is not None:
                        return numeric
            return None

        aqi       = first_numeric("aqi_mean", "AirQualityIndex")
        impervious = first_numeric("impervious_mean", "ImperviousSurface")
        clay      = first_numeric("soil_clay_pct", "ClayContent")
        sand      = first_numeric("soil_sand_pct", "SandContent")

        if aqi is None and impervious is None and clay is None and sand is None:
            return None

        aqi        = 75.0 if aqi is None else aqi
        impervious = 0.5  if impervious is None else impervious
        clay       = 20.0 if clay is None else clay
        sand       = 40.0 if sand is None else sand

        aqi_norm        = min(max((aqi - 20.0) / 130.0, 0.0), 1.0)
        impervious_norm = min(max(impervious / 100.0 if impervious > 1.0 else impervious, 0.0), 1.0)
        clay_norm       = min(max(clay / 100.0, 0.0), 1.0)
        sand_norm       = min(max(sand / 100.0, 0.0), 1.0)

        risk_norm = (
            0.45 * aqi_norm
            + 0.30 * impervious_norm
            + 0.15 * clay_norm
            + 0.10 * (1.0 - sand_norm)
        )
        return min(max(risk_norm, 0.0), 1.0)

    def predict(self, parcels_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict land-use suitability scores based on environmental risk.

        Fully vectorized: single DataFrame lookup + NumPy array math.
        Feature-based fallback is applied only for parcels missing from the
        precomputed index (typically a small fraction).

        Parameters
        ----------
        parcels_df : pd.DataFrame
            Must contain a 'parcel_id' column with APN strings.

        Returns
        -------
        pd.DataFrame with columns:
            parcel_id, residential, commercial, industrial, green, environmental_risk
            All score columns are float in [0, 1].
        """
        pids = parcels_df["parcel_id"].astype(str)

        # --- vectorized lookup ---
        # reindex aligns by APN; missing rows get NaN automatically
        if not self.risk_data.empty:
            matched   = self.risk_data.reindex(pids.values)
            risk_raw  = matched["xgb_risk_score"].to_numpy(dtype=float)
        else:
            risk_raw = np.full(len(pids), np.nan)

        # Normalize 0-100 → 0-1; NaN stays NaN (handled below)
        risk_norm = np.where(
            np.isfinite(risk_raw),
            np.clip(risk_raw / 100.0, 0.0, 1.0),
            np.nan,
        )

        # --- feature-based fallback for missing APNs only ---
        missing_idx = np.where(~np.isfinite(risk_norm))[0]
        if missing_idx.size > 0:
            logging.debug(
                "%d parcels not found in risk lookup; applying feature-based fallback.",
                missing_idx.size,
            )
            for i in missing_idx:
                fb = self._feature_based_risk(parcels_df.iloc[i])
                if fb is not None:
                    risk_norm[i] = fb

        # --- vectorized suitability scoring ---
        # Suitability heuristics based on planning best practices:
        #   Residential: most risk-averse  (high penalty)
        #   Commercial:  moderate penalty
        #   Industrial:  lower penalty     (tolerates risk)
        #   Green:       inverse           (high-risk areas → conservation value)
        # Parcels still NaN after fallback get neutral 0.5 defaults.
        has_risk = np.isfinite(risk_norm)

        residential = np.where(has_risk, np.maximum(0.0, 0.8 - risk_norm),       0.5)
        commercial  = np.where(has_risk, np.maximum(0.0, 0.7 - risk_norm * 0.8), 0.5)
        industrial  = np.where(has_risk, np.maximum(0.0, 0.6 - risk_norm * 0.5), 0.5)
        green       = np.where(has_risk, np.minimum(1.0, 0.2 + risk_norm),       0.5)
        env_risk    = np.where(has_risk, risk_norm,                               0.0)

        return pd.DataFrame({
            "parcel_id":          pids.values,
            "residential":        residential,
            "commercial":         commercial,
            "industrial":         industrial,
            "green":              green,
            "environmental_risk": env_risk,
        })
