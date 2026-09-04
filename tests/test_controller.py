from __future__ import annotations

import json
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

    def runtime_fingerprint(self, route):
        return {"schema_version": 1, "fingerprint": "c" * 64}

    def export_cache(self, route, filename, destination):
        return {
            "sha256": {
                "slot": "a" * 64,
                "checkpoint": "b" * 64,
                "archive": "d" * 64,
            }
        }

    def import_cache(self, route, filename, source, manifest):
        return None


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

    def test_restore_can_be_kept_off_the_wake_critical_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("test\n", encoding="utf-8")
            config = {
                "provider_order": ["vast"],
                "route_file": str(root / "route.json"),
                "ensure_lock_file": str(root / "ensure.lock"),
                "inference_key_file": str(key),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {"enabled": True, "restore_on_wake": False},
                "providers": {},
            }
            provider = FakeProvider(
                "vast", Route("vast", "http://vast.test", {"id": 1})
            )
            controller = Controller(config)
            with patch("abliteration_station.controller.make_provider", return_value=provider), \
                 patch.object(controller, "model_gate"), \
                 patch.object(controller, "chat_gate"), \
                 patch.object(controller, "restore_cache") as restore:
                controller.ensure()
            restore.assert_not_called()

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

    def test_save_records_portable_artifact_and_live_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("test\n", encoding="utf-8")
            config = {
                "inference_key_file": str(key),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {
                    "enabled": True,
                    "filename": "pi.slot",
                    "state_file": str(root / "state.json"),
                    "artifact_directory": str(root / "cache"),
                    "portable_export_on_save": True,
                },
                "providers": {},
            }
            controller = Controller(config)
            provider = FakeProvider("vast", None)
            route = Route("vast", "http://vast.test", {"instance_id": "1"})
            with patch("abliteration_station.controller.make_provider", return_value=provider), \
                 patch.object(controller, "_request_json", return_value={"n_saved": 160000}):
                self.assertTrue(controller.save_cache(route))
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["runtime"]["fingerprint"], "c" * 64)
            self.assertEqual(state["artifact"]["sha256"]["archive"], "d" * 64)

    def test_provider_local_save_does_not_export_through_controller(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("test\n", encoding="utf-8")
            config = {
                "inference_key_file": str(key),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {
                    "enabled": True,
                    "filename": "pi.slot",
                    "state_file": str(root / "state.json"),
                    "portable_export_on_save": False,
                },
                "providers": {},
            }
            controller = Controller(config)
            provider = FakeProvider("vast", None)
            route = Route("vast", "http://vast.test", {"instance_id": "1"})
            with patch("abliteration_station.controller.make_provider", return_value=provider), \
                 patch.object(provider, "export_cache") as export, \
                 patch.object(controller, "_request_json", return_value={"n_saved": 160000}):
                self.assertTrue(controller.save_cache(route))
            export.assert_not_called()
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["storage"], "provider-local")
            self.assertNotIn("artifact", state)

    def test_empty_slot_save_does_not_replace_portable_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("test\n", encoding="utf-8")
            state = root / "state.json"
            state.write_text('{"preserved":true}\n', encoding="utf-8")
            config = {
                "inference_key_file": str(key),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {
                    "enabled": True,
                    "filename": "pi.slot",
                    "state_file": str(state),
                    "artifact_directory": str(root / "cache"),
                },
                "providers": {},
            }
            controller = Controller(config)
            route = Route("vast", "http://vast.test", {"instance_id": "1"})
            with patch.object(controller, "_request_json", return_value={"n_saved": 0}):
                self.assertFalse(controller.save_cache(route))
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"preserved": True})

    def test_replacement_route_imports_before_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            key = root / "key"
            key.write_text("test\n", encoding="utf-8")
            state = root / "state.json"
            config = {
                "inference_key_file": str(key),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {
                    "enabled": True,
                    "filename": "pi.slot",
                    "state_file": str(state),
                    "artifact_directory": str(root / "cache"),
                },
                "providers": {},
            }
            controller = Controller(config)
            provider = FakeProvider("vast", None)
            state.write_text(json.dumps({
                "fingerprint": controller._cache_fingerprint(),
                "filename": "pi.slot",
                "identity": {"instance_id": "old"},
                "runtime": provider.runtime_fingerprint(None),
                "artifact": provider.export_cache(None, "pi.slot", root),
            }) + "\n", encoding="utf-8")
            order = []
            with patch("abliteration_station.controller.make_provider", return_value=provider), \
                 patch.object(provider, "import_cache", side_effect=lambda *args: order.append("import")), \
                 patch.object(controller, "_request_json", side_effect=lambda *args, **kwargs: order.append("restore") or {}):
                restored = controller.restore_cache(
                    Route("vast", "http://vast.test", {"instance_id": "new"})
                )
            self.assertTrue(restored)
            self.assertEqual(order, ["import", "restore"])

    def test_live_runtime_mismatch_uses_cold_fallback_before_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "state.json"
            controller = Controller({
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {"enabled": True, "state_file": str(state)},
            })
            state.write_text(json.dumps({
                "fingerprint": controller._cache_fingerprint(),
                "filename": "pi.slot",
                "identity": {"instance_id": "old"},
                "runtime": {"fingerprint": "old-runtime"},
                "artifact": {},
            }) + "\n", encoding="utf-8")
            provider = FakeProvider("vast", None)
            with patch("abliteration_station.controller.make_provider", return_value=provider), \
                 patch.object(provider, "runtime_fingerprint", return_value={"fingerprint": "new-runtime"}), \
                 patch.object(provider, "import_cache") as import_cache, \
                 patch.object(controller, "_request_json") as request:
                restored = controller.restore_cache(
                    Route("vast", "http://vast.test", {"instance_id": "new"})
                )
            self.assertFalse(restored)
            import_cache.assert_not_called()
            request.assert_not_called()

    def test_required_cache_failure_cancels_provider_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            route_file = root / "route.json"
            route_file.write_text(
                '{"provider":"vast","upstream":"http://vast.test","identity":{"instance_id":"1"}}\n',
                encoding="utf-8",
            )
            controller = Controller({
                "route_file": str(route_file),
                "model": {"id": "qwen38-cloud", "context_size": 262144},
                "kv_cache": {"enabled": True, "required_before_stop": True},
                "providers": {},
            })
            provider = FakeProvider("vast", None)
            with patch("abliteration_station.controller.make_provider", return_value=provider), \
                 patch.object(controller, "save_cache", return_value=False):
                with self.assertRaisesRegex(LifecycleError, "stop was cancelled"):
                    controller.stop()
            self.assertFalse(provider.stopped)
            self.assertTrue(route_file.exists())


if __name__ == "__main__":
    unittest.main()
