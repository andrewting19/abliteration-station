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

from abliteration_station.errors import LifecycleError
from abliteration_station.providers.base import Route
from abliteration_station.providers.vast import VastProvider

ROOT = Path(__file__).parents[1]


class VastProviderTest(unittest.TestCase):
    def test_cache_export_passes_selected_replace_mode(self) -> None:
        provider = VastProvider(
            {
                "cache_command": "/bin/true",
                "cache_replace_mode": "in-place-safe",
            }
        )
        result = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"sha256": {"archive": "a" * 64}}),
            stderr="",
        )
        with patch.object(provider, "_run_cache_command", return_value=result) as run:
            provider.export_cache(
                Route("vast", "http://model.test", {"instance_id": "12345"}),
                "pi-session.slot",
                Path("/var/lib/cache"),
            )
        run.assert_called_once_with(
            "cache-export",
            "12345",
            "pi-session.slot",
            "/var/lib/cache",
            "in-place-safe",
        )

    def test_cache_export_rejects_unknown_replace_mode(self) -> None:
        provider = VastProvider(
            {"cache_command": "/bin/true", "cache_replace_mode": "unsafe"}
        )
        with self.assertRaisesRegex(LifecycleError, "replace mode is invalid"):
            provider.export_cache(
                Route("vast", "http://model.test", {"instance_id": "12345"}),
                "pi-session.slot",
                Path("/var/lib/cache"),
            )

    def test_fast_bootstrap_uses_verified_release_artifacts(self) -> None:
        manifest = (ROOT / "scripts" / "vast" / "portable-manifest.env").read_text(
            encoding="utf-8"
        )
        bootstrap = (ROOT / "scripts" / "vast" / "bootstrap-fresh-vast.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("releases/download/bootstrap-artifacts-v1", manifest)
        self.assertIn(
            "a306552e059c812dc9a0991b19be400e98b6f7c6174a8ad5921a91a837247955",
            manifest,
        )
        self.assertIn("QWEN38_RUNTIME_PATCH_SHA256", manifest)
        self.assertIn('export LD_LIBRARY_PATH="$SERVER_DIR', (ROOT / "scripts" / "vast" / "run-qwen38-cloud.sh").read_text(encoding="utf-8"))
        self.assertIn('git -C "$LLAMA_DIR" apply', bootstrap)
        self.assertIn('git -C "$LLAMA_DIR" write-tree', bootstrap)
        self.assertIn("does not match the current manifest", bootstrap)
        self.assertIn("QWEN38_TARGET_BYTES", manifest)
        self.assertIn("complete_stable", bootstrap)
        self.assertIn("stopped making progress", bootstrap)
        self.assertIn("supervisorctl pid", bootstrap)
        self.assertNotIn("if ! supervisorctl status", bootstrap)
        self.assertIn("${CUDA_VERSION:-} == 13.2*", bootstrap)
        self.assertIn("-DLLAMA_USE_PREBUILT_UI=OFF", bootstrap)
        self.assertIn("https://hf-mirror.com/", bootstrap)
        self.assertIn("curl -fsSIL --connect-timeout 5 --max-time 10", bootstrap)
        self.assertIn(
            'LD_LIBRARY_PATH="$binary_dir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"',
            bootstrap,
        )
        self.assertLess(
            bootstrap.index("Using the verified cached RTX 5090 build"),
            bootstrap.index("git clone --filter=blob:none"),
        )
        self.assertIn("draft_artifact_pid=$!", bootstrap)
        self.assertLess(
            bootstrap.index("draft_artifact_pid=$!"),
            bootstrap.index('"$QWEN38_TARGET_REPO"'),
        )
        self.assertIn("The portable Q4 draft download failed", bootstrap)

    def test_installed_deploy_includes_checkpoint_patch(self) -> None:
        installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        deploy = (ROOT / "scripts" / "vast" / "deploy-fresh-vast.sh").read_text(
            encoding="utf-8"
        )
        bootstrap = (ROOT / "scripts" / "vast" / "bootstrap-fresh-vast.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('"$vast_root/patches/llama-slot-checkpoints.patch"', installer)
        self.assertIn('PATCH_FILE="$SCRIPT_DIR/patches/llama-slot-checkpoints.patch"', deploy)
        self.assertIn('"$PATCH_FILE"', deploy)
        self.assertIn('"$SCRIPT_DIR/slot-cache-control.sh"', deploy)
        self.assertIn('/usr/local/bin/qwen38-slot-cache', bootstrap)

    def test_selector_accepts_32_gb_system_ram_hosts(self) -> None:
        script = (ROOT / "scripts" / "vast" / "qwen-vast").read_text(
            encoding="utf-8"
        )
        self.assertIn("cpu_ram>=32", script)
        self.assertNotIn("cpu_ram>=48", script)

    def test_launcher_supports_target_only_and_backend_sampling(self) -> None:
        launcher = (ROOT / "scripts" / "vast" / "run-qwen38-cloud.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("QWEN38_BACKEND_SAMPLING", launcher)
        self.assertIn("--backend-sampling", launcher)
        self.assertIn("QWEN38_DRAFT_BACKEND_SAMPLING", launcher)
        self.assertIn("--no-spec-draft-backend-sampling", launcher)
        self.assertIn('if [[ "$SPEC_TYPE" != "none" ]]', launcher)
        self.assertIn("SPEC_MODEL_ARGS+=(--spec-type none)", launcher)

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
        self.assertIn(
            "/var/lib/abliteration-station/performance-gates/runner-", ensure
        )
        self.assertNotIn("/var/log/abliteration-station-gate-", ensure)
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
            failed_offers = root / "failed-offers"
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
            environment.update(
                {
                    "HOME": str(home),
                    "VASTAI": str(fake),
                    "QWEN38_FAILED_OFFERS_FILE": str(failed_offers),
                }
            )
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
            self.assertEqual(failed_offers.read_text(encoding="utf-8").splitlines(), ["101"])

    def test_cuda_13_0_offer_uses_matching_base_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            (home / ".config" / "vastai").mkdir(parents=True)
            (home / ".config" / "vastai" / "vast_api_key").write_text(
                "test-only\n", encoding="utf-8"
            )
            arguments = root / "arguments"
            fake = root / "vastai"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                f"arguments = {str(arguments)!r}\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['search', 'offers']:\n"
                "    print(json.dumps([{'id': 303, 'dph_total': 0.4, "
                "'cuda_max_good': 13.0, 'pcie_bw': 45, 'reliability': 0.99}]))\n"
                "elif args[:2] == ['create', 'instance']:\n"
                "    open(arguments, 'w').write('\\n'.join(args))\n"
                "    print(json.dumps({'success': True, 'new_contract': 404}))\n"
                "else:\n"
                "    raise SystemExit('unexpected arguments: ' + repr(args))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "VASTAI": str(fake),
                    "QWEN38_CUDA_MIN": "13.0",
                    "QWEN38_RENT_BEST_ATTEMPTS": "1",
                }
            )
            subprocess.run(
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
            value = arguments.read_text(encoding="utf-8").splitlines()
            self.assertIn("vastai/base-image:cuda-13.0.3-auto", value)

    def test_cuda_13_2_offer_uses_prebuilt_runtime_image(self) -> None:
        script = (ROOT / "scripts" / "vast" / "qwen-vast").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "ghcr.io/andrewting19/abliteration-station-runtime:cuda13.2-v1",
            script,
        )
        self.assertIn("image=$RUNTIME_IMAGE", script)

    def test_bootstrap_uses_prebuilt_runtime_and_draft_cache(self) -> None:
        bootstrap = (
            ROOT / "scripts" / "vast" / "bootstrap-fresh-vast.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("QWEN38_PREBUILT_CACHE_DIR", bootstrap)
        self.assertIn("$PREBUILT_CACHE_DIR/runtime.tar.zst", bootstrap)
        self.assertIn(
            '$PREBUILT_CACHE_DIR/$QWEN38_DRAFT_Q4_FILE', bootstrap
        )

    def test_ensure_falls_back_from_cuda_13_2_to_cuda_13_0(self) -> None:
        ensure = (ROOT / "scripts" / "vast" / "ensure.sh").read_text(
            encoding="utf-8"
        )
        first = ensure.index("QWEN38_CUDA_MIN=13.2")
        fallback = ensure.index("QWEN38_CUDA_MIN=13.0")
        self.assertLess(first, fallback)
        self.assertIn("No CUDA 13.2 GPU is available", ensure)
        self.assertIn('sort -nu "$failed_offers_file" | paste -sd, -', ensure)

    def test_retained_start_grace_fails_over_after_provider_scheduling_window(self) -> None:
        script = (ROOT / "scripts" / "vast" / "qwen-vast").read_text(
            encoding="utf-8"
        )
        self.assertIn("QWEN38_STOPPED_START_GRACE_SECONDS:-45", script)
        self.assertIn("QWEN38_FRESH_HOST_GRACE_SECONDS:-300", script)
        self.assertIn("QWEN38_RETAINED_START=1", script)
        self.assertIn("did not return the retained GPU within", script)
        self.assertIn("did not expose the fresh container within", script)
        self.assertIn("provider_image", script)
        self.assertIn("provider_ssh", script)
        self.assertIn("copy did not finish within 15 minutes", script)


if __name__ == "__main__":
    unittest.main()
