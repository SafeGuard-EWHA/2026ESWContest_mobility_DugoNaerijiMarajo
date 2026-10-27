#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime'))
from run_receiver import main
if __name__=='__main__':
    if '--project' not in sys.argv:
        sys.argv.extend(['--project',str(Path.home()/'SafeGuard_Main')])
    raise SystemExit(main())
