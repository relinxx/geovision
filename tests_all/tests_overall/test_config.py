import os
import unittest
from unittest.mock import patch

from config import get_settings, reset_settings_cache_for_tests


class TestConfig(unittest.TestCase):
    def tearDown(self) -> None:
        reset_settings_cache_for_tests()

    def test_builds_database_and_redis_urls_from_component_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "POSTGRES_HOST": "db",
                "POSTGRES_PORT": "5433",
                "POSTGRES_DB": "geovision_test",
                "POSTGRES_USER": "planner",
                "POSTGRES_PASSWORD": "secret",
                "REDIS_HOST": "cache",
                "REDIS_PORT": "6380",
                "REDIS_DB": "2",
                "JWT_SECRET_KEY": "test-secret",
            },
            clear=False,
        ):
            reset_settings_cache_for_tests()
            settings = get_settings()

        self.assertEqual(
            settings.database_url,
            "postgresql://planner:secret@db:5433/geovision_test",
        )
        self.assertEqual(settings.redis_url, "redis://cache:6380/2")
        self.assertEqual(settings.jwt_secret_key, "test-secret")

    def test_database_url_env_takes_precedence(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "DATABASE_URL": "postgresql://user:pass@pg:5432/customdb",
                "JWT_SECRET_KEY": "test-secret",
            },
            clear=False,
        ):
            reset_settings_cache_for_tests()
            settings = get_settings()

        self.assertEqual(settings.database_url, "postgresql://user:pass@pg:5432/customdb")


if __name__ == "__main__":
    unittest.main()
