import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "replay", Path(__file__).parents[1] / "benchmarks/replay_captured_pi.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class FingerprintTests(unittest.TestCase):
    def call(self, arguments, name="edit", identifier="a"):
        return {"id": identifier, "function": {"name": name, "arguments": arguments}}

    def fingerprint(self, *calls):
        return replay.tool_output_fingerprint({"tool_calls": list(calls)})

    def test_arguments_are_not_omitted(self):
        self.assertNotEqual(self.fingerprint(self.call('{"text":"one"}')),
                            self.fingerprint(self.call('{"text":"two"}')))

    def test_generated_id_is_not_part_of_output(self):
        self.assertEqual(self.fingerprint(self.call("{}", identifier="a")),
                         self.fingerprint(self.call("{}", identifier="b")))

    def test_call_order_and_name_matter(self):
        a, b = self.call("{}"), self.call("{}", name="read")
        self.assertNotEqual(self.fingerprint(a, b), self.fingerprint(b, a))

    def test_no_private_text_in_hash(self):
        result = self.fingerprint(self.call("private source text"))
        self.assertRegex(result, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
