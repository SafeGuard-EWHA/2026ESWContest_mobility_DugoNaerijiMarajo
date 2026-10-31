#!/usr/bin/env python3
"""Future deployment preparation only: new directory, build/tests, same TLS identity.
Does not install/enable/start/stop services or run hardware programs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from prepare_services import units

ROOT=Path(__file__).resolve().parent


def project_config(config,destination):
    result=json.loads(json.dumps(config))
    result['ambient_provider']['location_file']=str(Path(destination).resolve()/'runtime/navigation_location.json')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=Path('/home/pi/SafeGuard_Operational_20261030'))
    args=parser.parse_args()
    if sys.platform!='linux' or os.geteuid()==0:
        parser.error('Run on Pi as pi, not root. This is never a Windows deployment tool.')
    destination=args.destination
    if destination.parent!=Path('/home/pi') or destination.is_symlink() or destination.exists():
        parser.error('Use a new, absent directory directly under /home/pi. Existing files are preserved.')
    units(str(destination))  # Validate service paths before writing anything.
    baseline=json.loads((ROOT/'baseline_main_sha256.json').read_text())
    for relative,digest in baseline.items():
        source=Path('/home/pi/SafeGuard_Main')/relative
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            parser.error('Pi source changed since inspection; review before staging: '+relative)
    sys.path.insert(0,'/usr/local/lib/safeguard-navigation')
    from run_receiver import existing_identity
    existing_identity('/home/pi/SafeGuard_Main')  # Includes cert/key/CA/profile/name/expiry checks.
    shutil.copytree(ROOT/'SafeGuard_Main',destination,
        ignore=shutil.ignore_patterns('__pycache__','build','runs','runtime'))
    config_path=destination/'configs/real_navigation_control.json'
    config_path.write_text(json.dumps(project_config(json.loads(config_path.read_text()),destination),indent=2)+'\n')
    runtime=destination/'runtime';runtime.mkdir(mode=0o700)
    maintenance=destination/'maintenance';maintenance.mkdir(exist_ok=True)
    for name in ('prepare_services.py','stage_on_pi.py'):
        shutil.copy2(ROOT/name,maintenance/name)
    shutil.copytree('/home/pi/SafeGuard_Main/runtime/navigation_tls',runtime/'navigation_tls')
    # Preserve phone pairing if this future deployment follows an already-patched version.
    for name in ('navigation_auth.json','portal_auth.json'):
        source=Path('/home/pi/SafeGuard_Main/runtime')/name
        if source.is_file(): shutil.copy2(source,runtime/name);os.chmod(runtime/name,0o600)
    subprocess.run(['cmake','-S',str(destination),'-B',str(destination/'build'),
        '-DJSON_INCLUDE_DIR='+str(ROOT/'third_party'),'-DCMAKE_BUILD_TYPE=Debug'],check=True)
    subprocess.run(['cmake','--build',str(destination/'build'),'-j2'],check=True)
    subprocess.run(['ctest','--test-dir',str(destination/'build'),'--output-on-failure'],check=True)
    out=destination/'deployment/systemd';out.mkdir(parents=True)
    for name,content in units(str(destination)).items():(out/name).write_text(content)
    print('Staged and tested source in',destination)
    print('No services changed. Existing Main and Filming folders preserved.')
    print('Initialize portal password before service activation; retain the existing certificate trust.')


if __name__=='__main__':main()
