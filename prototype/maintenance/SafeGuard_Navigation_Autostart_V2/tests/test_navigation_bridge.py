import http.client
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import tempfile
import threading
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'patch/scripts/navigation_bridge.py'
spec = importlib.util.spec_from_file_location('navigation_bridge_tested', MODULE)
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)


class FakeClock:
    def __init__(self): self.wall, self.mono = 1760000000.0, 1000.0
    def advance(self, seconds): self.wall += seconds; self.mono += seconds


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.path = Path(self.temp.name) / 'location.json'
        self.store = nav.LocationStore(self.path, clock=lambda:self.clock.mono,
            wall_clock=lambda:self.clock.wall, pairing_code='12345678')

    def tearDown(self): self.temp.cleanup()

    def sample(self, **updates):
        result = {'seq':1,'valid':True,'latitude':37.5664,'longitude':126.9462,
                  'accuracy_m':12,'position_timestamp_ms':self.clock.wall*1000}
        result.update(updates)
        return result

    def test_pair_auth_one_use_and_invalid_on_start(self):
        self.assertFalse(json.loads(self.path.read_text())['valid'])
        result = self.store.pair({'code':'12345678'})
        self.assertTrue(self.store.authorized('Bearer '+result['token']))
        self.assertFalse(self.store.authorized('Bearer wrong'))
        with self.assertRaises(nav.BridgeError): self.store.pair({'code':'12345678'})
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_pairing_attempts_and_expiry(self):
        for _ in range(10):
            with self.assertRaises(nav.BridgeError): self.store.pair({'code':'00000000'})
        with self.assertRaises(nav.BridgeError) as ctx: self.store.pair({'code':'12345678'})
        self.assertEqual(ctx.exception.status,429)
        self.store.pair_attempts=0
        self.clock.advance(600)
        with self.assertRaises(nav.BridgeError): self.store.pair({'code':'12345678'})

    def test_valid_replay_regression_and_expiry(self):
        value=self.store.accept(self.sample())
        self.assertTrue(value['valid'])
        self.assertEqual(value['source'],'IPHONE_NAVIGATION')
        with self.assertRaises(nav.BridgeError): self.store.accept(self.sample())
        with self.assertRaises(nav.BridgeError): self.store.accept(self.sample(seq=2,position_timestamp_ms=self.clock.wall*1000-1))
        self.clock.advance(15)
        self.assertFalse(self.store.status()['location']['valid'])

    def test_explicit_stop_invalidates_and_sequence_advances(self):
        self.store.accept(self.sample())
        result=self.store.accept({'valid':False,'seq':2})
        self.assertFalse(result['valid'])
        self.assertIsNone(result['latitude'])
        self.assertEqual(json.loads(self.path.read_text())['seq'],2)

    def test_bad_location_does_not_renew_good_sample(self):
        old=self.store.accept(self.sample())
        self.clock.advance(2)
        for patch in ({'accuracy_m':201},{'latitude':float('nan')},{'longitude':181},
                      {'valid':1},{'position_timestamp_ms':self.clock.wall*1000-16000},
                      {'position_timestamp_ms':self.clock.wall*1000+6000},
                      {'latitude':10**3000}):
            with self.assertRaises(nav.BridgeError): self.store.accept(self.sample(seq=2,**patch))
        self.assertEqual(json.loads(self.path.read_text()),old)

    def test_repeat_timestamp_cannot_extend_age_after_clock_rollback(self):
        stamp=self.clock.wall*1000
        self.store.accept(self.sample())
        self.clock.advance(14)
        self.clock.wall-=10
        self.store.accept(self.sample(seq=2,position_timestamp_ms=stamp))
        self.clock.advance(2)
        self.clock.wall-=2
        with self.assertRaises(nav.BridgeError): self.store.accept(self.sample(seq=3,position_timestamp_ms=stamp))
        self.assertFalse(self.store.status()['location']['valid'])

    def test_receiver_close_prevents_late_request_overwriting_invalid_state(self):
        self.store.accept(self.sample())
        self.store.close()
        with self.assertRaises(nav.BridgeError): self.store.accept(self.sample(seq=2))
        self.assertFalse(json.loads(self.path.read_text())['valid'])
        self.assertEqual(json.loads(self.path.read_text())['status'],'receiver_stopped')

    def test_strict_json_rejects_duplicate_nonfinite_nonobject(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'[]'):
            with self.assertRaises(ValueError): nav.strict_json(raw)

    def test_profile_contains_only_matching_certificate(self):
        path=Path(self.temp.name)/'cert.mobileconfig'
        profile={'PayloadType':'Configuration','PayloadContent':[{'PayloadType':'com.apple.security.root','PayloadContent':b'cert'}]}
        path.write_bytes(plistlib.dumps(profile))
        self.assertEqual(nav.load_profile(path,b'cert'),path.read_bytes())
        with self.assertRaises(ValueError): nav.load_profile(path,b'wrong')
        profile['PayloadContent'].append({'PayloadType':'com.apple.vpn.managed'})
        path.write_bytes(plistlib.dumps(profile))
        with self.assertRaises(ValueError): nav.load_profile(path,b'cert')

    def test_http_handler_host_origin_auth_payload_and_bootstrap_scope(self):
        server=nav.BridgeServer(('127.0.0.1',0),nav.BaseHTTPRequestHandler)
        port=server.server_port
        server.RequestHandlerClass=nav.make_handler(self.store,host='127.0.0.1',port=port,
            ca_der=b'cert',mobile_html=b'<html>phone</html>')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        host=f'127.0.0.1:{port}'; origin='https://'+host
        def request(path,body=None,**changes):
            headers={'Host':host,'Origin':origin}
            if body is not None:headers['Content-Type']='application/json'
            headers.update(changes)
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            connection.request('GET' if body is None else 'POST',path,body=body,headers=headers)
            response=connection.getresponse();status=response.status;data=response.read();connection.close()
            return status,data
        try:
            self.assertEqual(request('/')[0],200)
            self.assertEqual(request('/',Host='wrong')[0],403)
            self.assertEqual(request('/api/status')[0],401)
            self.assertEqual(request('/api/pair',b'{"code":"12345678"}',Origin='http://evil')[0],403)
            code,data=request('/api/pair',b'{"code":"12345678"}')
            self.assertEqual(code,200);auth='Bearer '+json.loads(data)['token']
            self.assertEqual(request('/api/location',b'{"valid":true,"valid":false}',Authorization=auth)[0],400)
            self.assertEqual(request('/api/location',b' '*4097,Authorization=auth)[0],413)
            code,data=request('/api/location',json.dumps(self.sample()).encode(),Authorization=auth)
            self.assertEqual(code,200);self.assertTrue(json.loads(data)['valid'])
            self.assertEqual(request('/api/status',Authorization=auth)[0],200)
            self.assertEqual(request('/server.key')[0],404)
            server.RequestHandlerClass=nav.make_handler(self.store,host='127.0.0.1',port=port,
                ca_der=b'cert',mobile_html=b'phone',bootstrap=True,profile_bytes=b'profile')
            self.assertEqual(request('/safeguard-root.cer'),(200,b'cert'))
            self.assertEqual(request('/SafeGuard_Navigation.mobileconfig'),(200,b'profile'))
            self.assertEqual(request('/api/location',b'{}')[0],405)
            self.assertEqual(request('/../server.key')[0],404)
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
