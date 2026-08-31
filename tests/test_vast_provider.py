from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path

from abliteration_station.providers.vast import VastProvider


class VastProviderTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
