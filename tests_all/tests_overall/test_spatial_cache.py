import unittest

from services.spatial_cache import build_spatial_optimize_cache_key, normalize_target_mix


def make_feature(parcel_id: str, risk: float) -> dict:
    return {
        "type": "Feature",
        "id": parcel_id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        },
        "properties": {
            "APN": parcel_id,
            "xgb_risk_score": risk,
            "area_m2": 1000,
        },
    }


class TestSpatialCacheHelpers(unittest.TestCase):
    def test_normalize_target_mix_filters_and_normalizes(self):
        normalized = normalize_target_mix(
            {
                "Residential": 3,
                "commercial": 1,
                "ignored_zero": 0,
                "ignored_bad": "x",
            }
        )
        self.assertEqual(set(normalized.keys()), {"residential", "commercial"})
        self.assertAlmostEqual(normalized["residential"], 0.75)
        self.assertAlmostEqual(normalized["commercial"], 0.25)

    def test_cache_key_is_stable_for_equivalent_requests(self):
        features_a = [make_feature("A-1", 0.1), make_feature("B-2", 0.2)]
        features_b = [make_feature("B-2", 0.2), make_feature("A-1", 0.1)]

        key_a = build_spatial_optimize_cache_key(
            features=features_a,
            num_output_plans=5,
            population_size=30,
            generations=20,
            include_adjacency=True,
            adjacency_predicate="touches",
            target_mix=normalize_target_mix({"commercial": 1, "residential": 3}),
        )
        key_b = build_spatial_optimize_cache_key(
            features=features_b,
            num_output_plans=5,
            population_size=30,
            generations=20,
            include_adjacency=True,
            adjacency_predicate="touches",
            target_mix=normalize_target_mix({"residential": 3, "commercial": 1}),
        )

        self.assertEqual(key_a, key_b)

    def test_cache_key_changes_when_effective_settings_change(self):
        features = [make_feature("A-1", 0.1)]
        base_key = build_spatial_optimize_cache_key(
            features=features,
            num_output_plans=5,
            population_size=30,
            generations=20,
            include_adjacency=True,
            adjacency_predicate="touches",
            target_mix={},
        )
        changed_key = build_spatial_optimize_cache_key(
            features=features,
            num_output_plans=5,
            population_size=40,
            generations=20,
            include_adjacency=True,
            adjacency_predicate="touches",
            target_mix={},
        )

        self.assertNotEqual(base_key, changed_key)


if __name__ == "__main__":
    unittest.main()
