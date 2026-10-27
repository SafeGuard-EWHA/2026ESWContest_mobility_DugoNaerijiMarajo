import sys
import unittest
import tempfile
import json
import types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
import run_receiver as runner
import navigation_tls_identity as tls

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


class AddressTests(unittest.TestCase):
    def test_global_address_included_in_network_signature(self):
        entries=[{'ifname':'wlan0','operstate':'UP','addr_info':[
            {'family':'inet','local':'172.20.10.8'},
            {'family':'inet6','scope':'link','local':'fe80::1'},
            {'family':'inet6','scope':'global','local':'2001:db8::1'},
            {'family':'inet6','scope':'global','local':'2001:db8::2','tentative':True}]}]
        result=runner.network_signature(lambda *a,**k:types.SimpleNamespace(stdout=json.dumps(entries)))
        self.assertEqual(result,('172.20.10.8',('2001:db8::1','fe80::1')))
