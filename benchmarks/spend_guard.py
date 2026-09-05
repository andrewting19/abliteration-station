#!/usr/bin/env python3
"""Conservative account drawdown guard for explicitly labelled test rentals."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def decision(state, available):
    if available > state['last_available'] + 0.05:
        return 'account funds increased; reassess accounting'
    if state['start_available'] - available >= state['stop_drawdown']:
        return 'experiment spending limit reached'
    return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('state',type=Path)
    parser.add_argument('--vastai',required=True)
    args=parser.parse_args()
    state=json.loads(args.state.read_text())
    def call(*command):
        result=subprocess.run([args.vastai,*command,'--raw'],check=True,capture_output=True,text=True,timeout=30)
        return json.loads(result.stdout) if result.stdout.strip() else {}
    try:
        user=call('show','user')
        available=float(user['balance'])+float(user['credit'])
        reason=decision(state,available)
        state['last_available']=available
        state['measured_drawdown']=state['start_available']-available
        state['read_failures']=0
    except Exception as error:
        state['read_failures']=state.get('read_failures',0)+1
        reason='billing status unavailable' if state['read_failures']>=2 else None
        state['last_error']=type(error).__name__
    if reason:
        state['stopped']=True
        state['stop_reason']=reason
    temporary=args.state.with_suffix('.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as handle:
        json.dump(state,handle,indent=2)
    os.replace(temporary,args.state)
    if state.get('stopped'):
        # Leave production and older retained instances untouched.
        instances=call('show','instances')
        for instance in instances:
            if (instance.get('label') or '').startswith(state['label_prefix']):
                call('destroy','instance',str(instance['id']),'--yes')
    print(json.dumps({k:state.get(k) for k in ('stopped','stop_reason','measured_drawdown','last_available')}))


if __name__=='__main__':
    main()
