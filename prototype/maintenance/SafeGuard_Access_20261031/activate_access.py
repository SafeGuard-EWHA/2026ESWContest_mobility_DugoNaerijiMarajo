"""Install access-only services with an exact rollback record. Never run a controller."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT=Path('/home/pi/SafeGuard_Operational_20261031')
PORTAL=Path('/etc/systemd/system/safeguard-portal.service')
NAV=Path('/etc/systemd/system/safeguard-navigation.service.d/95-operational-20261031.conf')
PORTAL_TEXT=f'''[Unit]
Description=SafeGuard HTTPS access - phone and weather inspection only
Wants=safeguard-navigation.service
After=safeguard-navigation.service

[Service]
Type=simple
User=pi
WorkingDirectory={PROJECT}
UMask=0077
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 {PROJECT}/scripts/access_portal.py --project {PROJECT} --connection-check
Restart=on-failure
RestartSec=5
KillSignal=SIGINT
KillMode=mixed
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
'''
NAV_TEXT=f'''[Service]
WorkingDirectory={PROJECT}
ExecStart=
ExecStart=/usr/bin/python3 /usr/local/lib/safeguard-navigation/run_receiver.py --project {PROJECT}
ExecStartPre=
'''


def call(*args,check=True):
    result=subprocess.run(args,check=check,text=True,capture_output=True,timeout=35)
    return result.stdout.strip()


def restore(backup):
    record=json.loads((backup/'restore.json').read_text())
    if set(record['files'])!={str(PORTAL),str(NAV)}:raise ValueError('Unexpected restore destinations')
    call('systemctl','disable','--now','safeguard-portal.service',check=False)
    for path,content in record['files'].items():
        destination=Path(path)
        if destination.is_symlink():raise ValueError('Refusing symlink restore')
        if content is None:destination.unlink(missing_ok=True)
        else:destination.write_text(content)
    call('systemctl','daemon-reload')
    if record['navigation_active']:call('systemctl','restart','safeguard-navigation.service')
    print('Restored previous access services from',backup)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollback',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Run through sudo for service installation')
    if args.rollback:restore(args.rollback);return
    if not (PROJECT/'runtime/portal_auth.json').is_file():raise ValueError('Portal password must be initialized first')
    for path in (PORTAL,NAV):
        if path.exists() or path.is_symlink():raise ValueError('Existing service file preserved; review needed: '+str(path))
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                if (entry/'comm').read_text().strip()=='safeguard_main':raise ValueError('Controller running; defer service change')
            except (FileNotFoundError,PermissionError):pass
    backup=PROJECT/'deployment'/('access_backup_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700,parents=True)
    record={'files':{str(p):p.read_text() if p.exists() else None for p in (PORTAL,NAV)},
        'navigation_active':call('systemctl','is-active','safeguard-navigation.service',check=False)=='active'}
    (backup/'restore.json').write_text(json.dumps(record,indent=2))
    (backup/'navigation_before.txt').write_text(call('systemctl','cat','safeguard-navigation.service'))
    try:
        for path,content in ((PORTAL,PORTAL_TEXT),(NAV,NAV_TEXT)):
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x') as out:out.write(content)
            path.chmod(0o644)
        call('systemd-analyze','verify',str(PORTAL))
        call('systemctl','daemon-reload')
        call('systemctl','restart','safeguard-navigation.service')
        call('systemctl','enable','--now','safeguard-portal.service')
        time.sleep(3)
        for name in ('safeguard-navigation.service','safeguard-portal.service'):
            if call('systemctl','is-active',name,check=False)!='active':raise ValueError(name+' not active')
        print('ACCESS_ONLY_ACTIVE; hardware main remains unstarted')
        print('ROLLBACK_RECORD',backup)
    except BaseException:
        restore(backup);raise


if __name__=='__main__':main()
