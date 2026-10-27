import importlib.util
import json
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
import run_receiver as runner
import prepare_network as network
import navigation_tls_identity as tls
spec=importlib.util.spec_from_file_location('demo_installer',ROOT/'install_demo.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class NetworkTests(unittest.TestCase):
    def test_exact_interface_usable_addresses(self):
        entries=[{'ifname':'eth0','operstate':'UP','addr_info':[{'family':'inet','local':'10.0.0.99'}]},
            {'ifname':'wlan0','operstate':'UP','addr_info':[
                {'family':'inet','local':'172.20.10.9'},
                {'family':'inet6','local':'fe80::1234','scope':'link'},
                {'family':'inet6','local':'2001:db8::1','scope':'global'},
                {'family':'inet6','local':'fe80::5','scope':'link','tentative':True}]}]
        fake=lambda *a,**k:types.SimpleNamespace(stdout=json.dumps(entries))
        self.assertEqual(runner.network_signature(fake),('172.20.10.9',('2001:db8::1','fe80::1234')))
        entries[1]['operstate']='DOWN'
        with self.assertRaises(ValueError):runner.network_signature(fake)

    def test_network_change_stops_only_child(self):
        child=mock.Mock();child.poll.return_value=None
        result=runner.monitor(child,('172.20.10.8',('fe80::1',)),[False],
                              inspect=lambda:('172.20.10.9',('fe80::1',)),pause=lambda t:None)
        self.assertEqual(result,75);child.send_signal.assert_called_once_with(signal.SIGINT)

    def test_loss_stops_child_and_requests_retry(self):
        child=mock.Mock();child.poll.return_value=None
        def unavailable():raise ValueError('down')
        self.assertEqual(runner.monitor(child,('old',()),[False],inspect=unavailable,pause=lambda t:None),75)
        child.send_signal.assert_called_once_with(signal.SIGINT)

    def test_service_stop_exits_cleanly(self):
        child=mock.Mock();child.poll.return_value=None
        self.assertEqual(runner.monitor(child,('old',()),[True],pause=lambda t:None),0)
        child.send_signal.assert_called_once_with(signal.SIGINT)

class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.project=Path(cls.temp.name)
        (cls.project/'scripts').mkdir();(cls.project/'scripts/navigation_bridge.py').write_text('# fixture')
        cls.original=tls.setup(cls.project,ip='172.20.10.8')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_dhcp_address_changes_do_not_replace_identity(self):
        directory=self.project/'runtime/navigation_tls'
        before={p.name:p.read_bytes() for p in directory.iterdir()}
        identity=runner.existing_identity(self.project)
        command=runner.receiver_command(self.project,'192.168.44.23',identity)
        self.assertEqual(command[command.index('--host')+1],'192.168.44.23')
        self.assertIn('--prefer-hostname',command)
        self.assertEqual(identity['fingerprint_sha256'],self.original['fingerprint_sha256'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in directory.iterdir()})
        tls.openssl('verify','-CAfile',identity['ca'],'-verify_hostname','safeguard.local',identity['cert'])
        with self.assertRaises(ValueError):
            tls.openssl('verify','-CAfile',identity['ca'],'-verify_hostname','unrelated.example',identity['cert'])

class InstallerTests(unittest.TestCase):
    def test_unit_has_unprivileged_receiver_and_network_recovery(self):
        unit=installer.unit_text(Path('/home/pi/SafeGuard_Main'),'pi')
        self.assertIn('User=pi',unit);self.assertIn('ExecStartPre=+/usr/bin/python3',unit)
        self.assertIn('RestartPreventExitStatus=78',unit);self.assertIn('KillSignal=SIGINT',unit)
        self.assertNotIn('safeguard_main --',unit)
        with self.assertRaises(ValueError):installer.unit_text(Path('/home/pi/x\nUser=root'),'pi')

    def test_project_plan_preserves_unknown_edits(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'scripts').mkdir()
            for f in (ROOT/'patch/scripts').iterdir():
                if f.is_file():shutil.copyfile(f,p/'scripts'/f.name)
            self.assertEqual(installer.plan_project(p),[])
            (p/'scripts/navigation_bridge.py').write_text('# teammate edits')
            with self.assertRaisesRegex(ValueError,'Local changes'):installer.plan_project(p)

if __name__=='__main__':unittest.main()
