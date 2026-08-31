from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from abliteration_station.controller import Controller, make_provider
from abliteration_station.errors import LifecycleError, ProviderUnavailable
from abliteration_station.providers.base import Route


class FakeProvider:
    def __init__(self, name, result):
        self.name = name
        self.result = result
        self.stopped = False

    def ensure(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def doctor(self):
        return []

    def stop(self):
        self.stopped = True

    def status(self):
        return {"provider": self.name}


class ControllerTest(unittest.TestCase):
    def test_provider_adapter_loads_from_configuration(self):
        provider = make_provider(
            "custom",
            {
                "providers": {
                    "custom": {
                        "adapter": "abliteration_station.providers.vast:VastProvider",
                        "ensure_command": "/tmp/ensure",
                        "instance_file": "/tmp/instance",
                        "lifecycle_token_file": "/tmp/token",
                        "upstream": "http://model.test",
                    }
                }
            },
        )
        self.assertEqual(provider.name, "vast")

    def test_unavailable_primary_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("test\n", encoding="utf-8")
            config = {
                "provider_order": ["first", "vast"],
                "route_file": str(root / "route.json"),
                "ensure_lock_file": str(root / "ensure.lock"),
                "inference_key_file": str(key),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "providers": {},
            }
            providers = {
                "first": FakeProvider("first", ProviderUnavailable("not configured")),
                "vast": FakeProvider("vast", Route("vast", "http://vast.test", {"id": 1})),
            }
            controller = Controller(config)
            with patch("abliteration_station.controller.make_provider", side_effect=lambda name, _: providers[name]), \
                 patch.object(controller, "model_gate"), patch.object(controller, "chat_gate"):
                route = controller.ensure()
            self.assertEqual(route.provider, "vast")
            self.assertIn('"provider": "vast"', (root / "route.json").read_text())

    def test_all_failures_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            config = {
                "provider_order": ["vast"],
                "route_file": str(Path(temp) / "route.json"),
                "ensure_lock_file": str(Path(temp) / "ensure.lock"),
                "inference_key_file": str(Path(temp) / "key"),
                "providers": {},
            }
            provider = FakeProvider("vast", LifecycleError("capacity unavailable"))
            controller = Controller(config)
            with patch("abliteration_station.controller.make_provider", return_value=provider):
                with self.assertRaisesRegex(LifecycleError, "capacity unavailable"):
                    controller.ensure()
            self.assertTrue(provider.stopped)

    def test_ready_active_route_avoids_new_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            route_file = root / "route.json"
            route_file.write_text(
                '{"provider":"vast","upstream":"https://ready.test","identity":{"id":1}}\n',
                encoding="utf-8",
            )
            config = {
                "provider_order": ["vast"],
                "route_file": str(route_file),
                "ensure_lock_file": str(root / "ensure.lock"),
                "inference_key_file": str(root / "key"),
                "providers": {},
            }
            controller = Controller(config)
            with patch("abliteration_station.controller.make_provider") as make, \
                 patch.object(controller, "model_gate"), patch.object(controller, "chat_gate"):
                route = controller.ensure()
            self.assertEqual(route.provider, "vast")
            make.assert_not_called()

    def test_gate_failure_stops_provider_before_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            providers = {
                "vast": FakeProvider("vast", Route("vast", "http://bad.test", {})),
                "second": FakeProvider("second", Route("second", "https://good.test", {})),
            }
            config = {
                "provider_order": ["vast", "second"],
                "route_file": str(root / "route.json"),
                "ensure_lock_file": str(root / "ensure.lock"),
                "inference_key_file": str(root / "key"),
                "providers": {},
            }
            controller = Controller(config)
            def gate(upstream):
                if upstream == "http://bad.test":
                    raise LifecycleError("bad model")
            with patch("abliteration_station.controller.make_provider", side_effect=lambda name, _: providers[name]), \
                 patch.object(controller, "model_gate", side_effect=gate), patch.object(controller, "chat_gate"):
                route = controller.ensure()
            self.assertEqual(route.provider, "second")
            self.assertTrue(providers["vast"].stopped)

    def test_stop_removes_route_after_provider_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            route_file = root / "route.json"
            route_file.write_text(
                '{"provider":"vast","upstream":"http://vast.test","identity":{"id":1}}\n',
                encoding="utf-8",
            )
            config = {
                "provider_order": ["vast"],
                "route_file": str(route_file),
                "ensure_lock_file": str(root / "ensure.lock"),
                "providers": {},
            }
            provider = FakeProvider("vast", None)
            controller = Controller(config)
            with patch("abliteration_station.controller.make_provider", return_value=provider):
                controller.stop()
            self.assertTrue(provider.stopped)
            self.assertFalse(route_file.exists())


if __name__ == "__main__":
    unittest.main()
