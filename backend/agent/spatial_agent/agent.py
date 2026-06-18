"""Spatial Agent - Generates spatial data and geometries."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import geopandas as gpd
import numpy as np
from shapely import STRtree
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union, voronoi_diagram

logger = logging.getLogger(__name__)

_METRIC_CRS = "EPSG:3857"
_GEO_CRS = "EPSG:4326"


class SpatialAgent:
    """Agent responsible for spatial data generation and manipulation."""

    def __init__(self) -> None:
        logger.info("SpatialAgent initialized")

    def generate(
        self,
        parcels: List[Dict[str, Any]],
        generation_type: str = "parcel_subdivision",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate spatial data based on input parcels.

        generation_type options: parcel_subdivision | buffer_zones | voronoi | grid
        """
        if parameters is None:
            parameters = {}

        started_at = time.perf_counter()
        logger.info("Generating spatial data: %s for %d parcels", generation_type, len(parcels))

        dispatch = {
            "parcel_subdivision": self._subdivide_parcels,
            "buffer_zones":       self._create_buffer_zones,
            "voronoi":            self._generate_voronoi,
            "grid":               self._generate_grid,
        }
        handler = dispatch.get(generation_type)
        if handler is None:
            raise ValueError(f"Unknown generation type: {generation_type}")

        result = handler(parcels, parameters)
        logger.info(
            "Generation completed | type=%s | features=%d | elapsed=%.4fs",
            generation_type, len(result.get("features", [])), time.perf_counter() - started_at,
        )
        return result

    # ------------------------------------------------------------------
    # Parcel subdivision
    # ------------------------------------------------------------------

    def _subdivide_parcels(
        self,
        parcels: List[Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Subdivide parcels into smaller grid cells."""
        started_at = time.perf_counter()
        target_area = float(parameters.get("target_area", 1000.0))
        min_area    = float(parameters.get("min_area",    100.0))
        if target_area <= 0:
            raise ValueError("target_area must be greater than zero")
        if min_area <= 0:
            raise ValueError("min_area must be greater than zero")
        if min_area > target_area:
            raise ValueError("min_area cannot exceed target_area")

        gdf = gpd.GeoDataFrame.from_features(parcels, crs=_GEO_CRS).to_crs(_METRIC_CRS)
        prop_cols = [c for c in gdf.columns if c != "geometry"]

        subdivided_geoms: list[Any] = []
        subdivided_props: list[dict] = []

        for idx, row in gdf.iterrows():
            geom     = row.geometry
            area_m2  = geom.area
            base_props = {c: row[c] for c in prop_cols}

            if area_m2 < target_area:
                subdivided_geoms.append(geom)
                subdivided_props.append(base_props)
                continue

            minx, miny, maxx, maxy = geom.bounds
            width  = maxx - minx
            height = maxy - miny
            n = max(1, int(np.sqrt(area_m2 / target_area)))
            cw = width  / n
            ch = height / n

            for i in range(n):
                for j in range(n):
                    cell = Polygon([
                        (minx + j * cw,       miny + i * ch),
                        (minx + (j + 1) * cw, miny + i * ch),
                        (minx + (j + 1) * cw, miny + (i + 1) * ch),
                        (minx + j * cw,       miny + (i + 1) * ch),
                    ])
                    clipped = geom.intersection(cell)
                    if getattr(clipped, "area", 0.0) >= min_area:
                        props = dict(base_props)
                        props["subdivision_id"] = f"{idx}_{len(subdivided_geoms)}"
                        props["parent_id"]       = idx
                        subdivided_geoms.append(clipped)
                        subdivided_props.append(props)

        # Batch-reproject all output geometries in one call
        result_gdf = gpd.GeoDataFrame(subdivided_props, geometry=subdivided_geoms, crs=_METRIC_CRS)
        result_gdf = result_gdf.to_crs(_GEO_CRS)

        features = [
            {"type": "Feature", "properties": row.drop("geometry").to_dict(),
             "geometry": row.geometry.__geo_interface__}
            for _, row in result_gdf.iterrows()
        ]
        logger.debug(
            "Subdivision completed | output=%d | elapsed=%.4fs",
            len(features), time.perf_counter() - started_at,
        )
        return {"type": "FeatureCollection", "features": features}

    # ------------------------------------------------------------------
    # Buffer zones
    # ------------------------------------------------------------------

    def _create_buffer_zones(
        self,
        parcels: List[Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create buffer zones around parcels."""
        started_at = time.perf_counter()
        distance = float(parameters.get("distance", 50.0))
        if distance <= 0:
            raise ValueError("distance must be greater than zero")
        units = parameters.get("units", "meters")

        gdf = gpd.GeoDataFrame.from_features(parcels, crs=_GEO_CRS).to_crs(_METRIC_CRS)
        buffered = gdf.copy()
        buffered.geometry = gdf.geometry.buffer(distance)
        buffered = buffered.to_crs(_GEO_CRS)

        features = [
            {
                "type": "Feature",
                "properties": {**row.drop("geometry").to_dict(), "buffer_distance": distance, "buffer_units": units},
                "geometry": row.geometry.__geo_interface__,
            }
            for _, row in buffered.iterrows()
        ]
        logger.debug("Buffer completed | output=%d | elapsed=%.4fs", len(features), time.perf_counter() - started_at)
        return {"type": "FeatureCollection", "features": features}

    # ------------------------------------------------------------------
    # Voronoi
    # ------------------------------------------------------------------

    def _generate_voronoi(
        self,
        parcels: List[Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate Voronoi diagrams from parcel centroids."""
        started_at = time.perf_counter()

        gdf = gpd.GeoDataFrame.from_features(parcels, crs=_GEO_CRS)
        if gdf.empty:
            return {"type": "FeatureCollection", "features": []}

        gdf = gdf.to_crs(_METRIC_CRS)
        centroids = gdf.geometry.centroid
        indexed_points = [(idx, pt) for idx, pt in centroids.items() if pt and not pt.is_empty]
        if not indexed_points:
            return {"type": "FeatureCollection", "features": []}

        extent    = unary_union(gdf.geometry)
        clip_geom = extent.envelope if (extent and not extent.is_empty) else (
            MultiPoint([pt for _, pt in indexed_points]).envelope
        )

        voronoi_cells: dict[Any, Any] = {}
        if len(indexed_points) == 1:
            only_idx = indexed_points[0][0]
            voronoi_cells[only_idx] = gdf.loc[only_idx].geometry
        else:
            points_geom  = MultiPoint([pt for _, pt in indexed_points])
            voronoi_geom = voronoi_diagram(points_geom, envelope=clip_geom, edges=False)
            cells = [
                cell.intersection(clip_geom)
                for cell in getattr(voronoi_geom, "geoms", [])
                if cell and not cell.is_empty
            ]
            for idx, point in indexed_points:
                matched = None
                for cell in cells:
                    if cell.covers(point):
                        matched = cell if matched is None else matched.union(cell)
                if matched is None and cells:
                    matched = min(cells, key=lambda c: c.distance(point))
                if not matched or matched.is_empty:
                    matched = gdf.loc[idx].geometry
                voronoi_cells[idx] = matched.intersection(clip_geom)

        # Collect result geometries and batch-reproject once
        result_geoms  = []
        result_props  = []
        prop_cols     = [c for c in gdf.columns if c != "geometry"]
        for i, (idx, row) in enumerate(gdf.iterrows()):
            cell = voronoi_cells.get(idx, row.geometry)
            if not cell or cell.is_empty:
                continue
            result_geoms.append(cell)
            result_props.append({**{c: row[c] for c in prop_cols}, "voronoi_region": i})

        result_gdf = gpd.GeoDataFrame(result_props, geometry=result_geoms, crs=_METRIC_CRS).to_crs(_GEO_CRS)
        features = [
            {"type": "Feature", "properties": row.drop("geometry").to_dict(),
             "geometry": row.geometry.__geo_interface__}
            for _, row in result_gdf.iterrows()
        ]
        logger.debug("Voronoi completed | output=%d | elapsed=%.4fs", len(features), time.perf_counter() - started_at)
        return {"type": "FeatureCollection", "features": features}

    # ------------------------------------------------------------------
    # Grid
    # ------------------------------------------------------------------

    def _generate_grid(
        self,
        parcels: List[Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a grid overlay, using STRtree for O(n log n) intersection testing."""
        started_at = time.perf_counter()
        cell_size  = float(parameters.get("cell_size", 100.0))
        if cell_size <= 0:
            raise ValueError("cell_size must be greater than zero")
        cell_units = parameters.get("cell_units", "meters")

        gdf = gpd.GeoDataFrame.from_features(parcels, crs=_GEO_CRS).to_crs(_METRIC_CRS)
        minx, miny, maxx, maxy = gdf.total_bounds

        # Build all candidate cells
        xs = np.arange(minx, maxx, cell_size)
        ys = np.arange(miny, maxy, cell_size)
        all_cells = [
            Polygon([(x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)])
            for x in xs for y in ys
        ]

        if not all_cells:
            return {"type": "FeatureCollection", "features": []}

        # STRtree bulk query: find which cells intersect any parcel geometry
        parcel_geoms = list(gdf.geometry)
        cell_tree    = STRtree(all_cells)
        # query returns (cell_idx, parcel_idx) pairs for bbox-overlapping pairs
        result = cell_tree.query(parcel_geoms, predicate="intersects")
        # result[1] = cell indices that hit at least one parcel
        if result.size == 0:
            return {"type": "FeatureCollection", "features": []}

        hit_cell_indices = np.unique(result[1])
        hit_cells = [all_cells[i] for i in hit_cell_indices]

        # Batch-reproject hit cells in one GeoSeries call
        hit_gdf = gpd.GeoDataFrame(
            [{"cell_id": i, "cell_size": cell_size, "cell_units": cell_units} for i in range(len(hit_cells))],
            geometry=hit_cells, crs=_METRIC_CRS,
        ).to_crs(_GEO_CRS)

        features = [
            {"type": "Feature", "properties": row.drop("geometry").to_dict(),
             "geometry": row.geometry.__geo_interface__}
            for _, row in hit_gdf.iterrows()
        ]
        logger.debug(
            "Grid completed | tested=%d | hit=%d | elapsed=%.4fs",
            len(all_cells), len(features), time.perf_counter() - started_at,
        )
        return {"type": "FeatureCollection", "features": features}
