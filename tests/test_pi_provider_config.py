from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PiProviderConfigTest(unittest.TestCase):
    def test_install_uses_declarative_model_and_remove_is_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            agent = root / "agent"
            agent.mkdir()
            (agent / "models.json").write_text(
                '{"providers":{"keep":{"models":[]}}}\n', encoding="utf-8"
            )
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "model": {
                            "id": "fork-model",
                            "display_name": "Fork Model",
                            "context_size": 32768,
                        }
                    }
                ),
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "PI_CODING_AGENT_DIR": str(agent),
                    "ABLITERATION_STATION_CONFIG": str(config),
                }
            )
            subprocess.run(
                [str(ROOT / "scripts" / "install-pi-provider.py")],
                env=environment,
                check=True,
            )
            installed = json.loads((agent / "models.json").read_text(encoding="utf-8"))
            model = installed["providers"]["abliteration-station"]["models"][0]
            self.assertEqual(model["id"], "fork-model")
            self.assertEqual(model["contextWindow"], 32768)

            subprocess.run(
                [str(ROOT / "scripts" / "remove-pi-provider.py")],
                env=environment,
                check=True,
            )
            removed = json.loads((agent / "models.json").read_text(encoding="utf-8"))
            self.assertNotIn("abliteration-station", removed["providers"])
            self.assertIn("keep", removed["providers"])


if __name__ == "__main__":
    unittest.main()
