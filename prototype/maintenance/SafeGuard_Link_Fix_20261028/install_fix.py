"""Install reviewed Python link fixes; never starts main or enables outputs."""
import argparse,datetime,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CONFIG='SafeGuard_Main/configs/real_navigation_control.json'
def digest(data):return hashlib.sha256(data).hexdigest()
def stopped(home):
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:args=(p/'cmdline').read_bytes().split(b'\0')
  except OSError:continue
  names=[a.decode(errors='replace').rsplit('/',1)[-1] for a in args]
  if any(n in names for n in ('safeguard_main','sensor_hub.py','safeguard_uwb_reader.py','run_control.py')):
   raise RuntimeError('Main/reader still running. Confirm physical outputs OFF; stop main before install.')
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.linkfix-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,path.stat().st_mode & 0o777 if path.exists() else 0o644)
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--home',type=Path,default=Path.home());ap.add_argument('--rollback',type=Path);a=ap.parse_args()
 home=a.home.resolve();stopped(home)
 if a.rollback:
  folder=a.rollback.resolve();record=json.loads((folder/'record.json').read_text())
  if record['home']!=str(home):raise RuntimeError('Backup belongs to another home')
  for rel,info in record['files'].items():
   p=home/rel
   if not p.exists() or digest(p.read_bytes())!=info['installed_sha256']:raise RuntimeError('Changed after install: '+rel)
  for rel,info in record['files'].items():
   p=home/rel
   if info['existed']:atomic(p,(folder/rel).read_bytes())
   else:p.unlink()
  print('ROLLED BACK. Original config restored (may contain test 18C/servo80). Do not start until reviewed.');return
 hashes=json.loads((ROOT/'base_hashes.json').read_text());payload={}
 for rel,expected in hashes.items():
  p=home/rel
  actual=digest(p.read_bytes()) if p.exists() else None
  if actual!=expected:raise RuntimeError('Source differs from supplied snapshot: '+rel+'; no files changed.')
  data=(ROOT/rel).read_bytes();compile(data,rel,'exec');payload[rel]=data
 c=json.loads((home/CONFIG).read_text())
 if c['thermal']['enabled'] is not False or c['manual_control']['enabled'] is not True:raise RuntimeError('Unexpected safety config; no files changed')
 if c['thermal']['risk_temp_c'] not in (18,35) or c['actuation']['servo_protect_deg'] not in (None,80):raise RuntimeError('Unexpected test settings; no files changed')
 c['thermal']['risk_temp_c']=35.0;c['actuation']['servo_protect_deg']=None
 payload[CONFIG]=(json.dumps(c,ensure_ascii=False,indent=2)+'\n').encode()
 subprocess.run([sys.executable,str(ROOT/'test_links.py')],check=True)
 folder=home/'SafeGuard_Link_Backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
 folder.mkdir(parents=True)
 record={'home':str(home),'files':{}}
 for rel,data in payload.items():
  p=home/rel;exists=p.exists()
  if exists:
   b=folder/rel;b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(p.read_bytes())
  record['files'][rel]={'existed':exists,'installed_sha256':digest(data)}
 (folder/'record.json').write_text(json.dumps(record,indent=2))
 changed=[]
 try:
  for rel,data in payload.items():atomic(home/rel,data);changed.append(rel)
 except BaseException:
  for rel in reversed(changed):
   if record['files'][rel]['existed']:atomic(home/rel,(folder/rel).read_bytes())
   else:(home/rel).unlink(missing_ok=True)
  raise
 print('BACKUP:',folder)
 print('INSTALLED: 35C restored; prediction remains OFF; servo protection angle=None.')
 print('Main NOT started. MCU firmware, network, camera adapter and C++ code unchanged.')
 print('ROLLBACK: python3 '+str(ROOT/'install_fix.py')+' --rollback '+str(folder))
if __name__=='__main__':
 try:main()
 except Exception as e:raise SystemExit('INSTALL STOPPED: '+str(e))
