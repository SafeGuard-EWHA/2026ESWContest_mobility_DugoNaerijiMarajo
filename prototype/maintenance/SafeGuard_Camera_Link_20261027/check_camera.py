"""30-second camera-only check through installed sensor_hub.camera_worker.
Does not start main, ESP32, radar, UWB, weather or actuator control.
"""
import argparse
import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import uuid
from install_camera import ensure_idle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, default=Path.home()/'SafeGuard_Main')
    p.add_argument('--duration', type=int, default=30)
    a = p.parse_args()
    if not 10 <= a.duration <= 120: p.error('duration must be 10..120 seconds')
    project = a.project.resolve()
    ensure_idle()
    with (project/'runtime/software_control.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        ensure_idle()
        settings = json.loads((project/'configs/real_navigation_control.json').read_text())
        if settings['hardware'].get('camera_backend') != 'block_b_motion':
            raise ValueError('Install camera link first')
        sys.path.insert(0, str(project/'scripts'))
        from sensor_hub import SensorHub
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
        out = project/'camera_checks'/stamp
        out.mkdir(parents=True)
        counts = dict(frames=0, valid_frames=0, motion_frames=0, lighting_frames=0, errors=0)
        prev, reported = None, -1e30
        config = dict(mode='REAL', profile='REAL', hardware=dict(settings['hardware'], uwb_enabled=False),
                      actuation={'enabled':False}, dashboard={'enabled':False}, ambient_provider={'enabled':False})
        with (out/'camera.jsonl').open('w') as log:
            def output(msg):
                nonlocal prev, reported
                log.write(json.dumps(msg, ensure_ascii=False)+'\n'); log.flush()
                if msg.get('type') != 'camera': return
                counts['frames'] += 1
                counts['valid_frames'] += bool(msg.get('valid'))
                counts['motion_frames'] += bool(msg.get('valid') and msg.get('motion'))
                counts['lighting_frames'] += msg.get('kind') in ('light','settle')
                counts['errors'] += msg.get('status') == 'camera_unavailable'
                state = (msg.get('valid'), msg.get('motion'), msg.get('status'))
                if state != prev or time.monotonic()-reported >= 2:
                    print('CAMERA valid=%s motion=%s kind=%s status=%s' %
                          (msg.get('valid'), msg.get('motion'), msg.get('kind'), msg.get('status')), flush=True)
                    if msg.get('error'): print('ERROR:', msg['error'], flush=True)
                    prev, reported = state, time.monotonic()
            hub = SensorHub(config, out/'state.json', output=output)
            hub.processing['camera'] = True
            timer = threading.Timer(a.duration, hub.stop.set)
            timer.daemon = True; timer.start()
            print('Camera only. Leave scene still 5s, move your hand/body in view, then stay still.', flush=True)
            print('LOG:', out, flush=True)
            try: hub.camera_worker()
            except KeyboardInterrupt: hub.stop.set()
            finally: timer.cancel(); hub.stop.set()
        counts['camera_input_received'] = counts['valid_frames'] > 0 and counts['errors'] == 0
        counts['physical_outputs_tested'] = False
        (out/'result.json').write_text(json.dumps(counts, indent=2)+'\n')
        print(json.dumps(counts, indent=2), flush=True)
        return 0 if counts['camera_input_received'] else 2


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError, ImportError) as exc: raise SystemExit(str(exc))
