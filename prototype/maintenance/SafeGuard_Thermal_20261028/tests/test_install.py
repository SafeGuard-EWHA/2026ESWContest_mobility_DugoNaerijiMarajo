"""End-to-end installer/rollback test on a disposable copy, never on hardware."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

pkg=Path(__file__).resolve().parents[1]
base=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(pkg))
from install import install,restore,FILES

with tempfile.TemporaryDirectory(prefix='sg-installer-test-') as td:
    root=Path(td)/'SafeGuard_Main'
    shutil.copytree(base,root,ignore=shutil.ignore_patterns('build','runs','runtime','.git','__pycache__'))
    p=root/'configs/real_navigation_control.json'
    c=json.loads(p.read_text());c['thermal']['risk_temp_c']=35;c['thermal']['enabled']=False
    c['thermal']['calibrated']=False;c['actuation']['servo_protect_deg']=80
    p.write_text(json.dumps(c))
    original={n:(root/n).read_bytes() if (root/n).exists() else None for n in FILES}
    install(root)
    saved=json.loads(p.read_text())
    assert saved['actuation']==c['actuation'] and saved['thermal']['risk_temp_c']==35
    assert saved['thermal']['literature_observer_enabled'] and not saved['thermal']['enabled']
    backup=next((Path(td)/'SafeGuard_Thermal_Backups').iterdir())
    # A post-install edit is protected from rollback.
    main=root/'src/main.cpp'; main.write_text(main.read_text()+'\n// user edit\n')
    try: restore(root,backup)
    except RuntimeError: pass
    else: raise AssertionError('rollback overwrote a later edit')
    main.write_text(main.read_text().removesuffix('\n// user edit\n'))
    restore(root,backup)
    for n,contents in original.items():
        assert ((root/n).read_bytes() if (root/n).exists() else None)==contents,n
    # Unknown sources must be rejected before any source/config writes.
    main.write_text(main.read_text()+'\n// unsupported version\n')
    pre=p.read_bytes()
    try: install(root)
    except RuntimeError: pass
    else: raise AssertionError('unsupported source accepted')
    assert p.read_bytes()==pre
print('PASS: staged build/CTest, config preservation, verified install, rollback, later-edit protection, unknown-version refusal')
