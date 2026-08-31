from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "migrate-config.py"
SPEC = importlib.util.spec_from_file_location("migrate_config", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfigMigrationTest(unittest.TestCase):
    def test_old_defaults_are_increased(self) -> None:
        config = {
            "ensure_lock_timeout_seconds": 1800,
            "providers": {"vast": {"start_timeout_seconds": 1800}},
        }
        self.assertTrue(MODULE.migrate(config))
        self.assertEqual(config["ensure_lock_timeout_seconds"], 7200)
        self.assertEqual(config["providers"]["vast"]["start_timeout_seconds"], 7200)

    def test_custom_values_are_preserved(self) -> None:
        config = {
            "ensure_lock_timeout_seconds": 3600,
            "providers": {"vast": {"start_timeout_seconds": 9000}},
        }
        self.assertFalse(MODULE.migrate(config))
        self.assertEqual(config["ensure_lock_timeout_seconds"], 3600)
        self.assertEqual(config["providers"]["vast"]["start_timeout_seconds"], 9000)


if __name__ == "__main__":
    unittest.main()
