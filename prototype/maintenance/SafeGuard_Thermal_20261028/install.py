#!/usr/bin/env python3
"""Build and test in a staging copy, then install with backup and rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime
from patch_project import patch

HERE=Path(__file__).resolve().parent
FILES=['src/main.cpp','src/thermal_observer.hpp','scripts/dashboard.html',
       'build/safeguard_main','configs/real_navigation_control.json']

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def ensure_stopped():
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try: args=(p/'cmdline').read_bytes().split(b'\0')
        except OSError: continue
        names={Path(a.decode(errors='replace')).name for a in args if a}
        if names & {'safeguard_main','sensor_hub.py','run_control.py'}:
            raise RuntimeError('메인이 실행 중입니다. 전체 정지 확인 후 메인 창에서 Ctrl+C 하세요.')

def atomic_copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    temporary=dst.with_name(dst.name+'.thermal-tmp')
    shutil.copy2(src,temporary)
    os.replace(temporary,dst)

def restore(project,backup,force=False):
    manifest=json.loads((backup/'manifest.json').read_text())
    if str(project)!=manifest['project']: raise RuntimeError('백업 대상 경로가 다릅니다.')
    if not force:
        for name,expected in manifest['installed_hashes'].items():
            if digest(project/name)!=expected:
                raise RuntimeError('설치 후 변경된 파일이 있어 자동 복원을 중단합니다: '+name)
    for name in FILES:
        old=backup/name; target=project/name
        if old.exists(): atomic_copy(old,target)
        elif name in manifest['previously_absent'] and target.exists(): target.unlink()

def install(project):
    ensure_stopped()
    expected=json.loads((HERE/'supported_sources.json').read_text())
    for name,sha in expected.items():
        if digest(project/name)!=sha:
            raise RuntimeError('현재 코드가 확인된 기준 버전과 다릅니다. 덮어쓰지 않았습니다: '+name)
    if (project/'src/thermal_observer.hpp').exists(): raise RuntimeError('기존 열 예측 파일이 있습니다. 중복 설치하지 않습니다.')
    config_path=project/'configs/real_navigation_control.json'
    cfg=json.loads(config_path.read_text())
    if cfg.get('thermal',{}).get('risk_temp_c')!=35:
        raise RuntimeError('위험 온도 35°C 복원 후 설치하세요.')
    if cfg['thermal'].get('enabled') is not False or cfg['thermal'].get('calibrated') is not False:
        raise RuntimeError('기존 자동 예측 설정이 달라 중단합니다. 수동으로 변경하지 않았습니다.')
    before={name:digest(project/name) for name in FILES}
    with tempfile.TemporaryDirectory(prefix='.thermal-stage-',dir=project.parent) as td:
        stage=Path(td)/'project'
        shutil.copytree(project,stage,ignore=shutil.ignore_patterns('build','runs','runtime','.git',
            '__pycache__','*.log','.venv','venv','node_modules'))
        patch(stage)
        cfg['thermal']['literature_observer_enabled']=True
        (stage/'configs/real_navigation_control.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
        with (stage/'CMakeLists.txt').open('a') as f:
            f.write('\nadd_executable(test_thermal_observer tests/test_observer.cpp)\n'
                    'target_link_libraries(test_thermal_observer PRIVATE safeguard_core)\n'
                    'target_compile_options(test_thermal_observer PRIVATE -UNDEBUG)\n'
                    'add_test(NAME thermal_observer COMMAND test_thermal_observer)\n')
        shutil.copy2(HERE/'tests/test_observer.cpp',stage/'tests/test_observer.cpp')
        shutil.copy2(HERE/'tests/test_dashboard_research.js',stage/'tests/test_dashboard_research.js')
        subprocess.run(['cmake','-S',str(stage),'-B',str(stage/'build'),'-DBUILD_TESTING=ON'],check=True)
        subprocess.run(['cmake','--build',str(stage/'build'),'-j2'],check=True)
        subprocess.run(['ctest','--test-dir',str(stage/'build'),'--output-on-failure'],check=True)
        if shutil.which('node'):
            subprocess.run(['node',str(stage/'tests/test_dashboard_research.js')],check=True)
        ensure_stopped()
        if any(digest(project/n)!=h for n,h in before.items()):
            raise RuntimeError('빌드 중 원본 변경 감지. 설치 중단.')
        backup=project.parent/'SafeGuard_Thermal_Backups'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        backup.mkdir(parents=True)
        absent=[]
        for name in FILES:
            if (project/name).exists(): atomic_copy(project/name,backup/name)
            else: absent.append(name)
        manifest={'project':str(project),'previously_absent':absent,
                  'installed_hashes':{name:digest(stage/name) for name in FILES}}
        (backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
        try:
            for name in FILES: atomic_copy(stage/name,project/name)
            assert all(digest(project/n)==h for n,h in manifest['installed_hashes'].items())
        except BaseException:
            restore(project,backup,force=True)
            raise
        print('INSTALLED: 열 추정 화면/로그 활성화; 35°C 유지; 서보 각도 유지; 자동 예측 제어 OFF')
        print('BACKUP:',backup)
        print('ROLLBACK: python3',HERE/'install.py','--project',project,'--rollback',backup)
        print('메인은 자동 실행하지 않았습니다. ESP32 재업로드 불필요.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=Path.home()/'SafeGuard_Main')
    p.add_argument('--rollback',type=Path)
    a=p.parse_args(); project=a.project.resolve()
    ensure_stopped()
    if a.rollback: restore(project,a.rollback.resolve());print('ROLLBACK_OK')
    else: install(project)

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as e:
        raise SystemExit('설치 중단: '+str(e))
