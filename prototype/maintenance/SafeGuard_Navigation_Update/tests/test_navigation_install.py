"""Installer preflight, preservation, backup and repeatability contract."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('navigation_installer',ROOT/'install_navigation.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)/'project';self.package=Path(self.tmp.name)/'package'
        (self.project/'scripts').mkdir(parents=True);(self.project/'configs').mkdir()
        (self.package/'patch/scripts').mkdir(parents=True)
        (self.project/'scripts/dependency.py').write_text('dependency = 1\n')
        (self.project/'scripts/changed.py').write_text('old = 1\n')
        (self.package/'patch/scripts/changed.py').write_text('new = 1\n')
        (self.package/'patch/scripts/new.py').write_text('new = 2\n')
        hashes={'dependencies':{'scripts/dependency.py':installer.digest(self.project/'scripts/dependency.py')},
                'files':{'scripts/changed.py':installer.digest(self.project/'scripts/changed.py'),'scripts/new.py':None}}
        (self.package/'base_hashes.json').write_text(json.dumps(hashes))
        self.base={'mode':'REAL','profile':'REAL','hardware':{'camera_enabled':True,'uwb_port':'/dev/custom'},
             'required':{'uwb':True},'thermal':{'enabled':True,'other':25},'actuation':{'enabled':True},
             'ambient_provider':{'latitude':37.5,'longitude':127.}}
        (self.project/'configs/real_ambient.json').write_text(json.dumps(self.base))
    def install(self): return installer.install(self.project,package=self.package)
    def test_preserve_hardware_original_config_and_backup(self):
        result=self.install();cfg=json.loads(Path(result['config']).read_text())
        self.assertEqual(cfg['hardware'],self.base['hardware']);self.assertEqual(cfg['required'],self.base['required'])
        self.assertFalse(cfg['actuation']['enabled']);self.assertFalse(cfg['thermal']['enabled'])
        self.assertNotIn('latitude',cfg['ambient_provider']);self.assertEqual(cfg['ambient_provider']['location_timeout_s'],15)
        self.assertEqual(json.loads((self.project/'configs/real_ambient.json').read_text()),self.base)
        self.assertEqual((Path(result['backup'])/'scripts/changed.py').read_text(),'old = 1\n')
        self.assertEqual(self.install()['changed_files'],0)
    def test_teammate_edit_aborts_before_any_change(self):
        (self.project/'scripts/changed.py').write_text('teammate = 9\n')
        with self.assertRaisesRegex(ValueError,'Local code differs'):self.install()
        self.assertFalse((self.project/'scripts/new.py').exists());self.assertFalse((self.project/'configs/real_navigation.json').exists())
    def test_dependency_mismatch_aborts(self):
        (self.project/'scripts/dependency.py').write_text('modified = 1\n')
        with self.assertRaisesRegex(ValueError,'dependency'):self.install()
        self.assertEqual((self.project/'scripts/changed.py').read_text(),'old = 1\n')
    def test_existing_output_config_never_silently_overwritten(self):
        (self.project/'configs/real_navigation.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Output config differs'):self.install()
        self.assertEqual((self.project/'scripts/changed.py').read_text(),'old = 1\n')
    def test_symlink_target_is_rejected(self):
        target=self.project/'scripts/new.py';target.symlink_to(self.project/'scripts/changed.py')
        with self.assertRaisesRegex(ValueError,'Symlink'):self.install()
        self.assertEqual((self.project/'scripts/changed.py').read_text(),'old = 1\n')

if __name__=='__main__':unittest.main()
