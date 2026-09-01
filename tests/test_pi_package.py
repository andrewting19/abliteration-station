from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PiPackageTest(unittest.TestCase):
    def test_manifest_declares_extension_and_release_version(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("pi-package", package["keywords"])
        self.assertEqual(package["pi"]["extensions"], ["./extensions"])
        self.assertEqual(package["version"], "0.2.1")
        self.assertIn(
            'version = "0.2.1"',
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        )

    def test_extension_registers_provider_and_lifecycle_commands(self) -> None:
        extension = (ROOT / "extensions" / "abliteration-station.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn('pi.registerProvider("abliteration-station"', extension)
        for command in ("use", "status", "wake", "stop", "doctor", "setup"):
            self.assertIn(f'pi.registerCommand("abliteration-{command}"', extension)
        self.assertNotIn("VAST_API_KEY", extension)
        self.assertNotIn("TAILSCALE_AUTH_KEY", extension)
        for lifecycle_message in (
            "Estimated time remaining for this phase",
            "Provider completion time is unknown",
            "The phase estimate was exceeded",
        ):
            self.assertIn(lifecycle_message, extension)
        ensure = (ROOT / "scripts" / "vast" / "ensure.sh").read_text(encoding="utf-8")
        self.assertIn("Waiting briefly for the retained GPU", ensure)
        self.assertIn("Copying the verified model workspace inside Vast", ensure)

    def test_system_installer_removes_only_known_legacy_pi_files(self) -> None:
        installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("abliteration-station-status.ts", installer)
        self.assertIn("qwen-cloud-wake-status.ts", installer)
        configure = (ROOT / "scripts" / "configure.sh").read_text(encoding="utf-8")
        self.assertNotIn('"$install_root/install-pi-provider.py"', configure)


if __name__ == "__main__":
    unittest.main()
