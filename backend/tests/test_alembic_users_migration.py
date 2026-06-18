from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0001_create_users_table.py"
    )
    spec = importlib.util.spec_from_file_location("users_migration_0001", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module from {migration_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAlembicUsersMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_migration_module()

    def test_upgrade_skips_create_when_users_table_already_exists(self) -> None:
        inspector = MagicMock()
        inspector.has_table.return_value = True

        with (
            patch.object(self.module.op, "get_bind", return_value=object()),
            patch.object(self.module.sa, "inspect", return_value=inspector),
            patch.object(self.module.op, "create_table") as mock_create_table,
            patch.object(self.module.op, "create_index") as mock_create_index,
        ):
            self.module.upgrade()

        mock_create_table.assert_not_called()
        mock_create_index.assert_not_called()

    def test_upgrade_creates_users_table_for_fresh_database(self) -> None:
        inspector = MagicMock()
        inspector.has_table.return_value = False

        with (
            patch.object(self.module.op, "get_bind", return_value=object()),
            patch.object(self.module.sa, "inspect", return_value=inspector),
            patch.object(self.module.op, "create_table") as mock_create_table,
            patch.object(self.module.op, "create_index") as mock_create_index,
        ):
            self.module.upgrade()

        mock_create_table.assert_called_once()
        self.assertEqual(mock_create_index.call_count, 2)


if __name__ == "__main__":
    unittest.main()
