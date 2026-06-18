"""Shared utilities used across agents and services."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import geopandas as gpd


def resolve_path(base_dir: Path, candidate) -> Path:
    path = Path(candidate)
    return path if path.is_absolute() else base_dir / path


def load_layer(path: Path, name: str, target_crs) -> gpd.GeoDataFrame:
    """Load a spatial dataset and reproject to target_crs if needed."""
    if not path.exists():
        logging.warning("%s not found at %s; returning empty layer", name, path)
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    logging.info("Loading %s from %s", name, path)
    gdf = gpd.read_file(path)

    if gdf.crs is None:
        logging.warning("%s has no CRS; assuming %s", name, target_crs)
        gdf.set_crs(target_crs, inplace=True)
    elif gdf.crs != target_crs:
        gdf = gdf.to_crs(target_crs)

    return gdf


def env_int(name: str, default: int, minimum: int) -> int:
    """Read an integer environment variable, clamped to minimum."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return max(default, minimum)
    try:
        return max(int(raw_value), minimum)
    except (TypeError, ValueError):
        logging.warning("Invalid integer for %s=%r; using default %s", name, raw_value, default)
        return max(default, minimum)
