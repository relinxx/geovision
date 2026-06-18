"""
GeoJSON Output Builder

Merges ML model predictions back into the original GeoJSON FeatureCollection
for frontend map visualization.

This module handles the transformation from:
- Model predictions (DataFrame/list of dicts with scores)
- Original GeoJSON features (with geometry and properties)

To:
- Enhanced GeoJSON with suitability scores in properties
- Ready for map rendering and visualization

Workflow:
    Frontend sends parcels -> Backend adds scores -> Frontend displays on map
"""
from typing import Any, Dict, List


def build_output_geojson(
    input_features: List[Dict[str, Any]], predictions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Build a GeoJSON FeatureCollection with suitability scores attached.

    Parameters
    ----------
    input_features:
        List of GeoJSON Feature dicts from the frontend's ParcelGeoJSONExport.
        Each feature should have:
          - "id": parcel identifier
          - "geometry": { "type": "Polygon", "coordinates": [...] }
          - "properties": { "centroid": {...}, ... }

    predictions:
        List of prediction dicts, each with:
          - "parcel_id": matches a feature "id"
          - "residential": float score (0-1)
          - "commercial": float score (0-1)
          - (or any other score keys the model produces)

    Returns
    -------
    dict
        GeoJSON FeatureCollection matching the frontend's ParcelGeoJSONExport
        structure, with prediction scores merged into each feature's properties.
    """
    # Map predictions by parcel_id for fast lookup
    pred_map: Dict[str, Dict[str, Any]] = {p["parcel_id"]: p for p in predictions}

    output_features: List[Dict[str, Any]] = []

    for feature in input_features:
        pid = feature.get("id")
        if pid is None or str(pid).strip() == "":
            continue  # Skip features without IDs

        # Get prediction scores for this parcel (default to empty dict if missing)
        pred = pred_map.get(pid, {})

        # Merge original properties with prediction scores
        # Exclude "parcel_id" from pred since it's redundant with feature "id"
        pred_scores = {k: v for k, v in pred.items() if k != "parcel_id"}

        new_feature: Dict[str, Any] = {
            "type": "Feature",
            "id": pid,
            "geometry": feature.get("geometry", {}),
            "properties": {
                **feature.get("properties", {}),
                **pred_scores,  # Merge scores into properties
            },
        }

        output_features.append(new_feature)

    return {
        "type": "FeatureCollection",
        "features": output_features,
    }

