#!/usr/bin/env python3
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def plan(project):
    result = []
    for relative, accepted in json.loads((ROOT/'base_hashes.json').read_text()).items():
        source, target = ROOT/'patch'/relative, project/relative
        if target.is_symlink() or project not in target.resolve().parents or not target.is_file():
            raise ValueError('Missing or unsafe project file: '+str(target))
        if digest(target) == digest(source):
            continue
        if digest(target) not in accepted:
            raise ValueError('Local changes found; refusing overwrite: '+relative)
        if source.suffix == '.py':
            ast.parse(source.read_text())
        result.append((source, target))
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=Path.home()/'SafeGuard_Main')
    args=parser.parse_args(); project=args.project.expanduser().resolve()
    try:
        changes=plan(project)
        sys.path.insert(0,str(ROOT/'runtime'))
        from run_receiver import existing_identity
        tls=existing_identity(project)
        listeners=subprocess.run(['ss','-H','-ltn','( sport = :8081 or sport = :8443 )'],capture_output=True,text=True,check=True)
        if listeners.stdout.strip():
            raise ValueError('Stop the old navigation receiver with Ctrl+C first. Other Pi programs can keep running.')
        backup=None
        if changes:
            parent=project/'backups'
            if parent.is_symlink():raise ValueError('Unsafe backup directory')
            backup=parent/('hotspot_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
            backup.mkdir(parents=True)
            for source,target in changes:shutil.copy2(target,backup/target.name)
            for source,target in changes:
                temporary=target.with_name(target.name+'.tmp-'+uuid.uuid4().hex)
                try:
                    with temporary.open('xb') as stream:stream.write(source.read_bytes())
                    os.chmod(temporary,target.stat().st_mode & 0o777)
                    temporary.replace(target)
                finally:
                    if temporary.exists():temporary.unlink()
        print('INSTALLED: Wi-Fi IPv6 listener fix')
        print('Changed files:',len(changes))
        print('Backup:',backup)
        print('Existing CA SHA256:',tls['fingerprint_sha256'])
        print('Next: python3 ~/SafeGuard_Navigation_Hotspot_Fix/start_fix.py --project ~/SafeGuard_Main')
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        parser.exit(2,'Install stopped: '+str(error)+'\n')

if __name__=='__main__':main()
