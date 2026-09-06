import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'),'Node required')
class LocalPortTest(unittest.TestCase):
    def invoke(self,port):
        script="import extension from './extensions/abliteration-station.ts'; extension({registerProvider: (_, p) => { console.log(p.baseUrl); process.exit(0); }});"
        env=dict(os.environ)
        env.pop('ABLITERATION_STATION_LOCAL_PORT',None)
        if port is not None: env['ABLITERATION_STATION_LOCAL_PORT']=port
        return subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',script],cwd=ROOT,env=env,capture_output=True,text=True)

    def test_default_and_isolated_port(self):
        for port,expected in ((None,17072),('17076',17076)):
            result=self.invoke(port)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),f'http://127.0.0.1:{expected}/v1')

    def test_invalid_port_rejected(self):
        for port in ('0','65536','17076.5','bad'):
            result=self.invoke(port)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('must be an integer',result.stderr)

    def test_ready_route_is_not_reported_as_still_starting(self):
        script="""
import extension from './extensions/abliteration-station.ts';
const events={}, commands={}, messages=[];
let reads=0;
globalThis.fetch=async()=>({ok:true,json:async()=>++reads===1
  ? {route:null,wake_in_flight:false}
  : {route:{provider:'vast'},wake_in_flight:false,active_requests:1}});
globalThis.setInterval=()=>1;
extension({registerProvider(){},on(n,f){events[n]=f;},registerCommand(n,c){commands[n]=c;}});
const ctx={model:{provider:'abliteration-station'},ui:{theme:{fg:(_,s)=>s},
 notify:m=>messages.push(m),setStatus:(_,s)=>messages.push(s),
 setWidget(){},setWorkingMessage:m=>messages.push(m)}};
await events.before_provider_request({},ctx);
await new Promise(resolve=>setImmediate(resolve));
console.log(JSON.stringify(messages));
"""
        env=dict(os.environ)
        env.pop('ABLITERATION_STATION_LOCAL_PORT',None)
        result=subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',script],cwd=ROOT,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Qwen connected; waiting for response',result.stdout)
        self.assertNotIn('The GPU is stopped',result.stdout)
