#!/usr/bin/env python3
"""Local HTTP + C++ + hub integration, with virtual sensors and outputs only."""
import argparse
import json
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,default=ROOT/'build/safeguard_main')
    args=parser.parse_args()
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1',0)); port=reserve.getsockname()[1]
    config=json.loads((ROOT/'configs/simulation.json').read_text())
    config['scenario']='estop'; config['dashboard']['port']=port
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'config.json'; path.write_text(json.dumps(config))
        proc=subprocess.Popen([str(args.binary.resolve()),'--config',str(path),'--duration','24'],
                              cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        url=f'http://127.0.0.1:{port}'
        def state():
            try:
                with urllib.request.urlopen(url+'/api/state',timeout=1) as response:
                    return json.load(response)
            except (OSError,ValueError,urllib.error.HTTPError):
                return {}
        def until(predicate,seconds=15):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                value=state()
                if value and predicate(value): return value
                if proc.poll() is not None: raise AssertionError(proc.communicate())
                time.sleep(0.08)
            raise AssertionError(('timeout',state()))
        def action(name):
            request=urllib.request.Request(url+'/api/control',json.dumps({'action':name}).encode(),
                                          {'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(request,timeout=2) as response:
                assert response.status==202
        try:
            before=until(lambda s:s['state']=='ESTOP' and s['inputs']['estop']['active'] is False)
            assert before['outputs']['fan'] is False
            action('rearm')
            until(lambda s:s['state']!='ESTOP' and s['outputs']['rearm_status']=='REARM_ACK_RECEIVED',4)
            protected=until(lambda s:s['state']=='PROTECTION' and s['outputs']['ack_status']=='SIMULATED_ACK',5)
            command=protected['outputs']['command_id']
            action('rearm')  # A rearm outside ESTOP must not turn protection off.
            time.sleep(0.5)
            after=state()
            assert after['state']=='PROTECTION' and after['outputs']['fan'] is True
            assert after['outputs']['command_id']==command
            with urllib.request.urlopen(url,timeout=1) as response:
                assert 'SafeGuard' in response.read().decode()
            print('PASS: local HTTP dashboard serves UI, acknowledged ESTOP rearm, protection rejects unrelated rearm.')
            print('SOFTWARE SIMULATION; this is not physical hardware verification.')
        finally:
            if proc.poll() is None: proc.send_signal(signal.SIGINT)
            stdout,stderr=proc.communicate(timeout=6)
            assert proc.returncode==0,(stdout,stderr)

if __name__=='__main__': main()
