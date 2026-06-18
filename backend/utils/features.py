"""
Feature Engineering Utilities

This module handles feature extraction and transformation for parcel data:
1. Extract/attach features from GeoJSON parcel data
2. Map frontend feature names to model input column names
3. Generate synthetic features when planning parameters are missing

The feature schema (feature_schema.json) ensures consistency between:
- Frontend feature names (lon, lat, soil_sand_pct, etc.)
- Model training column names (Longitude, Latitude, SandContent, etc.)
- Backend processing
"""
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


# Load feature name mapping schema (frontend -> model)
# This ensures all components use consistent column names
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "feature_schema.json"
with _SCHEMA_PATH.open() as f:
    FEATURE_SCHEMA: Dict[str, str] = json.load(f)


def _deterministic_fallback(parcel_id: Any, field_name: str, lower: float, upper: float) -> float:
    """Generate a deterministic pseudo-random fallback value for missing inputs."""
    token = f"{parcel_id}:{field_name}".encode("utf-8")
    digest = hashlib.sha256(token).hexdigest()
    scale = int(digest[:8], 16) / 0xFFFFFFFF
    return lower + ((upper - lower) * scale)


def attach_features(parcels: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    B2 - Attach features to parcel GeoJSON features.
    
    Uses planning parameters from frontend if provided, otherwise generates synthetic (random) values.

    Parameters
    ----------
    parcels:
        List of GeoJSON-like Feature dicts. Each feature is expected to have:
          - "id": parcel identifier
          - "properties": { 
                "centroid": { "x": float, "y": float },
                "soil_sand_pct": float (optional),
                "soil_clay_pct": float (optional),
                "aqi_mean": float (optional),
                "impervious_mean": float (optional)
            }

        This matches the frontend's `ParcelGeoJSONExport.features` shape.

    Returns
    -------
    pd.DataFrame
        One row per parcel with environmental / urban features.
        Column names are the *frontend* feature keys (lon, lat, soil_sand_pct, ...)
        so the FE can reason about them. The model-facing names come from
        `rename_features_for_model`.
    """
    rows: List[Dict[str, Any]] = []

    for f in parcels:
        pid = f.get("id")
        props = f.get("properties") or {}
        centroid = props.get("centroid") or {}

        # Extract coordinates from centroid
        lon = centroid.get("x")
        lat = centroid.get("y")

        # Extract or generate planning parameters
        # Priority: Use frontend-provided values if available (user inputs or API data)
        # Fallback: Generate synthetic/random values for development/testing
        # In production, these should ideally come from real GIS data sources
        
        # Soil composition parameters (0-100 percentage)
        soil_sand_pct = props.get("soil_sand_pct")
        if soil_sand_pct is None:
            # Synthetic fallback: deterministic value between 10-80%
            soil_sand_pct = _deterministic_fallback(pid, "soil_sand_pct", 10.0, 80.0)

        soil_clay_pct = props.get("soil_clay_pct")
        if soil_clay_pct is None:
            soil_clay_pct = _deterministic_fallback(pid, "soil_clay_pct", 5.0, 40.0)

        aqi_mean = props.get("aqi_mean")
        if aqi_mean is None:
            aqi_mean = _deterministic_fallback(pid, "aqi_mean", 20.0, 150.0)

        impervious_mean = props.get("impervious_mean")
        if impervious_mean is None:
            impervious_mean = _deterministic_fallback(pid, "impervious_mean", 0.0, 1.0)

        rows.append(
            {
                "parcel_id": pid,
                "lon": lon,
                "lat": lat,
                "soil_sand_pct": soil_sand_pct,
                "soil_clay_pct": soil_clay_pct,
                "aqi_mean": aqi_mean,
                "impervious_mean": impervious_mean,
            }
        )

    return pd.DataFrame(rows)


def rename_features_for_model(df: pd.DataFrame) -> pd.DataFrame:
    """
    Use the shared feature schema (backend/data/feature_schema.json)
    to rename frontend feature keys to model input column names.

    Example schema:
      {
        "lon": "Longitude",
        "lat": "Latitude",
        "soil_sand_pct": "SandContent",
        "soil_clay_pct": "ClayContent",
        "aqi_mean": "AirQualityIndex",
        "impervious_mean": "ImperviousSurface"
      }

    This function ensures the model, training code, and backend all
    agree on column names and order.
    """
    return df.rename(columns=FEATURE_SCHEMA)

