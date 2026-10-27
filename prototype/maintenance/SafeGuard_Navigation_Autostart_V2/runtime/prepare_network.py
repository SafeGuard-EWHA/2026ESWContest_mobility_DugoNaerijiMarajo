#!/usr/bin/env python3
"""Prepare wlan0 IPv6 at boot without restarting the Wi-Fi connection."""
import argparse
import json
import os
from pathlib import Path
import time
BASE=Path('/proc/sys/net/ipv6/conf/wlan0')
RECORD=Path('/run/safeguard-navigation-ipv6-v2.json')
KEYS=('accept_ra','autoconf','disable_ipv6')
def read_values():
    return {key:int((BASE/key).read_text()) for key in KEYS}
def apply(values):
    for key,value in values.items():(BASE/key).write_text(str(value))
def validate(values):
    if set(values)!=set(KEYS) or values['accept_ra'] not in (0,1,2) or any(values[k] not in (0,1) for k in ('autoconf','disable_ipv6')):
        raise ValueError('Unexpected wlan0 IPv6 settings')
def prepare(*,restore=False,read=read_values,write=apply,record=RECORD):
    current=read();validate(current)
    if record.is_symlink():raise ValueError('Unexpected backup symlink')
    saved=None
    if record.exists():
        saved=json.loads(record.read_text());validate(saved['before']);validate(saved['applied'])
    if restore:
        if saved is None:return 'No service-owned IPv6 change to restore'
        if current==saved['before']:
            record.unlink();return 'Already restored'
        if current!=saved['applied']:raise ValueError('IPv6 settings changed elsewhere; restore skipped')
        old=saved['before']
        write({'disable_ipv6':old['disable_ipv6'],'accept_ra':old['accept_ra'],'autoconf':old['autoconf']})
        if read()!=old:raise ValueError('IPv6 setting restore failed')
        record.unlink();return 'Original wlan0 IPv6 settings restored'
    # Accept router advertisements even if a team component enables forwarding.
    # Only wlan0 settings are changed, never global forwarding or IPv4.
    desired={'accept_ra':2,'autoconf':1,'disable_ipv6':0}
    if current==desired:return 'Wi-Fi IPv6 autoconfiguration already enabled'
    if saved is not None and current not in (saved['before'],saved['applied']):
        raise ValueError('Wi-Fi settings changed elsewhere; refusing overwrite')
    if saved is None:
        saved={'before':current,'applied':desired}
        fd=os.open(record,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(saved,stream)
    try:
        write(desired)
        if read()!=desired:raise ValueError('IPv6 setup failed')
    except (OSError,ValueError):
        write({'disable_ipv6':current['disable_ipv6'],'accept_ra':current['accept_ra'],'autoconf':current['autoconf']})
        raise
    return 'wlan0 IPv6 + router advertisements enabled; Wi-Fi connection retained'
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:parser.exit(2,'Run this helper through the installed service.')
    try:
        print(prepare(restore=args.restore),flush=True)
        if not args.restore:time.sleep(2)
    except (OSError,ValueError,KeyError,TypeError) as error:parser.exit(2,'NETWORK WAIT: '+str(error))
if __name__=='__main__':main()
