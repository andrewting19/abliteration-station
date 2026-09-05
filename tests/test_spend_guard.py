import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('guard',Path(__file__).resolve().parents[1]/'benchmarks/spend_guard.py')
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class SpendGuardTest(unittest.TestCase):
    def test_threshold_and_deposit(self):
        state={'start_available':9.377988496900272,'last_available':9.377988496900272,'stop_drawdown':4.75}
        self.assertIsNone(guard.decision(state,8))
        self.assertIsNotNone(guard.decision(state,4.62))
        self.assertIsNotNone(guard.decision(state,10))
