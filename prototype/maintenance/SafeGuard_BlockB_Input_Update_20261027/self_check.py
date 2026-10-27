"""Offline parser/worker checks. No device is opened and no files are installed."""
from pathlib import Path
import unittest
if __name__=='__main__':
 root=Path(__file__).resolve().parent
 tests=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_radar.py')
 result=unittest.TextTestRunner(verbosity=2).run(tests)
 print('SOFTWARE FIXTURES ONLY: no real radar, occupancy or physical outputs validated.')
 raise SystemExit(0 if result.wasSuccessful() else 1)
