"""Software checks only; actual Pi camera/lighting requires check_camera.py."""
import pathlib
import sys
import types
import unittest
from unittest import mock
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/('patch/scripts' if (ROOT/'patch').exists() else 'scripts')))
from block_b_camera_adapter import Detector, checked_settings, run


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.s = checked_settings({})
        self.d = Detector(self.s)
        self.blank = np.zeros((240,320), dtype=np.uint8)
        self.changed = self.blank.copy(); self.changed[:20,:160] = 100

    def test_requires_baseline_and_three_frames(self):
        self.assertFalse(self.d.feed(self.blank, 0)['valid'])
        self.assertFalse(self.d.feed(self.changed, .1)['motion'])
        self.assertFalse(self.d.feed(self.blank, .2)['motion'])
        self.assertTrue(self.d.feed(self.changed, .3)['motion'])

    def test_still_is_valid_motion_negative_only(self):
        self.d.feed(self.blank,0)
        row = self.d.feed(self.blank,.1)
        self.assertTrue(row['valid']); self.assertFalse(row['motion'])
        self.assertEqual(row['status'],'motion_only_not_presence')

    def test_lighting_and_settle_are_unknown_without_positive_hold(self):
        self.d.feed(self.blank,0)
        lit = np.full_like(self.blank,200)
        row = self.d.feed(lit,.1)
        self.assertEqual(row['kind'],'light'); self.assertFalse(row['valid'])
        row = self.d.feed(lit,.2)
        self.assertEqual(row['kind'],'settle'); self.assertFalse(row['valid'])
        for i in range(3,13): row = self.d.feed(lit,i/10)
        self.assertTrue(row['valid']); self.assertFalse(row['motion'])

    def test_gap_resets_positive_hold_and_streak(self):
        for t,f in [(0,self.blank),(.1,self.changed),(.2,self.blank),(.3,self.changed)]:
            self.d.feed(f,t)
        row = self.d.feed(self.blank,1.5)
        self.assertFalse(row['valid']); self.assertFalse(row['motion'])
        self.assertEqual(row['status'],'frame_gap_reset')
        self.assertFalse(self.d.feed(self.changed,1.6)['motion'])

    def test_disable_reset_drops_old_positive(self):
        for t,f in [(0,self.blank),(.1,self.changed),(.2,self.blank),(.3,self.changed)]:
            self.d.feed(f,t)
        self.d.reset()
        self.assertFalse(self.d.feed(self.blank,.4)['valid'])
        self.assertFalse(self.d.feed(self.changed,.5)['motion'])

    def test_signed_difference_and_roi(self):
        from block_b_camera_motion import motion_ratio
        high = np.full_like(self.blank,255)
        self.assertEqual(motion_ratio(high,self.blank,25),1.0)
        self.assertEqual(motion_ratio(self.blank,self.changed,25,[.6,0,1,1]),0.0)

    def test_invalid_settings_and_frames_rejected(self):
        for settings in ({'fps':float('nan')},{'min_frames':True},{'roi':[0,0,.0001,.0001]},
                         {'ratio_thresh':.7},{'fps':0},{'extra':1}):
            with self.assertRaises(ValueError): checked_settings({'camera_motion':settings})
        with self.assertRaises(ValueError): self.d.feed(np.zeros((10,10),dtype=np.uint8),0)


class FakeStop:
    def __init__(self): self.stopped=False
    def is_set(self): return self.stopped
    def wait(self,seconds): return self.stopped
    def set(self): self.stopped=True


class WorkerTests(unittest.TestCase):
    def test_worker_protocol_and_cleanup(self):
        class Camera:
            stopped=closed=False
            def __init__(self): self.i=0
            def create_video_configuration(self,**kw): return kw
            def configure(self,c): self.config=c
            def start(self): pass
            def capture_array(self,name):
                self.i+=1
                frame=np.zeros((360,320),dtype=np.uint8)
                if self.i%2 == 0: frame[:20,:160]=100
                return frame
            def stop(self): self.stopped=True
            def close(self): self.closed=True
        c=Camera()
        class Hub:
            hardware={}
            stop=FakeStop()
            rows=[]
            def flags(self): return {'camera':True}
            def clock(self): return c.i/10
            def remember(self,*args): pass
            def envelope(self,k,s,now=None): return dict(type=k,source=s,rx_monotonic_s=now,seq=len(self.rows)+1,run_id='test',schema_version=1)
            def emit(self,row):
                self.rows.append(row)
                if len(self.rows)>=4:self.stop.set()
            def warn(self,*args): pass
        hub=Hub()
        with mock.patch.dict(sys.modules,{'picamera2':types.SimpleNamespace(Picamera2=lambda:c)}): run(hub)
        self.assertEqual(len(hub.rows),4)
        self.assertTrue(hub.rows[-1]['valid'] and hub.rows[-1]['motion'])
        self.assertTrue(all(r['source']=='REAL_CAMERA' and r['processing'] for r in hub.rows))
        self.assertTrue(c.stopped and c.closed)
        self.assertEqual(c.config['controls']['FrameRate'],10)

    def test_camera_open_error_is_invalid_not_empty(self):
        rows=[]
        hub=types.SimpleNamespace(hardware={}, stop=FakeStop(), flags=lambda:{'camera':True},
             warn=lambda *a:None, envelope=lambda *a:dict(type='camera',source='REAL_CAMERA'),emit=rows.append)
        with mock.patch.dict(sys.modules,{'picamera2':types.SimpleNamespace(Picamera2=mock.Mock(side_effect=RuntimeError('busy')))}): run(hub)
        self.assertFalse(rows[-1]['valid']);self.assertFalse(rows[-1]['motion'])
        self.assertEqual(rows[-1]['error'],'busy')


if __name__=='__main__': unittest.main()
