from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("g++"), "Linux preload test")
class SamplerProfileTest(unittest.TestCase):
    def test_preload_preserves_calls_and_reports_categories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = root / "fake.cpp"
            fake.write_text('''#include <unistd.h>
struct llama_sampler { const char * name; };
struct llama_token_data_array;
static int calls = 0;
extern "C" const char * llama_sampler_name(const llama_sampler * s) { return s->name; }
extern "C" void llama_sampler_apply(llama_sampler *, llama_token_data_array *) { ++calls; usleep(1000); }
extern "C" int fake_calls() { return calls; }
''')
            main = root / "main.cpp"
            main.write_text('''#include <cstdio>
struct llama_sampler { const char * name; };
struct llama_token_data_array;
extern "C" void llama_sampler_apply(llama_sampler *, llama_token_data_array *);
extern "C" int fake_calls();
int main() {
  llama_sampler grammar{"grammar"}, chain{"chain"};
  for (int i = 0; i < 20; ++i) { llama_sampler_apply(&grammar, nullptr); llama_sampler_apply(&chain, nullptr); }
  llama_sampler_apply(nullptr, nullptr);
  std::printf("calls=%d\\n", fake_calls());
}
''')
            commands = [
                ["g++", "-shared", "-fPIC", str(fake), "-o", str(root / "libfake.so")],
                ["g++", str(main), "-L" + str(root), "-lfake", "-Wl,-rpath," + str(root), "-o", str(root / "probe")],
                ["g++", "-O2", "-std=c++17", "-shared", "-fPIC", str(ROOT / "benchmarks" / "sampler_profile.cpp"), "-ldl", "-o", str(root / "profile.so")],
            ]
            for command in commands:
                subprocess.run(command, check=True, capture_output=True)
            baseline = subprocess.run([str(root / "probe")], check=True, capture_output=True, text=True)
            env = dict(os.environ, LD_PRELOAD=str(root / "profile.so"))
            measured = subprocess.run([str(root / "probe")], env=env, check=True, capture_output=True, text=True)
            self.assertEqual(measured.stdout, baseline.stdout)
            self.assertEqual(measured.stdout, "calls=41\n")
            report = json.loads(measured.stderr.split("QWEN_SAMPLER_PROFILE ", 1)[1])
            self.assertEqual(report["grammar_calls"], 20)
            self.assertEqual(report["chain_calls"], 20)
            self.assertGreater(report["grammar_ms"], 0)
            self.assertGreater(report["chain_ms"], 0)
