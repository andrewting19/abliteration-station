from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from abliteration_station.providers.vast import VastProvider

ROOT = Path(__file__).parents[1]


class VastProviderTest(unittest.TestCase):
    def test_selector_accepts_32_gb_system_ram_hosts(self) -> None:
        script = (ROOT / "scripts" / "vast" / "qwen-vast").read_text(
            encoding="utf-8"
        )
        self.assertIn("cpu_ram>=32", script)
        self.assertNotIn("cpu_ram>=48", script)

    def test_fresh_replacement_prefers_verified_workspace_copy(self) -> None:
        ensure = (ROOT / "scripts" / "vast" / "ensure.sh").read_text(encoding="utf-8")
        script = (ROOT / "scripts" / "vast" / "qwen-vast").read_text(encoding="utf-8")
        copy_position = ensure.index('"$QWEN_VAST" copy "$old_instance_id" "$new_instance_id"')
        deploy_position = ensure.index('"$QWEN_VAST" deploy "$new_instance_id"')
        self.assertLess(copy_position, deploy_position)
        self.assertIn('"$QWEN_VAST" activate-copy "$new_instance_id" "$old_instance_id"', ensure)
        self.assertIn("stopped-instance workspace copy failed", script)
        self.assertIn("public bootstrap fallback", ensure)
        self.assertIn("QWEN38_USE_PROVIDER_COPY:-0", ensure)
        self.assertIn(
            '[[ -n "$old_instance_id" && "$USE_PROVIDER_COPY" == 1 ]]', ensure
        )
        self.assertIn("abliteration-station-deferred-gate", ensure)
        self.assertNotIn('"$QWEN_VAST" performance-gate "$new_instance_id"', ensure)

    def test_ensure_default_timeout_allows_a_fresh_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = root / "ensure"
            command.write_text("#!/bin/sh\n", encoding="utf-8")
            instance_file = root / "instance"
            instance_file.write_text("12345\n", encoding="utf-8")
            provider = VastProvider(
                {
                    "ensure_command": str(command),
                    "instance_file": str(instance_file),
                    "lifecycle_token_file": str(root / "token"),
                    "upstream": "http://model.test",
                }
            )
            with patch(
                "abliteration_station.providers.vast.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ) as run:
                provider.ensure()
            self.assertEqual(run.call_args.kwargs["timeout"], 7200)

    def test_ensure_streams_progress_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            instance_file = root / "instance-id"
            command = root / "ensure"
            command.write_text(
                "#!/usr/bin/env bash\n"
                "echo 'Loading model assets...' >&2\n"
                f"printf '12345\\n' > {instance_file}\n",
                encoding="utf-8",
            )
            command.chmod(0o755)
            provider = VastProvider(
                {
                    "ensure_command": str(command),
                    "instance_file": str(instance_file),
                    "lifecycle_token_file": str(root / "token"),
                    "upstream": "http://model.test",
                }
            )
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
                with contextlib.redirect_stderr(output):
                    route = provider.ensure()
                output.seek(0)
                self.assertIn("Loading model assets...", output.read())
            self.assertEqual(route.identity, {"instance_id": "12345"})

    def test_rent_best_excludes_an_offer_after_create_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            (home / ".config" / "vastai").mkdir(parents=True)
            (home / ".config" / "vastai" / "vast_api_key").write_text(
                "test-only\n", encoding="utf-8"
            )
            calls = root / "calls"
            fake = root / "vastai"
            offers = [
                {
                    "id": 101,
                    "dph_total": 0.3,
                    "cuda_max_good": 13.2,
                    "pcie_bw": 30,
                    "reliability": 0.99,
                },
                {
                    "id": 202,
                    "dph_total": 0.31,
                    "cuda_max_good": 13.2,
                    "pcie_bw": 30,
                    "reliability": 0.99,
                },
            ]
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                f"calls = {str(calls)!r}\n"
                f"offers = {offers!r}\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['search', 'offers']:\n"
                "    print(json.dumps(offers))\n"
                "elif args[:2] == ['create', 'instance']:\n"
                "    offer = int(args[2])\n"
                "    with open(calls, 'a') as handle: handle.write(str(offer) + '\\n')\n"
                "    if offer == 101:\n"
                "        print(json.dumps({'error': True, 'status_code': 400, 'msg': 'conflict'}))\n"
                "        raise SystemExit(1)\n"
                "    print(json.dumps({'success': True, 'new_contract': 303}))\n"
                "else:\n"
                "    raise SystemExit('unexpected arguments: ' + repr(args))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            environment = os.environ.copy()
            environment.update({"HOME": str(home), "VASTAI": str(fake)})
            result = subprocess.run(
                [
                    str(ROOT / "scripts" / "vast" / "qwen-vast"),
                    "rent-best",
                    "on-demand",
                    "0.53",
                    "--rent",
                ],
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(json.loads(result.stdout)["offer_id"], 202)
            self.assertEqual(calls.read_text(encoding="utf-8").splitlines(), ["101", "202"])

    def test_retained_start_grace_fails_over_after_provider_scheduling_window(self) -> None:
        script = (ROOT / "scripts" / "vast" / "qwen-vast").read_text(
            encoding="utf-8"
        )
        self.assertIn("QWEN38_STOPPED_START_GRACE_SECONDS:-45", script)
        self.assertIn("QWEN38_RETAINED_START=1", script)
        self.assertIn("did not return the retained GPU within", script)
        self.assertIn("copy did not finish within 15 minutes", script)


if __name__ == "__main__":
    unittest.main()
