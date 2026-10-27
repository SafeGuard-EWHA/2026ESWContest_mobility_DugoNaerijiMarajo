#!/usr/bin/env python3
"""Install the navigation-only boot service; retain all sensor/main configuration."""
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parent
LIB=Path('/usr/local/lib/safeguard-navigation')
UNIT=Path('/etc/systemd/system/safeguard-navigation.service')
SERVICE=UNIT.name
MARKER='# SafeGuard navigation boot service v2\n'

def unit_text(project,user):
    # Restrict interpolated systemd argument characters; do not accept expansions.
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+',str(project)) or not re.fullmatch(r'[a-z_][a-z0-9_-]*',user):
        raise ValueError('Unsupported project path or user name')
    return MARKER+f'''[Unit]
Description=SafeGuard local iPhone navigation receiver
Wants=network-online.target avahi-daemon.service
After=network-online.target avahi-daemon.service
StartLimitIntervalSec=0

[Service]
Type=simple
User={user}
WorkingDirectory={project}
UMask=0077
Environment=PYTHONUNBUFFERED=1
ExecStartPre=+/usr/bin/python3 {LIB}/prepare_network.py
ExecStart=/usr/bin/python3 {LIB}/run_receiver.py --project {project}
Restart=always
RestartSec=5
RestartPreventExitStatus=78
KillSignal=SIGINT
KillMode=mixed
TimeoutStartSec=20
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
'''

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def plan_project(project):
    base=json.loads((ROOT/'base_hashes.json').read_text())
    plan=[]
    for relative,expected in base.items():
        target=project/relative;source=ROOT/'patch'/relative
        if target.is_symlink() or project not in target.resolve().parents or not target.is_file():
            raise ValueError('Missing or unsafe target: '+str(target))
        if relative.endswith('.py'):ast.parse(source.read_text())
        if digest(target)==digest(source):continue
        if digest(target)!=expected:raise ValueError('Local changes found; refusing overwrite: '+relative)
        plan.append((source,target))
    return plan

def atomic_write(target,data,*,uid=0,gid=0,mode=0o644):
    temporary=target.with_name(target.name+'.tmp-'+uuid.uuid4().hex[:8])
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
        with os.fdopen(fd,'wb') as stream:stream.write(data)
        os.chmod(temporary,mode);os.chown(temporary,uid,gid)
        temporary.replace(target)
    finally:
        if temporary.exists():temporary.unlink()

def systemctl(*args,check=True):
    return subprocess.run(['systemctl',*args],check=check)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path('/home/pi/SafeGuard_Main'))
    parser.add_argument('--remove',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:parser.exit(2,'Use sudo python3 install_demo.py --project /home/pi/SafeGuard_Main\n')
    project=args.project.resolve()
    try:
        account=pwd.getpwnam('pi')
        expected_unit=unit_text(project,account.pw_name)
        if UNIT.is_symlink() or (UNIT.exists() and UNIT.read_text()!=expected_unit):
            raise ValueError('A different service file exists; refusing to replace it')
        if args.remove:
            if not UNIT.exists():print('Service is not installed');return
            systemctl('disable','--now',SERVICE)
            subprocess.run(['/usr/bin/python3',str(LIB/'prepare_network.py'),'--restore'],check=True)
            print('Autostart disabled; application files and certificates retained.');return
        if socket.gethostname().split('.')[0]!='safeguard':raise ValueError('Expected Pi hostname safeguard')
        if not Path('/run/systemd/system').is_dir():raise ValueError('Run this installer on the Pi with systemd')
        if subprocess.run(['systemctl','is-active','--quiet','avahi-daemon.service']).returncode:
            raise ValueError('avahi-daemon must already be active for safeguard.local')
        changes=plan_project(project)
        if LIB.is_symlink():raise ValueError('Runtime install directory must not be a symlink')
        for source in (ROOT/'runtime').glob('*.py'):
            target=LIB/source.name
            ast.parse(source.read_text())
            if target.is_symlink() or (target.exists() and digest(target)!=digest(source)):
                raise ValueError('Different service runtime exists: '+str(target))
        sys.path.insert(0,str(ROOT/'runtime'))
        from run_receiver import existing_identity
        tls=existing_identity(project)
        # The receiver must already own its TLS files; do not change ownership.
        for path in [project/'runtime/navigation_tls',*(project/'runtime/navigation_tls').iterdir()]:
            if path.is_symlink():raise ValueError('Unexpected TLS symlink')
            if path.stat().st_uid!=account.pw_uid:raise ValueError('TLS files must be owned by pi; no automatic ownership change performed')
        active=subprocess.run(['systemctl','is-active','--quiet',SERVICE]).returncode==0
        listening=subprocess.run(['ss','-H','-ltn','( sport = :8081 or sport = :8443 )'],capture_output=True,text=True,check=True)
        if listening.stdout.strip() and not active:
            raise ValueError('Manual receiver still running. Ctrl+C its terminal, then run this installer again.')
        if active:systemctl('stop',SERVICE)
        backup=None
        if changes:
            parent=project/'backups'
            if parent.is_symlink():raise ValueError('Backups directory must not be a symlink')
            backup=parent/('navigation_demo_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
            backup.mkdir(parents=True)
            for source,target in changes:
                shutil.copy2(target,backup/target.name)
            os.chown(backup,account.pw_uid,account.pw_gid)
        # Root-owned service programs; the HTTP server itself runs as pi.
        LIB.mkdir(parents=True,exist_ok=True);os.chmod(LIB,0o755);os.chown(LIB,0,0)
        for source in (ROOT/'runtime').glob('*.py'):atomic_write(LIB/source.name,source.read_bytes())
        for source,target in changes:
            old=target.stat();atomic_write(target,source.read_bytes(),uid=old.st_uid,gid=old.st_gid,mode=old.st_mode&0o777)
        atomic_write(UNIT,expected_unit.encode())
        systemctl('daemon-reload');systemctl('enable','--now',SERVICE)
        print(json.dumps({'installed':SERVICE,'changed_project_files':len(changes),'backup':str(backup) if backup else None,
                          'phone_url':'https://safeguard.local:8443/','ca_sha256':tls['fingerprint_sha256']},indent=2))
        print('Use: sudo journalctl -u safeguard-navigation -b -n 25 --no-pager')
        print('Service activation does not by itself prove phone connectivity. Keep the iPhone page visible during the demo.')
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        parser.exit(2,'Install stopped: '+str(error)+'\n')

if __name__=='__main__':main()
