"""Merge environmental and zoning outputs into a single parcel GeoJSON.

Input:
- backend/agent/environment_agent/data/outputs/parcels_env_risk.geojson
- backend/agent/zoning_agent/data/outputs/parcels_zoning.geojson

Output:
- frontend/public/parcels_unified.geojson (for frontend consumption)

Join key: APN (string-normalized). Falls back to index-based join if APN is missing.
"""

from pathlib import Path
import logging
from typing import Optional

import geopandas as gpd
import pandas as pd


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _load_geojson(path: Path, name: str) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} not found at {path}")
    logging.info("Loading %s from %s", name, path)
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        logging.warning("%s has no CRS; assuming EPSG:4326", name)
        gdf.set_crs("EPSG:4326", inplace=True)
    return gdf


def _ensure_same_crs(env_gdf: gpd.GeoDataFrame, zoning_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if zoning_gdf.crs != env_gdf.crs:
        logging.info("Reprojecting zoning GeoDataFrame from %s to %s", zoning_gdf.crs, env_gdf.crs)
        zoning_gdf = zoning_gdf.to_crs(env_gdf.crs)
    return zoning_gdf


def _normalize_apn(df: gpd.GeoDataFrame, col: str = "APN") -> Optional[str]:
    if col not in df.columns:
        return None
    key = "apn_key"
    df[key] = df[col].astype(str).str.strip()
    return key


def merge_parcels(env_path: Optional[Path] = None, zoning_path: Optional[Path] = None, output_path: Optional[Path] = None) -> None:
    base = Path(__file__).resolve().parent.parent  # backend/agent
    repo_root = base.parent.parent  # geovison/

    if env_path is None:
        # Use existing clipped env-risk GeoJSON from the frontend as baseline
        env_path = repo_root / "frontend/public/parcels_env_risk_clipped.geojson"
    if zoning_path is None:
        zoning_path = base / "zoning_agent/data/outputs/parcels_zoning.geojson"
    if output_path is None:
        # Write directly into frontend public so Vite can serve it at /parcels_unified.geojson
        output_path = repo_root / "frontend/public/parcels_unified.geojson"

    logging.info("Environment path: %s", env_path)
    logging.info("Zoning path: %s", zoning_path)
    logging.info("Output path: %s", output_path)

    env_gdf = _load_geojson(env_path, "Environmental parcels")
    zoning_gdf = _load_geojson(zoning_path, "Zoning parcels")

    zoning_gdf = _ensure_same_crs(env_gdf, zoning_gdf)

    # Normalize APN keys if present
    env_key = _normalize_apn(env_gdf, "APN")
    zoning_key = _normalize_apn(zoning_gdf, "APN")

    # Select zoning attribute columns (drop zoning geometry; env geometry is authoritative)
    zoning_attr_cols = [c for c in zoning_gdf.columns if c != "geometry"]
    zoning_attrs = zoning_gdf[zoning_attr_cols].copy()

    if env_key and zoning_key:
        logging.info("Merging on APN (normalized string key)...")

        # Keep only zoning APNs that appear exactly once to avoid fan-out duplicates
        zoning_counts = zoning_attrs[zoning_key].value_counts()
        unique_apns = zoning_counts[zoning_counts == 1].index
        before_filter = len(zoning_attrs)
        zoning_attrs = zoning_attrs[zoning_attrs[zoning_key].isin(unique_apns)].copy()
        logging.info(
            "Filtered zoning records on unique APNs: %s → %s",
            before_filter,
            len(zoning_attrs),
        )

        # Ensure the column names match for merge
        if zoning_key != env_key:
            zoning_attrs.rename(columns={zoning_key: env_key}, inplace=True)

        unified = env_gdf.merge(
            zoning_attrs,
            on=env_key,
            how="left",
            suffixes=("", "_zoning"),
        )
    else:
        logging.warning("APN not present in both datasets; falling back to index-based join. This assumes identical ordering.")
        zoning_attrs = zoning_attrs.reset_index(drop=True)
        unified = env_gdf.reset_index(drop=True).join(zoning_attrs, rsuffix="_zoning")

    # Ensure geometry from env_gdf is used and CRS is WGS84 for frontend
    if unified.crs is None:
        unified.set_crs(env_gdf.crs or "EPSG:4326", inplace=True)
    try:
        unified = unified.to_crs("EPSG:4326")
    except Exception as exc:
        logging.warning("Failed to reproject to EPSG:4326: %s", exc)

    # Basic validation: log if parcel count changed (should not with unique APNs)
    if len(unified) != len(env_gdf):
        logging.warning(
            "Merge changed parcel count: %s → %s",
            len(env_gdf),
            len(unified),
        )

    # As a final safeguard, collapse back to one row per original env index
    if len(unified) > len(env_gdf):
        logging.warning(
            "Unified dataset has more rows than env; collapsing to first match per parcel."
        )
        unified = (
            unified.reset_index()
            .groupby("index", as_index=False)
            .first()
            .drop(columns=["index"])
        )

    # Logging stats around zoning coverage
    if "ZONING_CODE" in unified.columns:
        zoning_present = unified["ZONING_CODE"].notna().sum()
        zoning_missing = unified["ZONING_CODE"].isna().sum()
        logging.info("Parcels with zoning: %s", zoning_present)
        logging.info("Parcels missing zoning: %s", zoning_missing)
        # Mark missing zoning explicitly
        unified["ZONING_CODE"] = unified["ZONING_CODE"].fillna("UNKNOWN")
    else:
        logging.warning("Unified dataset has no ZONING_CODE column after merge.")

    # Optional: protect frontend from extremely large datasets (demo-friendly)
    if len(unified) > 50000:
        logging.warning("Large dataset (%s parcels); sampling 50k parcels for demo use.", len(unified))
        unified = unified.sample(n=50000, random_state=42)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logging.info("Writing unified parcels to %s", output_path)
    unified.to_file(output_path, driver="GeoJSON")
    logging.info("Done writing unified parcels.")


def main() -> None:
    merge_parcels()


if __name__ == "__main__":
    main()
