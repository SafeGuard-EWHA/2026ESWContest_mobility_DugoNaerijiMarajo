#!/usr/bin/env python3
"""Read the current service invocation; optionally restart to issue a fresh code."""
import argparse
import re
import subprocess
import time

def output(*args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=20,check=True)
    return result.stdout.strip()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--new-code',action='store_true');args=parser.parse_args()
    try:
        if args.new_code:output('systemctl','restart','safeguard-navigation.service')
        for attempt in range(8):
            invocation=output('systemctl','show','safeguard-navigation.service','--property=InvocationID','--value')
            state=output('systemctl','show','safeguard-navigation.service','--property=ActiveState','--value')
            if not re.fullmatch(r'[0-9a-f]{32}',invocation):
                print('SERVICE:',state,'No active receiver invocation.');return
            logs=output('journalctl','_SYSTEMD_INVOCATION_ID='+invocation,'-o','cat','--no-pager')
            codes=re.findall(r'PAIRING CODE \(8 digits, one phone, 10 minutes\): (\d{8})',logs)
            if codes or not args.new_code or state=='failed':break
            time.sleep(1)
        print('SERVICE:',state)
        print('PHONE: https://safeguard.local:8443/')
        for line in logs.splitlines():
            if line.startswith(('Certificate ','CA SHA-256:','IPv6 listening:','TLS CONFIG ERROR:','NETWORK WAIT:')):print(line)
        if codes:
            print('PAIRING CODE:',codes[-1])
            print('Valid for 10 minutes after receiver startup. If expired, rerun with --new-code.')
        else:print('Receiver is not ready yet. Recent service log:\n'+ '\n'.join(logs.splitlines()[-12:]))
    except (OSError,ValueError,subprocess.SubprocessError) as error:parser.exit(2,'Status check stopped: '+str(error)+'\n')

if __name__=='__main__':main()
