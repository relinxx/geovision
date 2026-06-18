import unittest
from unittest.mock import patch

import database

class TestDatabase(unittest.TestCase):
    def test_init_db_runs_alembic_upgrade_head(self) -> None:
        with patch("database.command.upgrade") as mock_upgrade:
            database.init_db()

        mock_upgrade.assert_called_once()
        args, kwargs = mock_upgrade.call_args
        if args:
            self.assertEqual(args[-1], "head")
        else:
            self.assertEqual(kwargs.get("revision"), "head")


if __name__ == "__main__":
    unittest.main()
