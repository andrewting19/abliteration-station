import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("image_pull_report",
    Path(__file__).parents[1] / "benchmarks/image_pull_report.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImagePullReportTest(unittest.TestCase):
    def manifest(self):
        return {"layers": [{"digest": "sha256:" + "a" * 64, "size": 1000000000},
                           {"digest": "sha256:" + "b" * 64, "size": 3000000000}]}

    def test_completion_is_evidence_not_an_invented_remaining_byte_count(self):
        result = module.report(self.manifest(), "aaaaaaaaaaaa: Download complete\nprivate secret text", 100)
        self.assertEqual(result["layers_reported_complete"], 1)
        self.assertEqual(result["uncached_transfer_seconds_at_supplied_rate"], 320)
        self.assertEqual(len(result["layers_without_completion_evidence"]), 1)
        self.assertNotIn("private secret", str(result))
        self.assertIn("partly downloaded", result["caveat"])

    def test_pull_started_does_not_count_as_complete(self):
        result = module.report(self.manifest(), "aaaaaaaaaaaa: Pulling fs layer")
        self.assertEqual(result["layers_reported_complete"], 0)
        self.assertIsNone(result["uncached_transfer_seconds_at_supplied_rate"])

    def test_invalid_rate_and_index_are_rejected(self):
        for value in (0, -1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                module.report(self.manifest(), "", value)
        with self.assertRaises(ValueError):
            module.report({"manifests": []}, "")

    def test_ambiguous_short_prefix_does_not_prove_completion(self):
        manifest = self.manifest()
        manifest["layers"][1]["digest"] = "sha256:" + "a" * 12 + "b" * 52
        self.assertEqual(module.report(manifest, "aaaaaaaaaaaa: Pull complete")["layers_reported_complete"], 0)
