#!/usr/bin/env python3
"""Single hardware controller owner. Launches HELD; never auto-resumes outputs."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import time


def validate(config):
    if config.get('mode')!='REAL' or config.get('profile')!='REAL' or config.get('demo',{}).get('override_temperature') is not False:
        raise ValueError('Managed operation requires REAL cabin and ambient input')
    manual=config.get('manual_control',{})
    if manual.get('enabled') is not True or manual.get('boot_policy')!='held_until_explicit_resume':
        raise ValueError('Manual hold on boot must remain enabled')
    if config.get('dashboard',{}).get('host')!='127.0.0.1':
        raise ValueError('Keep the hardware dashboard on loopback')
    if config.get('ambient_provider',{}).get('enabled') is not True:
        raise ValueError('Live ambient provider must be enabled')


def hardware_owners(proc=Path('/proc')):
    owners=[]
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name)==os.getpid(): continue
        try:
            args=(entry/'cmdline').read_bytes().split(b'\0')
            if any(Path(arg.decode(errors='replace')).name in ('safeguard_main','sensor_hub.py','sensor_hub_original.py') for arg in args if arg):
                owners.append(int(entry.name))
        except OSError: pass
    return owners


def main():
    import fcntl
    from check_link import check
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    args=parser.parse_args();project=args.project.resolve()
    config_path=project/'configs/real_navigation_control.json'
    config=json.loads(config_path.read_text());validate(config)
    directory=Path.home()/'.local/state/safeguard';directory.mkdir(parents=True,exist_ok=True)
    lock=(directory/'controller.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    owners=hardware_owners()
    if owners: raise ValueError('Another hardware controller is running: '+str(owners))
    # Refuse duplicate ownership BEFORE firmware probe opens the USB serial link.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',config['dashboard']['port']))
    binary=project/'build/safeguard_main'
    if not binary.is_file(): raise ValueError('Build the reviewed sources on Pi first')
    # Boot can precede udev's USB by-id link. Wait without opening/resetting the MCU.
    deadline=time.monotonic()+60
    while not Path(config['hardware']['esp32_port']).exists():
        if time.monotonic()>=deadline:
            print('Waiting for ESP32 USB device; service may retry.',file=sys.stderr)
            return 75
        time.sleep(1)
    if hardware_owners(): raise ValueError('Another controller started while waiting for USB')
    check(config['hardware']['esp32_port'])
    os.set_inheritable(lock.fileno(),True)
    os.chdir(project)
    print('Controller starts HELD; explicit dashboard resume is required.',flush=True)
    os.execv(str(binary),[str(binary),'--config',str(config_path)])


if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,ValueError,KeyError) as error:
        print('Controller launch refused: '+str(error),file=sys.stderr);raise SystemExit(78)
