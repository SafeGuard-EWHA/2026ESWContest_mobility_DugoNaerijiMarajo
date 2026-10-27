"""B's unchanged motion detector -> existing SafeGuard REAL_CAMERA protocol.

Motion evidence only: false is not an empty-seat verdict. No actuator access.
"""
import math
from block_b_camera_motion import MotionState, motion_ratio

DEFAULTS = dict(fps=10.0, pixel_thresh=25, ratio_thresh=0.01,
                light_thresh=0.6, min_frames=3, hold_s=2.0,
                light_settle_s=1.0, roi=[0.0, 0.0, 1.0, 1.0])


def checked_settings(hardware):
    supplied = hardware.get('camera_motion', {})
    if not isinstance(supplied, dict) or set(supplied) - set(DEFAULTS):
        raise ValueError('invalid camera_motion settings')
    s = dict(DEFAULTS, **supplied)
    for key in ('fps', 'ratio_thresh', 'light_thresh', 'hold_s', 'light_settle_s'):
        x = s[key]
        if type(x) not in (int, float) or not math.isfinite(x):
            raise ValueError('invalid camera setting: ' + key)
    if not (1 <= s['fps'] <= 30 and 0 < s['ratio_thresh'] < s['light_thresh'] <= 1
            and 0 <= s['hold_s'] <= 5 and 0 <= s['light_settle_s'] <= 5
            and type(s['pixel_thresh']) is int and 0 <= s['pixel_thresh'] <= 255
            and type(s['min_frames']) is int and 1 <= s['min_frames'] <= 30):
        raise ValueError('camera settings out of range')
    roi = s['roi']
    if not (isinstance(roi, list) and len(roi) == 4
            and all(type(x) in (int, float) and math.isfinite(x) for x in roi)
            and 0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1
            and int(roi[2]*320) > int(roi[0]*320)
            and int(roi[3]*240) > int(roi[1]*240)):
        raise ValueError('invalid/empty camera ROI')
    return s


class Detector:
    def __init__(self, settings):
        self.s = settings
        self.reset()

    def reset(self):
        s = self.s
        self.state = MotionState(s['ratio_thresh'], s['light_thresh'], s['hold_s'],
                                 s['min_frames'], s['light_settle_s'])
        self.previous = None
        self.last_time = None

    def feed(self, frame, now):
        import numpy as np
        if frame.shape != (240, 320) or frame.dtype != np.uint8:
            raise ValueError('unexpected camera Y frame')
        gap = self.last_time is not None and not 0 < now-self.last_time <= max(0.5, 3/self.s['fps'])
        if gap:
            self.reset()
        self.last_time = now
        if self.previous is None:
            self.previous = frame.copy()
            return dict(valid=False, motion=False, ratio=None, kind='baseline',
                        status='frame_gap_reset' if gap else 'warming_up')
        ratio = motion_ratio(self.previous, frame, self.s['pixel_thresh'], self.s['roi'])
        self.previous = frame.copy()
        active, kind = self.state.update(ratio, now)
        # Preserve an already observed short positive hold, but ambiguous lighting
        # without such evidence must not be turned into a valid negative.
        valid = active or kind not in ('light', 'settle')
        return dict(valid=bool(valid), motion=bool(active), ratio=ratio, kind=kind,
                    status='motion_only_not_presence' if valid else 'lighting_uncertain')


def run(hub):
    camera = None
    try:
        settings = checked_settings(hub.hardware)
        from picamera2 import Picamera2
        camera = Picamera2()
        camera.configure(camera.create_video_configuration(
            main={'size': (1280, 720)},
            lores={'size': (320, 240), 'format': 'YUV420'},
            controls={'FrameRate': settings['fps']}))
        camera.start()
        if hub.stop.wait(2.0):
            return
        detector = Detector(settings)
        while not hub.stop.is_set():
            if not hub.flags()['camera']:
                detector.reset()
                hub.stop.wait(0.1)
                continue
            yuv = camera.capture_array('lores')
            now = hub.clock()
            if hub.stop.is_set():
                break
            if not hub.flags()['camera']:
                detector.reset()
                continue
            sample = detector.feed(yuv[:240, :320], now)
            msg = hub.envelope('camera', 'REAL_CAMERA', now)
            msg.update(sample, processing=True, method='block_b_yuv_motion_v1')
            hub.remember('camera', now)
            hub.emit(msg)
    except Exception as exc:
        hub.warn('camera', 'B camera unavailable: ' + str(exc))
        msg = hub.envelope('camera', 'REAL_CAMERA')
        msg.update(valid=False, motion=False, processing=hub.flags()['camera'],
                   method='block_b_yuv_motion_v1', status='camera_unavailable', error=str(exc))
        hub.emit(msg)
    finally:
        if camera is not None:
            for action in ('stop', 'close'):
                try:
                    getattr(camera, action)()
                except Exception:
                    pass
