"""
Environmental Risk Training Pipeline

This module implements the training pipeline for environmental risk prediction:

1. Feature Engineering: Loads spatial hazard layers and joins with parcels
2. Rule-Based Label Generation: Computes rule_risk_score using weighted hazard flags
3. ML Model Training: Trains XGBoost to predict rule_risk_score (supervised learning)
4. Output: Exports GeoJSON with both rule-based and ML-predicted risk scores

Optimization notes (see CHANGELOG.md for full history):
    - Spatial joins parallelized with ThreadPoolExecutor: all 7 run concurrently
    - STRtree bulk intersection replaces per-hazard gpd.sjoin: lower overhead, no
      intermediate dataframe merge per join
    - Per-stage timing logged so you can see exactly where time is spent
"""
import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import STRtree
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# ---------- RISK WEIGHTS (for training label generation) ----------
# Used to compute rule_risk_score, which serves as XGBoost training labels.
# NOT used for production predictions — xgb_risk_score is primary.
RISK_WEIGHTS = {
    "has_flood":        0.25,
    "has_fault":        0.20,
    "has_liquefaction": 0.15,
    "is_steep":         0.15,
    "is_fire_zone":     0.15,
    "in_esa":           0.05,
    "in_mscp":          0.05,
}


# ---------- UTILS ----------
from utils.helpers import resolve_path, load_layer  # noqa: E402


