#!/usr/bin/env python3
"""Save or restore a private slot on an isolated worker's loopback server."""
import argparse
import json
from pathlib import Path
import re
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('action',choices=('save','restore'))
parser.add_argument('filename')
parser.add_argument('--minimum-tokens',type=int,default=100000)
args=parser.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_-]+\.slot',args.filename):
    raise SystemExit('A plain .slot filename is required')
key=Path('/workspace/qwen38/api_key').read_text().strip()
request=urllib.request.Request('http://127.0.0.1:17070/slots/0?action='+args.action,
    data=json.dumps({'filename':args.filename}).encode(),
    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=120) as response:
    result=json.load(response)
field='n_saved' if args.action=='save' else 'n_restored'
if result.get('error') or not isinstance(result.get(field),int) or result[field]<args.minimum_tokens:
    raise SystemExit('Slot operation did not verify the required token count')
print(json.dumps(result,sort_keys=True))
