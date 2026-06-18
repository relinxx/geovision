import asyncio
import copy
import unittest

from services.job_store import JobStore


class FakeRedisStore:
    def __init__(self):
        self.json_values: dict[str, dict] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.expirations: dict[str, int] = {}

    def set_json(self, key: str, value: dict, ttl_seconds: int | None = None) -> None:
        self.json_values[key] = copy.deepcopy(value)
        if ttl_seconds is not None:
            self.expirations[key] = int(ttl_seconds)

    def get_json(self, key: str):
        value = self.json_values.get(key)
        return copy.deepcopy(value) if value is not None else None

    def delete(self, key: str) -> None:
        self.json_values.pop(key, None)

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        bucket = self.sorted_sets.setdefault(key, {})
        bucket.update(mapping)

    def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, {}))

    def zrange(self, key: str, start: int, end: int) -> list[str]:
        bucket = self.sorted_sets.get(key, {})
        ordered = [item[0] for item in sorted(bucket.items(), key=lambda item: (item[1], item[0]))]
        if end == -1:
            return ordered[start:]
        return ordered[start : end + 1]

    def zrem(self, key: str, *values: str) -> None:
        bucket = self.sorted_sets.setdefault(key, {})
        for value in values:
            bucket.pop(value, None)

    def expire(self, key: str, ttl_seconds: int) -> None:
        self.expirations[key] = int(ttl_seconds)


class TestJobStore(unittest.TestCase):
    def test_in_memory_job_store_round_trip(self):
        async def run_case():
            store = JobStore(redis_store=None)
            await store.create_job("job-1")
            await store.update_step("job-1", "environment", "completed")
            await store.update_job("job-1", status="running", progress=40, stage="zoning")
            job = await store.get_job("job-1")
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job.status, "running")
            self.assertEqual(job.progress, 40)
            self.assertEqual(job.steps.environment, "completed")

        asyncio.run(run_case())

    def test_redis_backed_job_store_round_trip(self):
        async def run_case():
            fake_redis = FakeRedisStore()
            store = JobStore(redis_store=fake_redis)
            await store.create_job("job-redis")
            await store.update_job(
                "job-redis",
                status="completed",
                progress=100,
                stage="completed",
                result={"ok": True},
            )
            await store.update_step("job-redis", "merge", "completed")

            job = await store.get_job("job-redis")
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.result, {"ok": True})
            self.assertEqual(job.steps.merge, "completed")

            jobs = await store.list_jobs()
            self.assertIn("job-redis", jobs)
            self.assertIn("orchestrator:job:job-redis", fake_redis.json_values)
            self.assertIn("orchestrator:jobs:index", fake_redis.sorted_sets)

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
