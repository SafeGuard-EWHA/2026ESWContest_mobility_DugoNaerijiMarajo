#!/usr/bin/env python3
"""Supervise the receiver as an unprivileged user; retain its existing TLS identity."""
import argparse
import ipaddress
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import navigation_tls_identity as identity

def network_signature(runner=subprocess.run):
    result=runner(['ip','-j','address','show','dev','wlan0'],capture_output=True,text=True,timeout=5,check=True)
    ipv4=[];ipv6=[]
    for interface in json.loads(result.stdout):
        if interface.get('ifname')!='wlan0' or interface.get('operstate')!='UP':continue
        for entry in interface.get('addr_info',[]):
            flags=entry.get('flags',[])
            if entry.get('tentative') or entry.get('dadfailed') or any(f in flags for f in ('tentative','dadfailed')):continue
            try:
                if entry.get('family')=='inet':ipv4.append(identity.private_ipv4(entry['local']))
                elif entry.get('family')=='inet6' and entry.get('scope') in ('link','global'):
                    address=ipaddress.IPv6Address(entry['local'])
                    if not (address.is_unspecified or address.is_multicast or address.is_loopback or address.ipv4_mapped):ipv6.append(str(address))
            except (ValueError,KeyError):continue
    if not ipv4 or not ipv6:raise ValueError('Waiting for wlan0 IPv4 and usable IPv6')
    return (sorted(set(ipv4))[0],tuple(sorted(set(ipv6))))

def existing_identity(project):
    directory=Path(project)/'runtime/navigation_tls'
    if directory.is_symlink() or (Path(project)/'runtime').is_symlink():raise ValueError('TLS directories must not be symlinks')
    metadata=json.loads((directory/'setup.json').read_text())
    # Validate the original, exact certificate identities, including DNS name,
    # CA/profile consistency, key match and remaining validity. Current DHCP IP
    # is only a bind address and must NOT cause CA replacement.
    original_ip=identity.private_ipv4(metadata['ip'])
    identity.validate_existing(directory,original_ip)
    return identity.result_paths(directory,original_ip,True)

def receiver_command(project,current_ip,tls):
    return [sys.executable,str(Path(project)/'scripts/navigation_bridge.py'),
            '--host',current_ip,'--hostname','safeguard.local','--ipv6-interface','wlan0','--prefer-hostname',
            '--cert',tls['cert'],'--key',tls['key'],'--ca',tls['ca'],'--profile',tls['profile'],
            '--state-file',str(Path(project)/'runtime/navigation_location.json')]

def stop_child(child):
    if child.poll() is not None:return
    child.send_signal(signal.SIGINT)
    try:child.wait(timeout=7)
    except subprocess.TimeoutExpired:
        child.kill();child.wait(timeout=3)

def monitor(child,initial,stop,*,inspect=network_signature,pause=time.sleep):
    try:
        while not stop[0]:
            if child.poll() is not None:return 75
            pause(2)
            if stop[0]:break
            try:current=inspect()
            except (OSError,ValueError,subprocess.SubprocessError):
                print('NETWORK WAIT: wlan0 unavailable; receiver stopped. Run start_fix.py after reconnecting.',flush=True);return 75
            if current!=initial:
                print('NETWORK CHANGE: receiver stopped; certificate retained. Run start_fix.py again for a new pairing code.',flush=True);return 75
        return 0
    finally:stop_child(child)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,required=True)
    args=parser.parse_args();project=args.project.resolve()
    if socket.gethostname().split('.')[0]!='safeguard':
        print('CONFIG ERROR: this package expects hostname safeguard.',flush=True);return 78
    try:
        tls=existing_identity(project)
        expiry=identity.openssl('x509','-in',tls['cert'],'-noout','-enddate').strip()
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print('TLS CONFIG ERROR: '+str(error)+'; existing certificate was not replaced.',flush=True);return 78
    try:addresses=network_signature()
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print('NETWORK WAIT: '+str(error),flush=True);return 75
    print('CA SHA-256: '+tls['fingerprint_sha256'],flush=True)
    print('Certificate '+expiry,flush=True)
    print('Use https://safeguard.local:8443/ on the paired phone, even if the DHCP IP changes.',flush=True)
    stop=[False]
    def signal_stop(signum,frame):stop[0]=True
    signal.signal(signal.SIGTERM,signal_stop);signal.signal(signal.SIGINT,signal_stop)
    child=subprocess.Popen(receiver_command(project,addresses[0],tls))
    return monitor(child,addresses,stop)

if __name__=='__main__':raise SystemExit(main())
