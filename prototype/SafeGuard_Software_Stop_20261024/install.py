"""Stage/build/verify first, then back up and install. No service/reboot/MCU flashing."""
import argparse, datetime, hashlib, json, os, shutil, subprocess, tempfile, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PORT='/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def running(project):
 result=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   args=(p/'cmdline').read_bytes().split(b'\0')
   if any(Path(a.decode(errors='replace')).name in ('safeguard_main','sensor_hub.py') for a in args if a):
    if (p/'cwd').resolve()==project or any(str(project).encode() in a for a in args):result.append(int(p.name))
  except (OSError,RuntimeError):pass
 return result
def verify(project):
 if running(project):raise ValueError('This project main/hub is running. Stop only your main normally; do not reboot Pi or stop navigation.')
 manifest=json.loads((ROOT/'manifest.json').read_text())
 for rel,digest in manifest['sha256'].items():
  if sha(ROOT/rel)!=digest:raise ValueError('Package file damaged: '+rel)
 expected=json.loads((ROOT/'base_hashes.json').read_text())
 for rel,digest in expected.items():
  p=project/rel;patch=ROOT/'patch'/rel
  if p.is_symlink() or p.parent.is_symlink():raise ValueError('Refusing symlink: '+rel)
  actual=sha(p) if p.exists() else None
  if actual!=digest and (not patch.is_file() or actual!=sha(patch)):
   raise ValueError('Local work differs; preserved, needs merge: '+rel)
 for patch in (ROOT/'patch').rglob('*'):
  if patch.is_file():
   rel=str(patch.relative_to(ROOT/'patch'));target=project/rel
   if rel not in expected and target.exists() and sha(target)!=sha(patch):
    raise ValueError('New-file destination already contains other work: '+rel)
def install(project,port,angle,cmake):
 project=project.resolve();verify(project)
 if not shutil.which(cmake):raise ValueError('cmake missing. Install cmake and g++ on Pi first.')
 cfg=json.loads((project/'configs/real_navigation.json').read_text())
 if cfg.get('mode')!='REAL' or cfg.get('profile')!='REAL':raise ValueError('Expected REAL navigation config')
 cfg['hardware'].update(esp32_port=port,esp32_baud=115200,esp32_protocol='link')
 cfg['required']['esp32']=False  # old core couples this to physical ESTOP
 cfg['actuation'].update(enabled=True,servo_protect_deg=angle)
 cfg['manual_control']={'enabled':True,'version':1,'boot_policy':'held_until_explicit_resume'}
 cfg['dashboard'].update(enabled=True,host='127.0.0.1',port=8080)
 cfg['demo']['override_temperature']=False
 cfg['control_scope']={'physical_estop_installed':False,'physical_outputs_validated':False,
  'heartbeat_loss':'retain_fan_buzzer_disable_servo_pwm','software_stop':'latch_all_off',
  'servo_angle_calibrated_for_window':False}
 dest_cfg=project/'configs/real_navigation_control.json'
 if dest_cfg.exists() and json.loads(dest_cfg.read_text())!=cfg:
  raise ValueError('Existing real_navigation_control.json differs; preserved. Merge changes explicitly.')
 with tempfile.TemporaryDirectory(prefix='safeguard-stop-build-') as td:
  stage=Path(td)/'source';stage.mkdir()
  for folder in ('src','tests'):shutil.copytree(project/folder,stage/folder)
  shutil.copyfile(project/'CMakeLists.txt',stage/'CMakeLists.txt')
  shutil.copytree(ROOT/'patch/src',stage/'src',dirs_exist_ok=True)
  # Optional local JSON headers are carried from the reviewed Pi build if present.
  command=[cmake,'-S',str(stage),'-B',str(stage/'build')]
  cache=project/'build/CMakeCache.txt'
  if cache.exists():
   for line in cache.read_text().splitlines():
    if line.startswith('JSON_INCLUDE_DIR:PATH='):
     value=line.split('=',1)[1]
     if (Path(value)/'nlohmann/json.hpp').exists():command.append('-DJSON_INCLUDE_DIR='+value)
  subprocess.run(command,check=True)
  subprocess.run([cmake,'--build',str(stage/'build'),'-j2'],check=True)
  for test in ('test_core','test_input'):
   subprocess.run([str(stage/'build'/test)],check=True)
  verify(project)  # do not overwrite edits made while compiling
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
  backup=project/'backups'/('software_stop_'+stamp);backup.mkdir(parents=True)
  plan={str(p.relative_to(ROOT/'patch')):p.read_bytes() for p in (ROOT/'patch').rglob('*') if p.is_file()}
  plan['build/safeguard_main']=(stage/'build/safeguard_main').read_bytes()
  plan['configs/real_navigation_control.json']=(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n').encode()
  previous={};changed=[]
  for rel in plan:
   p=project/rel
   if p.is_symlink() or p.parent.is_symlink():raise ValueError('Refusing symlink destination: '+rel)
   previous[rel]=(p.read_bytes(),p.stat().st_mode) if p.exists() else None
   if p.exists():
    b=backup/rel;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
  (backup/'restore_manifest.json').write_text(json.dumps({'previously_absent':[k for k,v in previous.items() if v is None]},indent=2))
  try:
   for rel,data in plan.items():
    p=project/rel;p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.install-'+stamp);tmp.write_bytes(data)
    tmp.chmod(0o755 if rel=='build/safeguard_main' else 0o644);tmp.replace(p);changed.append(rel)
  except BaseException:
   for rel in reversed(changed):
    p=project/rel;old=previous[rel]
    if old is None:p.unlink(missing_ok=True)
    else:p.write_bytes(old[0]);p.chmod(old[1])
   raise
 print('INSTALLED: computer stop/resume + ESP32 protocol + servo command support')
 print('BACKUP:',backup)
 print('SERVO_PROTECT_DEG:',angle if angle is not None else 'disabled until angle explicitly configured')
 print('NEXT: upload firmware/SafeGuard_Software_Stop/SafeGuard_Software_Stop.ino to ESP32, then run run_control.py')
 print('Pi navigation service, original configs and physical firmware were not changed by this installer.')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=Path.home()/'SafeGuard_Main')
 p.add_argument('--port',default=PORT);p.add_argument('--servo-protect-angle',type=int,choices=range(45,136),metavar='45..135')
 p.add_argument('--cmake',default='cmake');a=p.parse_args()
 try:install(a.project,a.port,a.servo_protect_angle,a.cmake)
 except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as e:p.exit(2,str(e)+'\n')
