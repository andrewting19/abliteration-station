from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
INCLUDE = os.environ.get("LLAMA_PROFILE_INCLUDE")


@unittest.skipUnless(sys.platform.startswith("linux") and INCLUDE, "Exact Linux engine headers required")
class DecodeProfileTest(unittest.TestCase):
    def test_profile_forwards_batch_state_and_return_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = root / "fake.cpp"
            fake.write_text('''#include "llama.h"
#include <cstring>
#include <unistd.h>
struct llama_model { const char * arch; };
struct llama_context { llama_model * model; };
static llama_model models[] = {{"qwen35"}, {"dflash"}};
static llama_context contexts[] = {{models}, {models+1}};
extern "C" llama_context * fake_context(int i) { return contexts+i; }
extern "C" const llama_model * llama_get_model(const llama_context * c) { return c->model; }
extern "C" int32_t llama_model_meta_val_str(const llama_model * m, const char *, char * dst, size_t size) { std::strncpy(dst,m->arch,size); return std::strlen(m->arch); }
extern "C" int32_t llama_decode(llama_context *, llama_batch b) { usleep(1000); return b.n_tokens && b.token[0]==123 ? 0 : -1; }
extern "C" void llama_synchronize(llama_context *) { usleep(1000); }
extern "C" const char * llama_sampler_name(const llama_sampler *) { return "mock"; }
float * llama_get_embeddings_layer_inp(llama_context *, uint32_t) { static float value=2; usleep(1000); return &value; }
float * llama_get_embeddings_nextn(llama_context *) { static float value=3; usleep(1000); return &value; }
extern "C" float * llama_get_logits_ith(llama_context *, int32_t) { static float value=4; usleep(1000); return &value; }
extern "C" size_t llama_state_seq_get_data_ext(llama_context *, uint8_t * dst, size_t, llama_seq_id seq, llama_state_seq_flags flags) { dst[0]=seq+flags+7; return 17; }
extern "C" size_t llama_state_seq_set_data_ext(llama_context *, const uint8_t * src, size_t, llama_seq_id seq, llama_state_seq_flags flags) { return src[0]+seq+flags+2; }
''')
            main = root / "main.cpp"
            main.write_text('''#include "llama.h"
#include <cstdio>
extern "C" llama_context * fake_context(int);
float * llama_get_embeddings_layer_inp(llama_context *, uint32_t);
float * llama_get_embeddings_nextn(llama_context *);
int main() {
  llama_token token=123;
  llama_batch b={}; b.token=&token; b.n_tokens=7;
  int result=llama_decode(fake_context(0),b);
  llama_synchronize(fake_context(0));
  float read=*llama_get_embeddings_layer_inp(fake_context(0),0);
  b.n_tokens=8; result+=llama_decode(fake_context(1),b);
  read+=*llama_get_embeddings_nextn(fake_context(1));
  b.n_tokens=32; result+=llama_decode(fake_context(0),b);
  read+=*llama_get_logits_ith(fake_context(0),0);
  b.n_tokens=0; result+=llama_decode(fake_context(0),b);
  uint8_t data[32]={};
  auto got=llama_state_seq_get_data_ext(fake_context(0),data,32,3,LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY);
  auto put=llama_state_seq_set_data_ext(fake_context(1),data,32,4,LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY);
  std::printf("result=%d byte=%u get=%zu set=%zu read=%.0f\\n",result,data[0],got,put,read);
}
''')
            prefix = ["g++", "-std=c++17", "-I" + str(INCLUDE)]
            for command in (
                prefix + ["-shared", "-fPIC", str(fake), "-o", str(root / "libfake.so")],
                prefix + [str(main), "-L" + str(root), "-lfake", "-Wl,-rpath," + str(root), "-o", str(root / "probe")],
                prefix + ["-shared", "-fPIC", str(ROOT / "benchmarks" / "sampler_profile.cpp"), str(ROOT / "benchmarks" / "decode_profile.cpp"), "-ldl", "-o", str(root / "profile.so")],
            ):
                subprocess.run(command, check=True, capture_output=True)
            baseline = subprocess.run([str(root / "probe")], check=True, capture_output=True, text=True)
            result = subprocess.run([str(root / "probe")], env=dict(os.environ, LD_PRELOAD=str(root / "profile.so")), check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, baseline.stdout)
            records = [json.loads(line.split(" ", 1)[1]) for line in result.stderr.splitlines()]
            target = next(item for item in records if item["kind"] == "decode" and item.get("batch") == "7" and item["role"] == "target")
            self.assertEqual(target["tokens"], 7)
            self.assertEqual(target["failures"], 0)
            self.assertEqual(next(item for item in records if item.get("batch") == "0")["failures"], 1)
            self.assertEqual(next(item for item in records if item.get("operation") == "get")["bytes"], 17)
            self.assertEqual(next(item for item in records if item.get("operation") == "set")["bytes"], 18)
            read = next(item for item in records if item.get("operation") == "layer_input")
            self.assertEqual((read["role"], read["batch"], read["calls"]), ("target", "7", 1))
            self.assertIn("read=9", result.stdout)
            sync = next(item for item in records if item["kind"] == "sync")
            self.assertEqual((sync["role"], sync["batch"], sync["calls"]), ("target", "7", 1))
