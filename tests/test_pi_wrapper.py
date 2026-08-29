from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


WRAPPER = Path(__file__).parents[1] / "scripts" / "pi-qwen-cloud"


class PiWrapperTest(unittest.TestCase):
    def test_bootstrap_hold_is_released_before_pi_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / "events"
            curl = root / "curl"
            qwen_cloud = root / "qwen-cloud"
            pi = root / "pi"

            curl.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *lifecycle/inhibit*) printf 'inhibit\\n' >>\"$TEST_LOG\" ;;\n"
                "  *lifecycle/release*) printf 'release\\n' >>\"$TEST_LOG\" ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            qwen_cloud.write_text(
                "#!/usr/bin/env bash\nprintf 'ensure\\n' >>\"$TEST_LOG\"\n",
                encoding="utf-8",
            )
            pi.write_text(
                "#!/usr/bin/env bash\n"
                "[[ $(tail -n 1 \"$TEST_LOG\") == release ]] || exit 2\n"
                "printf 'pi\\n' >>\"$TEST_LOG\"\n",
                encoding="utf-8",
            )
            for command in (curl, qwen_cloud, pi):
                command.chmod(0o700)

            environment = os.environ.copy()
            environment.update(
                {
                    "TEST_LOG": str(log),
                    "QWEN_CLOUD_CURL": str(curl),
                    "QWEN_CLOUD_CLI": str(qwen_cloud),
                    "PI_QWEN_BIN": str(pi),
                    "QWEN_CLOUD_CONFIG": str(root / "config.json"),
                }
            )
            subprocess.run([str(WRAPPER), "--continue"], env=environment, check=True)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                ["inhibit", "ensure", "release", "pi"],
            )


if __name__ == "__main__":
    unittest.main()
