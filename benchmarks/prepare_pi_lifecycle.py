#!/usr/bin/env python3
"""Prepare isolated controller state without changing production config."""
import argparse
import json
import os
from pathlib import Path
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
parser.add_argument('instance')
parser.add_argument('ensure_script',type=Path)
args=parser.parse_args()
if not args.instance.isdigit(): raise SystemExit('Numeric instance required')
config=json.loads(Path('/etc/abliteration-station/config.json').read_text())
provider=config['providers']['vast']
if Path(provider['instance_file']).read_text().strip()==args.instance:
    raise SystemExit('Refusing production instance')
os.umask(0o077)
args.root.mkdir(mode=0o700,parents=True,exist_ok=False)
for name in ('project','sessions','agent'):
    (args.root/name).mkdir(mode=0o700)
config.update(provider_order=['vast'],fallback_on_runtime_failure=False,
    route_file=str(args.root/'route.json'),progress_file=str(args.root/'progress.json'),
    ensure_lock_file=str(args.root/'ensure.lock'))
config['providers']={'vast':provider}
provider.update(instance_file=str(args.root/'instance-id'),ensure_command=str(args.root/'ensure-test'),
    upstream='http://127.0.0.1:17075',start_timeout_seconds=120)
config['kv_cache'].update(enabled=True,state_file=str(args.root/'cache-state.json'),
    artifact_directory=str(args.root/'cache'),filename='pi-lifecycle-test.slot',
    portable_export_on_save=False,required_before_stop=True)
(args.root/'instance-id').write_text(args.instance+'\n')
(args.root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
(args.root/'project'/'README.md').write_text('# Lifecycle test project\n\nThis is a private test fixture.\n')
shutil.copyfile(args.ensure_script,args.root/'ensure-test')
(args.root/'ensure-test').chmod(0o700)
print('Prepared isolated Pi lifecycle state:',args.root)
