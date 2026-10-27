"""Explicitly configure the team's checked protection angle while main is stopped."""
import argparse, json, shutil, uuid
from pathlib import Path
from install import running
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=Path.home()/'SafeGuard_Main')
 p.add_argument('--angle',type=int,choices=range(45,136),required=True,metavar='45..135');a=p.parse_args()
 try:
  project=a.project.resolve()
  if running(project):raise ValueError('Click 전체 정지, wait for confirmation, then stop only this main before configuring the angle.')
  path=project/'configs/real_navigation_control.json';cfg=json.loads(path.read_text())
  if cfg.get('manual_control',{}).get('enabled') is not True:raise ValueError('Not a software-control config')
  backup=path.with_name(path.name+'.before-angle-'+uuid.uuid4().hex[:8]);shutil.copy2(path,backup)
  cfg['actuation']['servo_protect_deg']=a.angle
  tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
  print('PROTECTION_SERVO_ANGLE:',a.angle,'| BACKUP:',backup)
  print('This is a requested angle, not measured position or window opening distance.')
 except (OSError,ValueError,KeyError) as e:p.exit(2,str(e)+'\n')