def clip_to_parcels_bbox(hazard: gpd.GeoDataFrame,
                         parcels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Cheap bbox clip so we don't query against full-county hazards."""
    if hazard.empty:
        return hazard
    minx, miny, maxx, maxy = parcels.total_bounds
    hazard = hazard.cx[minx:maxx, miny:maxy]
    return hazard[["geometry"]].copy()


# ---------- OPTIMIZED SPATIAL JOIN ----------

def _compute_flag_strtree(
    parcel_geoms: np.ndarray,
    hazard_geoms: np.ndarray,
    col_name: str,
) -> Tuple[str, np.ndarray]:
    """
    Compute a binary intersection flag for every parcel using STRtree bulk query.

    Replaces gpd.sjoin per hazard layer. STRtree.query with predicate="intersects"
    does a single vectorized pass and returns (2, N) index pairs — no intermediate
    DataFrame merge needed. Shapely 2.0 releases the GIL during the query so this
    is safe to run across multiple threads simultaneously.

    Returns
    -------
    (col_name, flags) where flags is int8 array of length len(parcel_geoms).
    """
    flags = np.zeros(len(parcel_geoms), dtype=np.int8)
    if len(hazard_geoms) == 0:
        return col_name, flags

    tree = STRtree(hazard_geoms)
    # result shape: (2, n_pairs) — result[0] = parcel indices, result[1] = hazard indices
    result = tree.query(parcel_geoms, predicate="intersects")
    if result.size > 0:
        parcel_hit_idx = np.unique(result[0])
        flags[parcel_hit_idx] = 1

    return col_name, flags


# ---------- FEATURE FRAME ----------

def build_feature_frame(
    parcels_path: Path,
    flood_path: Path,
    faults_path: Path,
    liquefaction_path: Path,
    fire_path: Path,
    slopes_path: Path,
    esa_path: Path,
    mscp_path: Path,
) -> gpd.GeoDataFrame:

    t_total = time.perf_counter()

    # Load parcels
    t = time.perf_counter()
    logging.info("Loading parcels from %s", parcels_path)
    parcels = gpd.read_file(parcels_path)
    if parcels.crs is None:
        raise ValueError("Parcels file has no CRS defined.")
    metric_crs = "EPSG:3857"
    parcels = parcels.to_crs(metric_crs)
    logging.info("Loaded %d parcels (%.1fs)", len(parcels), time.perf_counter() - t)

    # Load all hazard layers (I/O-bound, run sequentially — disk is the bottleneck here)
    t = time.perf_counter()
    flood        = load_layer(flood_path,        "Floodplain",                       metric_crs)
    faults       = load_layer(faults_path,       "Active Faults",                    metric_crs)
    liquefaction = load_layer(liquefaction_path, "Potential Liquefaction",            metric_crs)
    fire         = load_layer(fire_path,         "Fire Hazard",                      metric_crs)
    slopes       = load_layer(slopes_path,       "Steep Slopes",                     metric_crs)
    esa          = load_layer(esa_path,          "Environmentally Sensitive Areas",   metric_crs)
    mscp         = load_layer(mscp_path,         "MSCP Habitrak",                    metric_crs)
    logging.info("All hazard layers loaded (%.1fs)", time.perf_counter() - t)

    # Clip each hazard to parcel bbox — cheap filter before the expensive join
    t = time.perf_counter()
    flood        = clip_to_parcels_bbox(flood,        parcels)
    faults       = clip_to_parcels_bbox(faults,       parcels)
    liquefaction = clip_to_parcels_bbox(liquefaction, parcels)
    fire         = clip_to_parcels_bbox(fire,         parcels)
    slopes       = clip_to_parcels_bbox(slopes,       parcels)
    esa          = clip_to_parcels_bbox(esa,          parcels)
    mscp         = clip_to_parcels_bbox(mscp,         parcels)
    logging.info("Hazard layers clipped to parcel bbox (%.1fs)", time.perf_counter() - t)

    # Extract geometry arrays once — shared read-only across threads.
    # Shapely 2.0 geometry arrays are GIL-free for predicate queries, so threads
    # run in true parallel for the CPU-bound STRtree work.
    parcel_geoms = parcels.geometry.values

    def _geoms(gdf: gpd.GeoDataFrame) -> np.ndarray:
        return gdf.geometry.values if not gdf.empty else np.array([])

    hazard_jobs = [
        ("has_flood",        _geoms(flood)),
        ("has_fault",        _geoms(faults)),
        ("has_liquefaction", _geoms(liquefaction)),
        ("is_fire_zone",     _geoms(fire)),
        ("is_steep",         _geoms(slopes)),
        ("in_esa",           _geoms(esa)),
        ("in_mscp",          _geoms(mscp)),
    ]

    # Run all 7 spatial intersection checks in parallel.
    # Previously sequential (hours); now concurrent (~5-7x speedup on multi-core machines).
    t = time.perf_counter()
    logging.info("Running %d spatial intersection checks in parallel...", len(hazard_jobs))

    with ThreadPoolExecutor(max_workers=len(hazard_jobs)) as pool:
        futures = {
            pool.submit(_compute_flag_strtree, parcel_geoms, haz_geoms, col): col
            for col, haz_geoms in hazard_jobs
        }
        for future in as_completed(futures):
            col_name, flags = future.result()
            parcels[col_name] = flags
            logging.info("  [done] %-20s  flagged %d / %d parcels",
                         col_name, int(flags.sum()), len(flags))

    logging.info("All spatial joins complete (%.1fs)", time.perf_counter() - t)

    # Geometry-derived features
    parcels["area_m2"]     = parcels.geometry.area
    parcels["perimeter_m"] = parcels.geometry.length
    cent = parcels.geometry.centroid
    parcels["centroid_x"]  = cent.x
    parcels["centroid_y"]  = cent.y

    logging.info("Feature frame ready — total elapsed: %.1fs", time.perf_counter() - t_total)
    return parcels


# ---------- RISK + MODEL ----------

def compute_rule_risk(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute rule-based risk score from hazard flags (used as XGBoost training labels).
    NOT used for production predictions — see SuitabilityAgent.
    """
    logging.info("Computing rule-based risk score (training labels)...")
    score = sum(gdf.get(col, pd.Series(0, index=gdf.index)) * w
                for col, w in RISK_WEIGHTS.items())
    gdf["rule_risk_score"] = (score * 100).clip(0, 100)
    return gdf


def train_xgboost(gdf: gpd.GeoDataFrame, random_state: int) -> Tuple[gpd.GeoDataFrame, dict]:
    """
    Train XGBoost regression model to predict environmental risk.
    Uses rule_risk_score as target (training labels).
    Stores predictions as xgb_risk_score — primary source for SuitabilityAgent.
    """
    target = "rule_risk_score"
    feature_cols = [
        "has_flood", "has_fault", "has_liquefaction",
        "is_steep", "is_fire_zone", "in_esa", "in_mscp",
        "area_m2", "perimeter_m", "centroid_x", "centroid_y",
    ]

    X = gdf[feature_cols].copy()
    y = gdf[target].values

    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_imp, y, test_size=0.2, random_state=random_state
    )

    model = xgb.XGBRegressor(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="reg:squarederror",
        random_state=random_state,
        n_jobs=-1,
        device="cuda",
        tree_method="hist",
    )

    t = time.perf_counter()
    logging.info("Training XGBoost model (GPU/cuda)...")
    model.fit(X_train, y_train)
    logging.info("XGBoost training complete (%.1fs)", time.perf_counter() - t)

    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2   = float(r2_score(y_test, y_pred))
    logging.info("XGBoost: RMSE=%.2f, R2=%.3f", rmse, r2)

    gdf["xgb_risk_score"] = model.predict(imputer.transform(X)).clip(0, 100)
    return gdf, {"rmse": rmse, "r2": r2, "test_size": int(len(y_test))}


def export_geojson(gdf: gpd.GeoDataFrame, out_path: Path):
    logging.info("Exporting GeoJSON to %s", out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    keep = [
        "rule_risk_score", "xgb_risk_score",
        "has_flood", "has_fault", "has_liquefaction",
        "is_steep", "is_fire_zone", "in_esa", "in_mscp",
        "area_m2", "perimeter_m",
    ]
    for cand in ["APN", "PARCELID", "PARNO", "apn", "parcel_id"]:
        if cand in gdf.columns:
            keep.insert(0, cand)
            break

    t = time.perf_counter()
    out_gdf = gdf[keep + ["geometry"]].to_crs("EPSG:4326")
    out_gdf.to_file(out_path, driver="GeoJSON")
    logging.info("GeoJSON exported (%.1fs)", time.perf_counter() - t)


# ---------- PIPELINE ----------

def run_pipeline(args: argparse.Namespace):
    base = Path(__file__).resolve().parent
    t_total = time.perf_counter()

    gdf = build_feature_frame(
        resolve_path(base, args.parcels_file),
        resolve_path(base, args.flood_file),
        resolve_path(base, args.faults_file),
        resolve_path(base, args.liquefaction_file),
        resolve_path(base, args.fire_file),
        resolve_path(base, args.slopes_file),
        resolve_path(base, args.esa_file),
        resolve_path(base, args.mscp_file),
    )

    gdf = compute_rule_risk(gdf)
    gdf, metrics = train_xgboost(gdf, random_state=args.random_state)
    export_geojson(gdf, resolve_path(base, args.output_geojson))

    metrics_path = resolve_path(base, args.metrics_json)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    logging.info(
        "Pipeline complete. RMSE=%.2f  R2=%.3f  |  Total wall time: %.1fs",
        metrics["rmse"], metrics["r2"], time.perf_counter() - t_total,
    )
    
    


def build_arg_parser():
    p = argparse.ArgumentParser(description="GeoVision Environmental Risk Pipeline")
    p.add_argument("--parcels-file",      default="data/parcels_clipped.shp")
    p.add_argument("--flood-file",        default="data/Floodplain_100_Year_CN_clean.shp")
    p.add_argument("--faults-file",       default="data/Active_Faults_CN.shp")
    p.add_argument("--liquefaction-file", default="data/Potential_Liquefaction_CN.shp")
    p.add_argument("--fire-file",         default="data/Fire_Hazard_Severity_Zones_SD.shp")
    p.add_argument("--slopes-file",       default="data/Steep_Slopes_25_CN.shp")
    p.add_argument("--esa-file",          default="data/Environmentally_Sensitive_Areas.shp")
    p.add_argument("--mscp-file",         default="data/MSCP_Habitrak.shp")
    p.add_argument("--output-geojson",    default="data/outputs/parcels_env_risk.geojson")
    p.add_argument("--metrics-json",      default="data/outputs/env_xgb_metrics.json")
    p.add_argument("--random-state", type=int, default=42)
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    run_pipeline(args)


if __name__ == "__main__":
    main()
