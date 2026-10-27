from pathlib import Path
import sys
import tempfile
import types
import json
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
import prepare_network as network
import run_receiver as receiver

class BootNetworkTests(unittest.TestCase):
    def test_disabled_ipv6_enabled_restored_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            state={'accept_ra':0,'autoconf':0,'disable_ipv6':1};original=dict(state);writes=[]
            def write(values):writes.append(dict(values));state.update(values)
            kwargs=dict(read=lambda:dict(state),write=write,record=Path(directory)/'saved')
            network.prepare(**kwargs)
            self.assertEqual(state,{'accept_ra':2,'autoconf':1,'disable_ipv6':0})
            network.prepare(**kwargs);self.assertEqual(len(writes),1)
            network.prepare(restore=True,**kwargs);self.assertEqual(state,original)
            self.assertFalse(kwargs['record'].exists())

    def test_already_working_addresses_do_not_require_disabling_ipv6(self):
        with tempfile.TemporaryDirectory() as directory:
            state={'accept_ra':1,'autoconf':1,'disable_ipv6':0};writes=[]
            def write(values):writes.append(values);state.update(values)
            network.prepare(read=lambda:dict(state),write=write,record=Path(directory)/'saved')
            self.assertTrue(all(v['disable_ipv6']==0 for v in writes))

    def test_restore_does_not_overwrite_external_change(self):
        with tempfile.TemporaryDirectory() as directory:
            state={'accept_ra':0,'autoconf':1,'disable_ipv6':1}
            kwargs=dict(read=lambda:dict(state),write=state.update,record=Path(directory)/'saved')
            network.prepare(**kwargs);state['autoconf']=0
            with self.assertRaisesRegex(ValueError,'changed elsewhere'):network.prepare(restore=True,**kwargs)
            self.assertEqual(state['autoconf'],0)

    def test_link_local_only_waits_instead_of_claiming_phone_ready(self):
        data=[{'ifname':'wlan0','operstate':'UP','addr_info':[
            {'family':'inet','local':'172.20.10.8'},
            {'family':'inet6','scope':'link','local':'fe80::1'}]}]
        fake=lambda *a,**k:types.SimpleNamespace(stdout=json.dumps(data))
        with self.assertRaisesRegex(ValueError,'global IPv6'):receiver.network_signature(fake)
        data[0]['addr_info'].append({'family':'inet6','scope':'global','local':'2001:db8::1'})
        self.assertIn('2001:db8::1',receiver.network_signature(fake)[1])

if __name__=='__main__':unittest.main()
