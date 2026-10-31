import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT.parent))
sys.path.insert(0,str(ROOT/'maintenance'))
import access_portal as portal
import dashboard
import navigation_bridge as nav
from navigation_session import atomic_json
import run_managed
from prepare_services import units
from stage_on_pi import project_config
from connection_status import ConnectionStatus
from navigation_ambient import PhoneAmbientProvider


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.time=1800000000.
    def tearDown(self):self.temp.cleanup()
    def store(self):
        return nav.LocationStore(self.root/'location.json',wall_clock=lambda:self.time,clock=lambda:1000,
            pairing_code='87654321',auth_file=self.root/'auth.json',pairing_info_file=self.root/'pairing.json',
            rotation_file=self.root/'reset.json')
    def test_restart_keeps_auth_but_invalidates_position_and_code_not_reused(self):
        first=self.store();token=first.pair({'code':'87654321'})['token']
        first.accept({'seq':1,'valid':True,'latitude':37.,'longitude':127.,'accuracy_m':10,'position_timestamp_ms':self.time*1000})
        second=self.store()
        self.assertTrue(second.authorized('Bearer '+token))
        self.assertFalse(second.status()['location']['valid'])
        self.assertNotIn(token,(self.root/'auth.json').read_text())
        self.assertIsNone(json.loads((self.root/'pairing.json').read_text())['code'])
        with self.assertRaises(nav.BridgeError):second.pair({'code':'87654321'})
        second.accept({'seq':2,'valid':True,'latitude':37.,'longitude':127.,'accuracy_m':10,'position_timestamp_ms':self.time*1000})
        self.assertTrue(second.status()['location']['valid'])
        self.time+=16
        self.assertFalse(second.status()['location']['valid'])
    def test_expiry_and_explicit_reset(self):
        store=self.store();token=store.pair({'code':'87654321'})['token']
        self.time+=7*86400
        self.assertFalse(store.authorized('Bearer '+token))
        atomic_json(self.root/'reset.json',{'reset':True});store.maintenance()
        self.assertFalse(store.authorized('Bearer '+token));self.assertFalse((self.root/'reset.json').exists())
        code=json.loads((self.root/'pairing.json').read_text())['code']
        self.assertEqual(len(code),8)
        new=store.pair({'code':code})['token'];self.assertTrue(store.authorized('Bearer '+new))
        self.assertFalse(store.authorized('Bearer '+token))


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.actions=[]
        self.state=self.root/'state.json';self.state.write_text(json.dumps({'thermal_observer':{'history_s':600},'counter':91}))
        self.backend=dashboard.start_dashboard(self.state,{'enabled':True,'port':0},self.actions.append)
        self.record=portal.Login.create('unit-test-password-only')
        self.login=portal.Login(self.record)
        self.server=portal.ThreadingHTTPServer(('127.0.0.1',0),portal.handler(self.login,self.root,
            upstream=('127.0.0.1',self.backend.server_address[1])))
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()
        self.cookie=''
    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        if self.backend:self.backend.shutdown();self.backend.server_close()
        self.temp.cleanup()
    def request(self,path='/',body=None,host='safeguard.local:9443',origin='https://safeguard.local:9443'):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=4)
        headers={'Host':host,'Cookie':self.cookie}
        if body is not None:headers.update(Origin=origin,**{'Content-Type':'application/json'})
        conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
        response=conn.getresponse();result=(response.status,response.read(),dict(response.getheaders()));conn.close();return result
    def signin(self):
        status,body,headers=self.request('/api/login',{'password':'unit-test-password-only'})
        self.assertEqual(status,200);self.cookie=headers['Set-Cookie'].split(';')[0]
        self.assertIn('Secure; HttpOnly; SameSite=Strict',headers['Set-Cookie'])
    def test_auth_and_origin_gate_real_control_callback(self):
        self.assertEqual(self.request('/api/state')[0],401)
        self.assertEqual(self.request('/api/control',{'action':'manual_stop'})[0],401)
        self.assertEqual(self.actions,[])
        self.signin()
        self.assertEqual(self.request('/api/control',{'action':'manual_stop'},origin='https://other.invalid')[0],403)
        self.assertEqual(self.request('/api/state',host='other.invalid')[0],403)
        self.assertEqual(self.actions,[])
        self.assertEqual(self.request('/api/control',{'action':'manual_stop'})[0],202)
        self.assertEqual(len(self.actions),1)
        self.assertEqual(self.request('/api/control',{'action':'manual_resume'})[0],400)
        self.assertEqual(len(self.actions),1)
        self.assertEqual(self.request('/dashboard')[0],200)
    def test_reconnect_preserves_backend_history_and_portal_survives_backend_loss(self):
        self.signin()
        for _ in range(3):
            state=json.loads(self.request('/api/state')[1]);self.assertEqual(state['thermal_observer']['history_s'],600)
            self.assertEqual(state['counter'],91)
        self.assertEqual(self.actions,[])
        self.backend.shutdown();self.backend.server_close();self.backend=None
        self.assertEqual(self.request('/api/state')[0],503)
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.actions,[])
    def test_pairing_code_only_after_login_and_reset_is_file_request(self):
        atomic_json(self.root/'navigation_pairing.json',{'paired':False,'code':'87654321'})
        self.assertEqual(self.request('/api/pairing')[0],401);self.signin()
        self.assertEqual(json.loads(self.request('/api/pairing')[1])['code'],'87654321')
        self.assertEqual(self.request('/api/pairing/reset',{})[0],202)
        self.assertTrue((self.root/'navigation_pairing_reset.json').exists());self.assertEqual(self.actions,[])
    def test_signed_session_persists_across_portal_restart_expires_and_resists_tamper(self):
        self.signin();restored=portal.Login(self.record)
        self.assertTrue(restored.valid(self.cookie));self.assertFalse(restored.valid(self.cookie+'x'))
        expired=portal.Login(self.record,clock=lambda:self.login.clock()+portal.SESSION_SECONDS+1)
        self.assertFalse(expired.valid(self.cookie))

    def test_connection_check_never_forwards_control_even_with_live_backend(self):
        class Monitor:
            def snapshot(self):return {'profile':'CONNECTION_CHECK','read_only':True}
        self.server.RequestHandlerClass=portal.handler(self.login,self.root,
            upstream=('127.0.0.1',self.backend.server_address[1]),monitor=Monitor())
        self.signin()
        self.assertEqual(self.request('/dashboard')[0],200)
        self.assertTrue(json.loads(self.request('/api/state')[1])['read_only'])
        for action in ('manual_resume','manual_stop','clear','rearm'):
            self.assertEqual(self.request('/api/control',{'action':action})[0],403)
        self.assertEqual(self.actions,[])


