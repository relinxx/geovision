from __future__ import annotations

from services.redis_store import RedisStore


class FakeRedisClient:
    def __init__(self):
        self.calls = []

    def geoadd(self, key, values):
        if len(values) % 3 != 0:
            raise ValueError("GEOADD requires places with lon, lat and name values")
        self.calls.append(("geoadd", key, values))
        return 1

    def geosearch(self, **kwargs):
        self.calls.append(("geosearch", kwargs))
        return [("parcel-1", 12.3), ("parcel-2", 45.6)]


def test_geo_helpers_namespace_keys_and_delegate_calls():
    store = object.__new__(RedisStore)
    store._prefix = "geovision"
    store._client = FakeRedisClient()

    store.geoadd("parcels:geo", -117.0, 32.8, "parcel-1")
    results = store.geosearch_by_member("parcels:geo", "parcel-1", radius_m=250, limit=10)

    assert store._client.calls[0] == (
        "geoadd",
        "geovision:parcels:geo",
        (-117.0, 32.8, "parcel-1"),
    )
    assert store._client.calls[1][0] == "geosearch"
    assert store._client.calls[1][1]["name"] == "geovision:parcels:geo"
    assert store._client.calls[1][1]["member"] == "parcel-1"
    assert store._client.calls[1][1]["unit"] == "m"
    assert store._client.calls[1][1]["radius"] == 250
    assert store._client.calls[1][1]["sort"] == "ASC"
    assert store._client.calls[1][1]["count"] == 10
    assert store._client.calls[1][1]["withdist"] is True
    assert results == [("parcel-1", 12.3), ("parcel-2", 45.6)]
