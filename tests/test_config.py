from __future__ import annotations

import unittest

from abliteration_station.config import validate_config


class ConfigTest(unittest.TestCase):
    def test_declarative_provider_and_model_profile(self) -> None:
        validate_config(
            {
                "provider_order": ["custom"],
                "providers": {"custom": {"adapter": "package.module:Provider"}},
                "model": {"id": "custom-model", "context_size": 32768},
            }
        )

    def test_provider_order_must_reference_configured_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing providers"):
            validate_config(
                {
                    "provider_order": ["missing"],
                    "providers": {"custom": {}},
                    "model": {"id": "custom-model", "context_size": 32768},
                }
            )


if __name__ == "__main__":
    unittest.main()