class ConnectionTests(unittest.TestCase):
    def test_only_weather_is_real_and_expired_weather_cannot_fill_temperatures(self):
        class Weather:
            valid=True
            def snapshot(self):return {'valid':self.valid,'temp_c':8.5,'source':'REAL_AMBIENT'}
        weather=Weather();monitor=ConnectionStatus(ROOT,provider=weather,clock=lambda:1000)
        s=monitor.snapshot()
        self.assertEqual(s['inputs']['ambient']['temp_c'],8.5)
        self.assertIsNone(s['inputs']['temperature']['temp_c'])
        self.assertFalse(s['thermal_observer']['valid']);self.assertFalse(s['outputs']['actuation_enabled'])
        self.assertTrue(s['read_only']);weather.valid=False
        self.assertIsNone(monitor.snapshot()['inputs']['ambient']['temp_c'])

    def test_staged_location_path_is_absolute_and_accepted_by_real_provider(self):
        config=json.loads((ROOT/'configs/real_navigation_control.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            prepared=project_config(config,Path(temp))
            provider=PhoneAmbientProvider(prepared['ambient_provider'])
            self.assertEqual(provider.location_file,Path(temp).resolve()/'runtime/navigation_location.json')
            self.assertEqual(provider.snapshot()['navigation_location']['status'],'await_location')
            self.assertFalse(provider.snapshot()['valid'])


class LaunchTests(unittest.TestCase):
    def test_real_only_and_manual_hold_required(self):
        config=json.loads((ROOT/'configs/real_navigation_control.json').read_text())
        run_managed.validate(config)
        config['demo']['override_temperature']=True
        with self.assertRaises(ValueError):run_managed.validate(config)
    def test_foreign_filming_controller_detected_before_serial_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'999999';p.mkdir()
            (p/'cmdline').write_bytes(b'/home/pi/SafeGuard_Filming/build/safeguard_main\0--config\0film.json')
            self.assertEqual(run_managed.hardware_owners(Path(temp)),[999999])
    def test_generated_services_do_not_couple_main_to_network_restart(self):
        package=units('/home/pi/SafeGuard_Operational_20261030')
        main=package['safeguard-main.service']
        self.assertIn('RestartPreventExitStatus=78',main)
        self.assertNotIn('network',main);self.assertIn('PartOf=safeguard.target',main);self.assertNotIn('BindsTo=',main)
        self.assertNotIn('PartOf=safeguard-navigation',main)
        self.assertIn('ExecStart=\nExecStart=',package['navigation-override.conf'])
        with self.assertRaises(ValueError):units('/home/pi/a;bad')


if __name__=='__main__':unittest.main()
