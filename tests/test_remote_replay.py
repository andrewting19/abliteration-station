import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]


class RemoteReplayTest(unittest.TestCase):
    def run_case(self, deadline, body, exit_code=0):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            ssh=root/'ssh'
            ssh.write_text('#!/bin/sh\nprintf \'%s\\n\' \''+body+"'\nexit "+str(exit_code)+'\n')
            ssh.chmod(0o755)
            output=root/'result.json'
            command=['bash',str(ROOT/'benchmarks/run_remote_replay.sh'),'worker.test','22','123','/tmp/replay.py','/tmp/private.json',str(output),str(deadline)]
            result=subprocess.run(command,env=dict(os.environ,PATH=str(root)+':'+os.environ['PATH']),capture_output=True,text=True)
            return result,output.read_text() if output.exists() else None, (output.stat().st_mode & 0o777) if output.exists() else None

    def test_deadline_rejects_before_creating_output(self):
        result,data,_=self.run_case(int(time.time())+60,'{}')
        self.assertEqual(result.returncode,2)
        self.assertIsNone(data)

    def test_summary_is_private_and_preserved(self):
        result,data,mode=self.run_case(int(time.time())+900,'{"finish_reason":"tool_calls"}')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(data)['finish_reason'],'tool_calls')
        self.assertEqual(mode,0o600)

    def test_disconnect_is_not_success(self):
        result,_,_=self.run_case(int(time.time())+900,'',255)
        self.assertEqual(result.returncode,255)

    def test_incomplete_response_is_not_success(self):
        result,_,_=self.run_case(int(time.time())+900,'{}')
        self.assertNotEqual(result.returncode,0)
