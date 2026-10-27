"""Synthetic location and weather fixtures; no live API or physical phone."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import types

PACKAGE = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get('SAFEGUARD_TEST_PROJECT', PACKAGE.parent / 'SafeGuard_Main'))
AMBIENT = PROJECT / 'scripts/ambient_weather.py'
if not AMBIENT.exists():
    AMBIENT = PACKAGE.parent / 'SafeGuard_Ambient_Update/patch/scripts/ambient_weather.py'
sys.path.insert(0, str(AMBIENT.parent))
sys.path.insert(0, str(PACKAGE / 'patch/scripts'))
import navigation_ambient as nav

class Reply:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return json.dumps(self.payload).encode()[:size]
    def geturl(self): return 'https://api.open-meteo.com/v1/forecast'

class NavigationWeatherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'location.json'
        self.mono, self.wall, self.seq = 100., 1792764000., 0
        self.failure = None; self.requests = []
        self.payload = {'utc_offset_seconds':0,
            'current_units': {'time':'unixtime','temperature_2m':'°C','interval':'seconds'},
            'current':{'time':int(self.wall)-120, 'temperature_2m':19.5,'interval':900}}
        self.config = {'enabled':True, 'location_mode':'phone','location_file':str(self.path)}
        self.provider = nav.PhoneAmbientProvider(self.config, clock=lambda:self.mono,
            wall_clock=lambda:self.wall, opener=self.opener)
    def opener(self, request, timeout):
        self.requests.append(request.full_url)
        if self.failure: raise self.failure
        return Reply(self.payload)
    def advance(self, seconds): self.mono += seconds; self.wall += seconds
    def location(self, lat=37.5, lon=127., **updates):
        self.seq += 1
        row = {'schema_version':1,'source':'IPHONE_NAVIGATION','receiver_session':'a'*32,
            'seq':self.seq,'valid':True,'latitude':lat,'longitude':lon,'accuracy_m':10.,
            'position_timestamp_ms':self.wall*1000,'received_wall_s':self.wall,
            'rx_monotonic_s':self.mono,'source_age_at_receive_s':0.}
        row.update(updates); self.path.write_text(json.dumps(row)); return row
    def test_no_location_never_uses_static_fallback_or_network(self):
        self.provider = nav.PhoneAmbientProvider(dict(self.config,latitude=37.,longitude=127.),
            clock=lambda:self.mono,wall_clock=lambda:self.wall,opener=self.opener)
        self.assertFalse(self.provider.refresh()); self.assertEqual(self.requests,[])
        self.assertIsNone(self.provider.snapshot()['temp_c'])
    def test_query_coordinates_and_metadata(self):
        self.location(); self.assertTrue(self.provider.refresh()); row=self.provider.snapshot()
        self.assertTrue(row['valid']); self.assertEqual(row['temp_c'],19.5)
        self.assertEqual(row['navigation_location']['age_s'],0)
        self.assertEqual((row['latitude'],row['longitude']),(37.5,127.))
        self.assertEqual(row['data_kind'],'model_estimate'); self.assertFalse(row['onsite_measurement'])
        self.assertIn('latitude=37.5',self.requests[0])
    def test_source_age_expires_without_renewing_on_snapshot(self):
        self.location(); self.provider.refresh(); self.advance(15)
        row=self.provider.snapshot(); self.assertFalse(row['valid']); self.assertIsNone(row['temp_c'])
        self.assertEqual(row['status'],'location_stale')
    def test_stop_invalidates_weather_immediately(self):
        self.location(); self.provider.refresh(); self.location(valid=False,status='phone_stopped')
        self.assertFalse(self.provider.snapshot()['valid']); self.assertFalse(self.provider.refresh())
        self.assertEqual(len(self.requests),1)
    def test_movement_rate_limit_and_query_provenance(self):
        self.location(); self.provider.refresh(); self.advance(10); self.location(lat=37.51)
        self.assertFalse(self.provider.refresh()); row=self.provider.snapshot()
        self.assertEqual(row['latitude'],37.5); self.assertEqual(row['navigation_location']['latitude'],37.51)
        self.assertFalse(row['valid']); self.advance(50); self.location(lat=37.51)
        self.assertTrue(self.provider.refresh()); self.assertEqual(len(self.requests),2)
        self.assertEqual(self.provider.snapshot()['latitude'],37.51)
    def test_small_movement_keeps_weather_query_location_until_refresh(self):
        self.location(); self.provider.refresh(); self.advance(60); self.location(lat=37.5001)
        self.assertFalse(self.provider.refresh()); row=self.provider.snapshot()
        self.assertTrue(row['valid']); self.assertEqual(row['latitude'],37.5)
        self.assertNotEqual(row['latitude'],row['navigation_location']['latitude'])
        self.advance(240); self.location(lat=37.5001); self.assertTrue(self.provider.refresh())
    def test_failed_refresh_only_keeps_nearby_unexpired_cache(self):
        self.location(); self.provider.refresh(); self.advance(60); self.location(lat=37.502)
        self.failure=TimeoutError('fixture'); self.assertFalse(self.provider.refresh())
        row=self.provider.snapshot(); self.assertTrue(row['valid']); self.assertEqual(row['status'],'cached_after_error')
        self.location(lat=38.); self.assertFalse(self.provider.snapshot()['valid'])
    def test_weather_expiry_even_with_new_phone_locations(self):
        self.location(); self.provider.refresh(); self.advance(1680); self.location()
        self.assertFalse(self.provider.snapshot()['valid']); self.assertEqual(self.provider.snapshot()['status'],'sample_expired')
    def test_moving_queries_do_not_renew_old_weather_after_clock_rollback(self):
        self.location(); self.provider.refresh(); self.mono += 1700; self.wall += 60; self.location(lat=37.502)
        self.assertFalse(self.provider.refresh()); self.assertFalse(self.provider.snapshot()['valid'])
        self.assertGreaterEqual(self.provider.snapshot()['sample_age_s'],1800)
    def test_future_inaccurate_regressed_and_invalid_location_rejected(self):
        cases=[{'accuracy_m':201},{'latitude':True},{'longitude':181},
               {'position_timestamp_ms':(self.wall+6)*1000}, {'rx_monotonic_s':self.mono+1},
               {'source_age_at_receive_s':5},{'source':'DEMO'},{'receiver_session':'bad'}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.location(**changes); self.assertFalse(self.provider.refresh())
                self.assertFalse(self.provider.snapshot()['valid'])
        self.assertEqual(self.requests,[])
    def test_corrupt_or_oversize_state_is_invalid(self):
        for text in ('{"valid":true,"valid":false}', 'null', 'x'*17000):
            self.path.write_text(text); self.assertFalse(self.provider.snapshot()['valid'])
    def test_new_location_during_http_does_not_relabel_reply(self):
        self.location()
        def opener(request, timeout): self.location(lat=38.); return Reply(self.payload)
        self.provider.opener=opener; self.assertFalse(self.provider.refresh())
        row=self.provider.snapshot(); self.assertEqual(row['latitude'],37.5)
        self.assertEqual(row['navigation_location']['latitude'],38.); self.assertFalse(row['valid'])
    def test_configuration_limits_and_disabled_mode(self):
        for cfg in ({'location_timeout_s':20},{'min_request_interval_s':5},
                    {'max_weather_distance_m':50},{'enabled':1},{'location_file':'relative.json'}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError): nav.PhoneAmbientProvider(dict(self.config,**cfg))
        off=nav.PhoneAmbientProvider(dict(self.config,enabled=False),opener=self.opener)
        self.assertFalse(off.refresh()); self.assertFalse(off.snapshot()['valid']); self.assertEqual(self.requests,[])
    def test_hub_publishes_weather_then_invalidates_after_phone_stop(self):
        spec=importlib.util.spec_from_file_location('navigation_hub_test',PACKAGE/'patch/scripts/sensor_hub.py')
        hubmod=importlib.util.module_from_spec(spec); spec.loader.exec_module(hubmod)
        output=[]
        config={'mode':'REAL','profile':'REAL','hardware':{},'dashboard':{'enabled':False},
                'actuation':{'enabled':False},'ambient_provider':self.config}
        with mock.patch.object(hubmod,'load_uwb_module',return_value=types.SimpleNamespace(DistanceState=lambda *a:None)), mock.patch.object(hubmod,'load_navigation_ambient_module',return_value=types.SimpleNamespace(PhoneAmbientProvider=lambda *a,**k:self.provider)):
            hub=hubmod.SensorHub(config,Path(self.temp.name)/'current_state.json',clock=lambda:self.mono,output=output.append)
        self.location(); self.provider.refresh(); hub.real_watchdog_tick(self.mono)
        row=next(x for x in output if x['type']=='ambient')
        self.assertTrue(row['valid']); self.assertEqual(row['source'],'REAL_AMBIENT')
        self.assertEqual(row['navigation_location']['latitude'],37.5)
        output.clear(); self.location(valid=False); hub.real_watchdog_tick(self.mono)
        self.assertFalse(next(x for x in output if x['type']=='ambient')['valid'])
        self.assertFalse(json.loads((Path(self.temp.name)/'ambient_status.json').read_text())['valid'])

if __name__=='__main__': unittest.main()
