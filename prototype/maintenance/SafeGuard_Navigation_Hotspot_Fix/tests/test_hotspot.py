import importlib.util
import ipaddress
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest import mock
from test_navigation_ipv6 import nav

ROOT=Path(__file__).resolve().parents[1]

class HotspotTests(unittest.TestCase):
    def test_only_usable_interface_unicast_bindings(self):
        entries=[{'ifname':'wlan0','ifindex':3,'addr_info':[
            {'family':'inet6','scope':'link','local':'fe80::1'},
            {'family':'inet6','scope':'global','local':'2001:db8:1::1','prefixlen':64},
            {'family':'inet6','scope':'global','local':'2001:db8:1::2','prefixlen':64,'tentative':True},
            {'family':'inet6','scope':'global','local':'2001:db8:2::1','prefixlen':32},
            {'family':'inet6','scope':'global','local':'ff02::1','prefixlen':64}]}]
        with mock.patch.object(nav.socket,'if_nametoindex',return_value=3),mock.patch.object(nav.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=json.dumps(entries))):
            bindings=nav.wlan_ipv6_bindings('wlan0')
        self.assertEqual(len(bindings),2)
        self.assertEqual(bindings[1],('2001:db8:1::1',0,(ipaddress.ip_network('2001:db8:1::/64'),)))

    def test_global_listener_rejects_outside_wifi_prefix(self):
        server=object.__new__(nav.IPv6BridgeServer)
        server.server_address=('2001:db8:1::1',8443,0,0)
        server.allowed_peer_networks=(ipaddress.ip_network('2001:db8:1::/64'),)
        self.assertTrue(server.verify_request(None,('2001:db8:1::99',12,0,0)))
        self.assertFalse(server.verify_request(None,('2001:db8:2::99',12,0,0)))
        server.allowed_peer_networks=()
        self.assertFalse(server.verify_request(None,('2001:db8:1::99',12,0,0)))

    def test_installer_known_files_idempotence_and_local_edits(self):
        spec=importlib.util.spec_from_file_location('hotfix_install',ROOT/'install_fix.py')
        install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
        with tempfile.TemporaryDirectory() as d:
            project=Path(d);(project/'scripts').mkdir()
            for source in (ROOT/'patch/scripts').glob('*'):
                if source.is_file():shutil.copyfile(source,project/'scripts'/source.name)
            self.assertEqual(install.plan(project),[])
            (project/'scripts/navigation_bridge.py').write_text('# teammate changes')
            with self.assertRaisesRegex(ValueError,'Local changes'):install.plan(project)

if __name__=='__main__':unittest.main()
