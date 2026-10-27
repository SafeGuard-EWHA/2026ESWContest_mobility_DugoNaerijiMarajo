"""Default: compatibility check. --apply: build/test/back up/install; radar stays disabled in existing configs."""
import argparse, datetime, hashlib, json, os, shutil, subprocess, tempfile, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(project):
 for rel,value in json.loads((ROOT/'manifest.json').read_text())['sha256'].items():
  if digest(ROOT/rel)!=value:raise ValueError('Damaged package: '+rel)
 expected=json.loads((ROOT/'base_hashes.json').read_text())
 for rel,sha in expected.items():
  p=project/rel;new=ROOT/'patch'/rel
  if p.is_symlink() or p.parent.is_symlink():raise ValueError('Symlink destination: '+rel)
  actual=digest(p) if p.is_file() else None
  if actual!=sha and not(new.is_file() and actual==digest(new)):
   raise ValueError('Different/missing source preserved: '+rel+'; Pi Software Stop update must be installed first, then local changes merged.')
 for p in (ROOT/'patch').rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts:continue
  rel=p.relative_to(ROOT/'patch');target=project/rel
  if str(rel) not in expected and target.exists() and digest(target)!=digest(p):
   raise ValueError('New filename already contains different work: '+str(rel))
 for p in Path('/proc').glob('[0-9]*'):
  if int(p.name)==os.getpid():continue
  try:
   args=(p/'cmdline').read_bytes().split(b'\0')
   if any(Path(x.decode(errors='replace')).name in ('safeguard_main','sensor_hub.py') for x in args if x):
    if (p/'cwd').resolve()==project or any(str(project).encode() in x for x in args):
     raise ValueError('Main/hub is running. Stop this main normally first. Leave navigation service alone.')
  except (OSError,RuntimeError):pass
 return True

def install(project,cmake):
 verify(project)
 with tempfile.TemporaryDirectory(prefix='safeguard-b-build-') as td:
  stage=Path(td)/'stage';stage.mkdir()
  for folder in ('src','tests','scripts'):shutil.copytree(project/folder,stage/folder)
  shutil.copy2(project/'CMakeLists.txt',stage/'CMakeLists.txt')
  for p in (ROOT/'patch').rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:
    dest=stage/p.relative_to(ROOT/'patch');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
  (stage/'tests/test_radar_main.cpp').write_text((ROOT/'tests/test_radar_main.cpp').read_text().replace('../patch/src/main.cpp','../src/main.cpp'))
  with (stage/'CMakeLists.txt').open('a') as f:
   f.write('\nadd_executable(test_radar_main tests/test_radar_main.cpp)\ntarget_link_libraries(test_radar_main PRIVATE safeguard_core)\ntarget_compile_options(test_radar_main PRIVATE -UNDEBUG)\n')
  command=[cmake,'-S',str(stage),'-B',str(stage/'build'),'-DCMAKE_BUILD_TYPE=Debug']
  cache=project/'build/CMakeCache.txt'
  if cache.is_file():
   for line in cache.read_text().splitlines():
    if line.startswith('JSON_INCLUDE_DIR:PATH='):
     value=line.split('=',1)[1]
     if (Path(value)/'nlohmann/json.hpp').is_file():command.append('-DJSON_INCLUDE_DIR='+value)
  subprocess.run(command,check=True)
  subprocess.run([cmake,'--build',str(stage/'build'),'-j2'],check=True)
  for name in ('test_core','test_input','test_radar_main'):subprocess.run([str(stage/'build'/name)],check=True)
  subprocess.run(['python3',str(ROOT/'self_check.py')],check=True)
  subprocess.run(['python3','-m','unittest','discover','-s',str(stage/'tests'),'-p','test_sensor_hub.py'],check=True)
  verify(project)
  plan={str(p.relative_to(ROOT/'patch')):p.read_bytes() for p in (ROOT/'patch').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
  plan['build/safeguard_main']=(stage/'build/safeguard_main').read_bytes()
  for rel in plan:
   p=project/rel
   if p.is_symlink() or p.parent.is_symlink():raise ValueError('Symlink destination: '+rel)
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
  backup=project/'backups'/('block_b_input_'+stamp);backup.mkdir(parents=True)
  old={}
  for rel in plan:
   p=project/rel;old[rel]=(p.read_bytes(),p.stat().st_mode) if p.exists() else None
   if p.exists():
    dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
  (backup/'restore_manifest.json').write_text(json.dumps({'previously_absent':[k for k,v in old.items() if v is None]},indent=2))
  changed=[]
  try:
   for rel,contents in plan.items():
    p=project/rel;p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.'+stamp);temp.write_bytes(contents)
    temp.chmod(0o755 if rel.startswith('build/') else 0o644);temp.replace(p);changed.append(rel)
  except BaseException:
   for rel in reversed(changed):
    p=project/rel
    if old[rel] is None:p.unlink(missing_ok=True)
    else:p.write_bytes(old[rel][0]);p.chmod(old[rel][1])
   raise
 print('Installed radar adapter and continuity handling. Backup:',backup)
 print('No config was changed. No radar, ESP32, camera or network service was started.')
 print('Actual firmware/profile/occupancy validation is still required before enabling radar.')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True)
 p.add_argument('--apply',action='store_true');p.add_argument('--cmake',default='cmake');args=p.parse_args()
 try:
  project=args.project.resolve()
  if args.apply:install(project,args.cmake)
  else:verify(project);print('COMPATIBLE. Check only; no installation or device access.')
 except (OSError,ValueError,subprocess.CalledProcessError) as e:p.exit(2,str(e)+'\n')
