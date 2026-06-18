import unittest

from fastapi.testclient import TestClient

from main import app


class TestCorsDefaults(unittest.TestCase):
    def test_allows_vite_fallback_port_for_auth_preflight(self) -> None:
        with TestClient(app) as client:
            response = client.options(
                "/auth/login",
                headers={
                    "Origin": "http://localhost:5174",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5174",
        )


if __name__ == "__main__":
    unittest.main()
