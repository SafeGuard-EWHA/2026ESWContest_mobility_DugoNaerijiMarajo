"""Generate a reviewable, non-installed systemd bundle for an isolated Pi copy."""
import argparse
from pathlib import Path
import re


def units(project):
    if not re.fullmatch(r'/home/pi/[A-Za-z0-9_-]+',project):
        raise ValueError('Use a simple isolated project directory under /home/pi')
    common='''[Unit]
Description={description}
After=local-fs.target
PartOf=safeguard.target

[Service]
Type=simple
User=pi
WorkingDirectory={project}
UMask=0077
Environment=PYTHONUNBUFFERED=1
ExecStart={command}
Restart=on-failure
RestartSec=5
RestartPreventExitStatus=78
KillSignal=SIGINT
KillMode=mixed
TimeoutStopSec=15

[Install]
WantedBy=safeguard.target
'''
    result={}
    for name,script in [('main','run_managed.py'),('portal','access_portal.py')]:
        result[f'safeguard-{name}.service']=common.format(description=f'SafeGuard {name}',project=project,
            command=f'/usr/bin/python3 {project}/scripts/{script} --project {project}')
    result['safeguard.target']='''[Unit]
Description=SafeGuard controller, navigation and access portal
Wants=safeguard-main.service safeguard-navigation.service safeguard-portal.service

[Install]
WantedBy=multi-user.target
'''
    # Reuse the existing navigation service, replace only its launch command.
    # Never introduce a second receiver or remove the already disabled network prep.
    result['navigation-override.conf']=f'''[Unit]
PartOf=safeguard.target

[Service]
WorkingDirectory={project}
ExecStart=
ExecStart=/usr/bin/python3 /usr/local/lib/safeguard-navigation/run_receiver.py --project {project}
ExecStartPre=
'''
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',default='/home/pi/SafeGuard_Operational_20261030')
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'deployment/systemd')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    for name,text in units(a.project).items(): (a.output/name).write_text(text,encoding='utf-8',newline='\n')
    print('Generated only; no Pi files or services changed:',a.output)
