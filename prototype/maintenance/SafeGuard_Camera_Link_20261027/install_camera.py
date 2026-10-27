"""Camera-only update. Default is a read-only compatibility check."""
import argparse
import ast
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
CONFIG = 'configs/real_navigation_control.json'
HUB = 'scripts/sensor_hub.py'
MARK = '    def camera_worker(self):\n'
INSERT = (MARK + '        if self.hardware.get("camera_backend") == "block_b_motion":\n'
          '            from block_b_camera_adapter import run\n'
          '            return run(self)\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ensure_idle():
    consumers = {'safeguard_main', 'sensor_hub.py', 'camera_motion.py',
                 'rpicam-hello', 'rpicam-vid', 'rpicam-still', 'check_camera.py'}
    for p in Path('/proc').glob('[0-9]*'):
        if int(p.name) == os.getpid():
            continue
        try:
            args = (p/'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        if any(Path(a.decode(errors='replace')).name in consumers for a in args if a):
            raise ValueError('Main/camera program is running (PID '+p.name+'). Stop it normally first.')


def make_plan(project):
    for rel, expected in json.loads((ROOT/'manifest.json').read_text())['sha256'].items():
        if sha((ROOT/rel).read_bytes()) != expected:
            raise ValueError('Package integrity error: '+rel)
    bases = json.loads((ROOT/'base_hashes.json').read_text())
    before = (project/HUB).read_bytes()
    code = before.decode('utf-8')
    # Accept either the exact uploaded main or the known prior radar adapter.
    original = code.replace(INSERT, MARK, 1) if INSERT in code else code
    if sha(original.encode()) not in bases['sensor_hub_sha256'] or original.count(MARK) != 1:
        raise ValueError('Different sensor_hub preserved. Send current source for merge.')
    patched = original.replace(MARK, INSERT, 1)
    ast.parse(patched)
    cfg = json.loads((project/CONFIG).read_text())
    if (cfg.get('mode') != 'REAL' or cfg.get('profile') != 'REAL'
            or cfg.get('manual_control', {}).get('enabled') is not True):
        raise ValueError('Expected existing REAL software-stop configuration')
    hardware = cfg['hardware']
    if hardware.get('camera_backend') not in (None, 'block_b_motion'):
        raise ValueError('Different camera backend preserved')
    defaults = dict(fps=10.0, pixel_thresh=25, ratio_thresh=0.01, light_thresh=0.6,
                    min_frames=3, hold_s=2.0, light_settle_s=1.0, roi=[0.0,0.0,1.0,1.0])
    if 'camera_motion' in hardware and hardware['camera_motion'] != defaults:
        raise ValueError('Custom camera settings preserved; review before installing')
    hardware.update(camera_enabled=True, camera_backend='block_b_motion', camera_motion=defaults)
    plan = {HUB: patched.encode(), CONFIG: (json.dumps(cfg, ensure_ascii=False, indent=2)+'\n').encode()}
    for p in (ROOT/'patch/scripts').glob('*.py'):
        ast.parse(p.read_text())
        rel = 'scripts/'+p.name
        target = project/rel
        if target.exists() and target.read_bytes() != p.read_bytes():
            raise ValueError('Different existing file preserved: '+rel)
        plan[rel] = p.read_bytes()
    for rel in plan:
        target = project/rel
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError('Symlink destination rejected: '+rel)
    return plan


def install(project):
    ensure_idle()
    plan = make_plan(project)
    with tempfile.TemporaryDirectory(prefix='safeguard-camera-check-') as directory:
        stage = Path(directory)
        for folder in ('scripts', 'tests'):
            shutil.copytree(project/folder, stage/folder)
        for rel, data in plan.items():
            p = stage/rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        shutil.copy2(ROOT/'tests/test_camera_adapter.py', stage/'tests/test_camera_adapter.py')
        for pattern in ('test_sensor_hub.py', 'test_camera_adapter.py'):
            subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(stage/'tests'),
                            '-p', pattern], check=True)
    ensure_idle()
    if make_plan(project) != plan:
        raise ValueError('Source changed during check; no files installed')
    changed = {rel: data for rel,data in plan.items()
               if not (project/rel).exists() or (project/rel).read_bytes() != data}
    if not changed:
        print('ALREADY INSTALLED. No changes.'); return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    backup = project/'backups'/('camera_link_'+stamp)
    backup.mkdir(parents=True)
    old = {}
    for rel in changed:
        target = project/rel
        old[rel] = (target.read_bytes(), target.stat().st_mode & 0o777) if target.exists() else None
        if target.exists():
            b = backup/rel; b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(target,b)
    (backup/'restore_manifest.json').write_text(json.dumps({
        'previously_absent': [rel for rel,v in old.items() if v is None],
        'installed_sha256': {rel:sha(v) for rel,v in changed.items()}}, indent=2))
    done = []
    try:
        for rel, data in changed.items():
            p = project/rel
            t = p.with_name(p.name+'.'+stamp)
            t.write_bytes(data); t.chmod(old[rel][1] if old[rel] else 0o644)
            t.replace(p); done.append(rel)
    except BaseException:
        for rel in reversed(done):
            p = project/rel
            if old[rel] is None: p.unlink(missing_ok=True)
            else: p.write_bytes(old[rel][0]); p.chmod(old[rel][1])
        raise
    print('INSTALLED: B camera motion adapter. Backup:',backup)
    print('No hardware or service was started. Run check_camera.py next.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.home()/'SafeGuard_Main')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        project = args.project.resolve()
        if args.apply:
            (project/'runtime').mkdir(exist_ok=True)
            with (project/'runtime/software_control.lock').open('a+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
                install(project)
        else:
            make_plan(project); print('COMPATIBLE. Read-only check; no installation/device access.')
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(2, str(exc)+'\n')
