"""Launch the existing main with the navigation + computer control config."""
import argparse, fcntl, json, os, socket, subprocess
from pathlib import Path
from install import running
from check_link import check
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=Path.home()/'SafeGuard_Main');a=p.parse_args()
 project=a.project.resolve()
 try:
  if running(project):raise ValueError('Your project main/hub is already running; use its dashboard. Do not start a second copy.')
  (project/'runtime').mkdir(exist_ok=True)
  lock=(project/'runtime/software_control.lock').open('a+')
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with socket.socket() as s:s.bind(('127.0.0.1',8080))
  cfg=project/'configs/real_navigation_control.json'
  settings=json.loads(cfg.read_text())
  if settings.get('manual_control',{}).get('enabled') is not True:raise ValueError('Install software-stop package first.')
  check(settings['hardware']['esp32_port'])
  print('DASHBOARD through SSH tunnel: http://127.0.0.1:8080/',flush=True)
  print('Starts HELD. Confirm ESP32 stopped, then click 감시 재개.',flush=True)
  print('Before Ctrl+C / closing SSH: click 전체 정지 and wait for 정지 확인됨.',flush=True)
  result=subprocess.run([str(project/'build/safeguard_main'),'--config',str(cfg)],cwd=project,pass_fds=(lock.fileno(),))
  raise SystemExit(result.returncode)
 except KeyboardInterrupt:
  print('\nMain stopped. This message alone does not confirm the physical outputs stopped.')
 except (OSError,ValueError) as e:p.exit(2,str(e)+'\n')
