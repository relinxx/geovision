from __future__ import annotations

import unittest

from ._helpers import BACKEND_DIR  # noqa: F401

from agent.spatial_agent.spatial.geo import (
    build_adjacency_from_geojson,
    build_parcels_from_geojson,
)


class TestGeoParcelIdResolution(unittest.TestCase):
    def test_prefers_property_ids_over_feature_id(self) -> None:
        features = [
            {
                "type": "Feature",
                "id": 101,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
                "properties": {
                    "APN": "APN-0001",
                    "residential": 0.8,
                },
            }
        ]

        parcels = build_parcels_from_geojson(features)
        self.assertEqual(len(parcels), 1)
        self.assertEqual(parcels[0].parcel_id, "APN-0001")

    def test_falls_back_to_feature_id_when_no_property_id(self) -> None:
        features = [
            {
                "type": "Feature",
                "id": 202,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
                "properties": {},
            }
        ]

        parcels = build_parcels_from_geojson(features)
        self.assertEqual(len(parcels), 1)
        self.assertEqual(parcels[0].parcel_id, "202")

    def test_invalid_geometry_does_not_break_adjacency(self) -> None:
        # Self-intersecting bow-tie polygon (invalid by design).
        invalid = {
            "type": "Feature",
            "id": "bad-1",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
            },
            "properties": {"APN": "BAD-1"},
        }
        valid = {
            "type": "Feature",
            "id": "ok-1",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
            },
            "properties": {"APN": "OK-1"},
        }

        parcels = build_parcels_from_geojson([invalid, valid])
        self.assertEqual(len(parcels), 2)

        adjacency = build_adjacency_from_geojson([invalid, valid], adjacency_predicate="touches")
        self.assertIn(0, adjacency)
        self.assertIn(1, adjacency)


if __name__ == "__main__":
    unittest.main()
