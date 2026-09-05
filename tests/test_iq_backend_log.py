import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "iq_check", Path(__file__).resolve().parents[1] / "benchmarks/check_iq_backend_log.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CoverageTest(unittest.TestCase):
    def test_complete(self):
        lines = [f"  MUL_MAT(type_a={t},type_b=f32,m=16,n={n},k=256): \x1b[1;32mOK\x1b[0m"
                 for t in checker.TYPES for n in checker.BATCHES]
        self.assertEqual(checker.check("\n".join(lines)), 42)

    def test_empty_skipped_and_failure_rejected(self):
        for text in ("", "all backends skipped", "MUL_MAT(type_a=iq3_s,n=7): not supported", "FAIL"):
            with self.assertRaises(ValueError):
                checker.check(text)
