from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


WRAPPER = Path(__file__).parents[1] / "scripts" / "pi-abliteration-station"


class PiWrapperTest(unittest.TestCase):
    def test_wrapper_opens_pi_without_a_blocking_prewake(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / "events"
            curl = root / "curl"
            qwen_cloud = root / "abliteration-station"
            pi = root / "pi"

            curl.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'health\\n' >>\"$TEST_LOG\"\n",
                encoding="utf-8",
            )
            qwen_cloud.write_text(
                "#!/usr/bin/env bash\nprintf 'ensure\\n' >>\"$TEST_LOG\"\n",
                encoding="utf-8",
            )
            pi.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'pi\\n' >>\"$TEST_LOG\"\n",
                encoding="utf-8",
            )
            for command in (curl, qwen_cloud, pi):
                command.chmod(0o700)
            (root / "config.json").write_text(
                '{"model":{"id":"custom-model"}}\n', encoding="utf-8"
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "TEST_LOG": str(log),
                    "ABLITERATION_STATION_CURL": str(curl),
                    "ABLITERATION_STATION_CLI": str(qwen_cloud),
                    "PI_ABLITERATION_STATION_BIN": str(pi),
                    "ABLITERATION_STATION_CONFIG": str(root / "config.json"),
                }
            )
            subprocess.run([str(WRAPPER), "--continue"], env=environment, check=True)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                ["health", "pi"],
            )
            self.assertNotIn("ensure", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
