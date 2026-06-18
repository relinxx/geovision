"""Zoning Agent - CORRECTED for actual SanGIS field names."""

import argparse
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

from utils.helpers import resolve_path, load_layer


def assign_zoning(
    parcels: gpd.GeoDataFrame,
    zoning_city: gpd.GeoDataFrame,
    zoning_county: gpd.GeoDataFrame,
    boundaries: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Assign zoning with robust CRS + index_right handling using SanGIS field names."""

    # Store original CRS to restore later
    original_crs = parcels.crs if parcels.crs is not None else "EPSG:3857"

    # Ensure parcels has a CRS
    if parcels.crs is None:
        logger.warning("Parcels have no CRS; setting to EPSG:3857")
        parcels.set_crs("EPSG:3857", inplace=True)

    if boundaries.empty or "Name" not in boundaries.columns:
        logger.warning("Municipal_Boundaries missing or invalid")
        parcels["JURISDICTION"] = "Unknown"
    else:
        # Step 1: Assign jurisdiction
        logger.info("Determining jurisdiction (using 'Name' field)...")

        if "index_right" in parcels.columns:
            parcels = parcels.drop(columns=["index_right"])

        parcels_w_juris = gpd.sjoin(
            parcels,
            boundaries[["Name", "geometry"]],
            how="left",
            predicate="intersects",
        )

        parcels_w_juris.rename(columns={"Name": "JURISDICTION"}, inplace=True)
        parcels_w_juris = (
            parcels_w_juris.groupby(parcels_w_juris.index)
            .first()
            .reset_index(drop=True)
        )

        # Restore CRS after groupby (can get lost)
        if parcels_w_juris.crs is None:
            parcels_w_juris.set_crs(original_crs, inplace=True)

        parcels = parcels_w_juris

    # Step 2: Split city vs county
    city_mask = parcels["JURISDICTION"].astype(str).str.contains(
        "City", na=False, case=False
    )
    city_parcels = parcels[city_mask].copy()
    county_parcels = parcels[~city_mask].copy()

    # Explicitly set CRS on copies
    if city_parcels.crs is None and len(city_parcels) > 0:
        city_parcels.set_crs(original_crs, inplace=True)
    if county_parcels.crs is None and len(county_parcels) > 0:
        county_parcels.set_crs(original_crs, inplace=True)

    logger.info(
        "Found %d city parcels, %d county parcels", len(city_parcels), len(county_parcels)
    )

    # Step 3: Join city parcels with Zoning_Base_SD (using ZONE_NAME)
    if (
        not city_parcels.empty
        and not zoning_city.empty
        and "ZONE_NAME" in zoning_city.columns
    ):
        logger.info("Joining city parcels with Zoning_Base_SD (using 'ZONE_NAME')...")

        if "index_right" in city_parcels.columns:
            city_parcels = city_parcels.drop(columns=["index_right"])

        city_zoned = gpd.sjoin(
            city_parcels,
            zoning_city[["ZONE_NAME", "geometry"]],
            how="left",
            predicate="intersects",
        )
        city_zoned.rename(columns={"ZONE_NAME": "ZONING_CODE"}, inplace=True)
        city_zoned = (
            city_zoned.groupby(city_zoned.index).first().reset_index(drop=True)
        )

        # Restore CRS
        if city_zoned.crs is None:
            city_zoned.set_crs(original_crs, inplace=True)

        city_zoned["MAX_HEIGHT"] = None
        city_zoned["MAX_FAR"] = None
        city_zoned["MIN_LOT_SIZE"] = None
    else:
        city_zoned = city_parcels.copy()
        if "ZONING_CODE" not in city_zoned.columns:
            city_zoned["ZONING_CODE"] = None
        for col in ["MAX_HEIGHT", "MAX_FAR", "MIN_LOT_SIZE"]:
            if col not in city_zoned.columns:
                city_zoned[col] = None

    # Step 4: Join county parcels with Zoning_Unincorporated
    if not county_parcels.empty and not zoning_county.empty:
        county_fields = ["USEREG", "geometry"]

        for field in ["MAXFLR", "HEIGHT", "DENSITY", "LOT"]:
            if field in zoning_county.columns:
                county_fields.append(field)

        logger.info(
            "Joining county parcels with Zoning_Unincorporated (fields: %s)...",
            county_fields,
        )

        if "index_right" in county_parcels.columns:
            county_parcels = county_parcels.drop(columns=["index_right"])

        county_zoned = gpd.sjoin(
            county_parcels,
            zoning_county[county_fields],
            how="left",
            predicate="intersects",
        )

        rename_map = {
            "USEREG": "ZONING_CODE",
            "HEIGHT": "MAX_HEIGHT",
            "MAXFLR": "MAX_FAR",
            "LOT": "MIN_LOT_SIZE",
        }
        county_zoned.rename(
            columns={k: v for k, v in rename_map.items() if k in county_zoned.columns},
            inplace=True,
        )
        county_zoned = (
            county_zoned.groupby(county_zoned.index).first().reset_index(drop=True)
        )

        # Restore CRS
        if county_zoned.crs is None:
            county_zoned.set_crs(original_crs, inplace=True)

        for col in ["MAX_HEIGHT", "MAX_FAR", "MIN_LOT_SIZE"]:
            if col not in county_zoned.columns:
                county_zoned[col] = None
    else:
        county_zoned = county_parcels.copy()
        if "ZONING_CODE" not in county_zoned.columns:
            county_zoned["ZONING_CODE"] = None
        for col in ["MAX_HEIGHT", "MAX_FAR", "MIN_LOT_SIZE"]:
            if col not in county_zoned.columns:
                county_zoned[col] = None

    # Step 5: Combine
    common_cols = list(set(city_zoned.columns) & set(county_zoned.columns))

    parcels_zoned = pd.concat(
        [city_zoned[common_cols], county_zoned[common_cols]], ignore_index=True
    )

    # Final CRS restore
    if parcels_zoned.crs is None:
        parcels_zoned.set_crs(original_crs, inplace=True)

    return parcels_zoned


def add_general_plan(parcels: gpd.GeoDataFrame, gp_layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add General Plan using GP_LU_DESC field as GP_LAND_USE.

    - Drops any pre-existing index_right to avoid sjoin collisions
    - Ensures CRS on parcels before spatial join
    - Restores CRS after groupby/reset_index if it gets lost
    """
    # If layer missing or doesn't have expected field, ensure GP_LAND_USE exists and return
    if gp_layer.empty or "GP_LU_DESC" not in gp_layer.columns:
        logger.warning("General Plan layer missing or invalid; GP_LU_DESC not found")
        parcels = parcels.copy()
        if "GP_LAND_USE" not in parcels.columns:
            parcels["GP_LAND_USE"] = None
        return parcels

    logger.info("Adding General Plan land use (using 'GP_LU_DESC')...")

    # Clean up sjoin bookkeeping
    if "index_right" in parcels.columns:
        parcels = parcels.drop(columns=["index_right"])

    # Ensure CRS is present and matches GP layer
    if parcels.crs is None:
        logger.warning("Parcels have no CRS before GP join; setting to match GP layer")
        parcels = parcels.set_crs(gp_layer.crs, allow_override=True)
    elif parcels.crs != gp_layer.crs:
        parcels = parcels.to_crs(gp_layer.crs)

    joined = gpd.sjoin(
        parcels,
        gp_layer[["GP_LU_DESC", "geometry"]],
        how="left",
        predicate="intersects",
    )

    joined.rename(columns={"GP_LU_DESC": "GP_LAND_USE"}, inplace=True)
    joined = joined.groupby(joined.index).first().reset_index(drop=True)

    # Restore CRS if lost after groupby
    if joined.crs is None:
        joined.set_crs(parcels.crs, inplace=True)

    return joined


def export_zoning_geojson(gdf: gpd.GeoDataFrame, out_path: Path):
    logger.info("Exporting zoning GeoJSON to %s", out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    keep = [
        "JURISDICTION",
        "ZONING_CODE",
        "GP_LAND_USE",
        "MAX_HEIGHT",
        "MAX_FAR",
        "MIN_LOT_SIZE",
    ]

    # Keep an APN-like field if present
    for apn_field in ["APN", "PARCELID", "PARNO"]:
        if apn_field in gdf.columns and apn_field not in keep:
            keep.insert(0, apn_field)
            break

    existing_cols = [c for c in keep if c in gdf.columns]
    out_gdf = gdf[existing_cols + ["geometry"]].copy()

    # Ensure CRS exists before reprojection
    if out_gdf.crs is None:
        logger.warning(
            "Output GeoDataFrame has no CRS; setting to EPSG:3857 before export"
        )
        out_gdf.set_crs("EPSG:3857", inplace=True)

    out_gdf = out_gdf.to_crs("EPSG:4326")
    out_gdf.to_file(out_path, driver="GeoJSON")

    total = len(out_gdf)
    logger.info("\n" + "=" * 50)
    logger.info("ZONING PIPELINE RESULTS:")
    logger.info("=" * 50)
    logger.info("Total parcels: %d", total)

    if "JURISDICTION" in out_gdf.columns:
        with_juris = out_gdf["JURISDICTION"].notna().sum()
        logger.info(
            "Parcels with jurisdiction: %d (%.1f%%)",
            with_juris,
            100 * with_juris / total if total else 0,
        )

    if "ZONING_CODE" in out_gdf.columns:
        with_zoning = out_gdf["ZONING_CODE"].notna().sum()
        logger.info(
            "Parcels with zoning code: %d (%.1f%%)",
            with_zoning,
            100 * with_zoning / total if total else 0,
        )

    if "GP_LAND_USE" in out_gdf.columns:
        with_gp = out_gdf["GP_LAND_USE"].notna().sum()
        logger.info(
            "Parcels with GP land use: %d (%.1f%%)",
            with_gp,
            100 * with_gp / total if total else 0,
        )

    if "MAX_HEIGHT" in out_gdf.columns:
        with_height = out_gdf["MAX_HEIGHT"].notna().sum()
        logger.info(
            "Parcels with max height: %d (%.1f%%)",
            with_height,
            100 * with_height / total if total else 0,
        )

    logger.info("=" * 50 + "\n")


def run_zoning_pipeline(args: argparse.Namespace):
    base = Path(__file__).resolve().parent
    metric_crs = "EPSG:3857"

    parcels = load_layer(
        resolve_path(base, args.parcels_file),
        "Parcels",
        metric_crs,
    )

    # Ensure parcels CRS is consistent
    if parcels.crs is None:
        logger.warning("Parcels loaded with no CRS; setting to %s", metric_crs)
        parcels.set_crs(metric_crs, inplace=True)
    elif parcels.crs != metric_crs:
        parcels = parcels.to_crs(metric_crs)

    # Optional: filter to APNs present in env baseline to maximize merge coverage
    try:
        repo_root = base.parent.parent.parent
        env_path = repo_root / "frontend" / "public" / "parcels_env_risk_clipped.geojson"
        if env_path.exists():
            logger.info("Filtering parcels to APNs present in env baseline at %s", env_path)
            env_gdf = gpd.read_file(env_path)
            # Determine APN field names
            def find_apn_field(cols):
                for c in ("APN", "PARCELID", "PARNO"):
                    if c in cols:
                        return c
                return None

            env_apn_field = find_apn_field(env_gdf.columns)
            parcels_apn_field = find_apn_field(parcels.columns)

            if env_apn_field and parcels_apn_field:
                env_keys = (
                    env_gdf[env_apn_field]
                    .astype(str)
                    .str.upper()
                    .str.strip()
                    .dropna()
                    .unique()
                )
                before = len(parcels)
                parcels = parcels[parcels[parcels_apn_field].astype(str).str.upper().str.strip().isin(env_keys)]
                parcels = parcels.reset_index(drop=True)
                if parcels.crs is None:
                    parcels.set_crs(metric_crs, inplace=True)
                logger.info("Filtered parcels by env APNs: %d -> %d", before, len(parcels))
            else:
                logger.warning("Could not find APN field in env or parcels; skipping APN-based filter")
        else:
            logger.info("Env baseline not found at %s; skipping APN filter", env_path)
    except Exception as e:
        logger.warning("Failed APN filtering step: %s", e)

    # Downsample only if still very large; keep enough to exceed zoning coverage target
    if len(parcels) > 20000:
        original_len = len(parcels)
        parcels = parcels.sample(n=20000, random_state=42).reset_index(drop=True)
        if parcels.crs is None:
            parcels.set_crs(metric_crs, inplace=True)
        logger.info("Downsampling from %d to 20000 parcels for speed testing", original_len)

    zoning_city = load_layer(
        resolve_path(base, args.zoning_city_file),
        "Zoning_Base_SD",
        metric_crs,
    )

    zoning_county = load_layer(
        resolve_path(base, args.zoning_county_file),
        "Zoning_Unincorporated",
        metric_crs,
    )

    boundaries = load_layer(
        resolve_path(base, args.boundaries_file),
        "Municipal_Boundaries",
        metric_crs,
    )

    gp_layer = load_layer(
        resolve_path(base, args.gp_file),
        "General_Plan_Land_Use",
        metric_crs,
    )

    parcels = assign_zoning(parcels, zoning_city, zoning_county, boundaries)
    parcels = add_general_plan(parcels, gp_layer)

    export_zoning_geojson(parcels, resolve_path(base, args.output_geojson))

    logger.info("Zoning pipeline complete.")


def build_arg_parser():
    p = argparse.ArgumentParser(
        description="GeoVision Zoning Agent - CORRECTED for SanGIS fields"
    )
    p.add_argument("--parcels-file", default="../environment_agent/data/parcels_clipped.shp")
    # Your data lives under src/data relative to this module
    p.add_argument("--zoning-city-file", default="src/data/Zoning_Base_SD.geojson")
    p.add_argument("--zoning-county-file", default="src/data/Zoning_Unincorporated.geojson")
    p.add_argument("--boundaries-file", default="src/data/Municipal_Boundaries.geojson")
    p.add_argument("--gp-file", default="src/data/General_Plan_Land_Use_SD.geojson")
    p.add_argument("--output-geojson", default="data/outputs/parcels_zoning.geojson")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    run_zoning_pipeline(args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    main()
