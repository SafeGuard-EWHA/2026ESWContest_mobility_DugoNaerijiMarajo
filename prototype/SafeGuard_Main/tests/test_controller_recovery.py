#!/usr/bin/env python3
"""Linux PTY protocol test: actual main+hub, simulated ESP32; NOT hardware evidence."""
import argparse
import errno
import json
import os
from pathlib import Path
import pty
import select
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class Board:
    """Small protocol peer; models retained outputs and session heartbeat handover."""
    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.port = os.ttyname(self.slave)
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.boot = 'mock-boot-1'
        self.started = time.monotonic()
        self.owner = 'previous-main'
        self.lock_until = self.started + 3.0
        self.fan = self.buzzer = True
        self.latched = False
        self.pause_until = 0.0
        self.seq = 0
        self.commands = []
        self.errors = []
        self.thread = threading.Thread(target=self.run, daemon=True)

    def write(self, msg):
        os.write(self.master, (json.dumps(msg) + '\n').encode())

    def receive(self, msg):
        kind, run = msg.get('type'), msg.get('run_id')
        now = time.monotonic()
        if kind == 'heartbeat':
            if now >= self.lock_until:
                self.owner = run
            return
        if kind not in ('command', 'rearm'):
            return
        accepted = run == self.owner
        if kind == 'rearm':
            accepted = accepted and self.latched
            if accepted:
                self.latched = False
                self.fan = self.buzzer = False
        else:
            accepted = accepted and not (self.latched and (msg.get('fan') or msg.get('buzzer')))
            if accepted:
                self.fan, self.buzzer = msg['fan'], msg['buzzer']
        self.commands.append(dict(msg, accepted=accepted, at=now))
        self.write({'type': 'ack', 'boot_id': self.boot, 'run_id': run,
                    'id': msg['id'], 'accepted': accepted, 'fan_cmd': self.fan,
                    'buzzer_cmd': self.buzzer, 'reason': 'ok' if accepted else 'rejected'})

    def telemetry(self):
        self.seq += 1
        return {'type': 'telemetry', 'boot_id': self.boot, 'seq': self.seq,
                'uptime_ms': int((time.monotonic() - self.started) * 1000),
                'pir': False, 'pir_valid': True, 'temp_c': 25.0, 'temp_valid': True,
                'humidity': 50.0, 'humidity_valid': True, 'estop': False,
                'estop_valid': True, 'estop_latched': self.latched,
                'fan_cmd': self.fan, 'buzzer_cmd': self.buzzer,
                'actuators_enabled': True, 'active_run': self.owner,
                'heartbeat_fault': False}

    def reboot(self):
        with self.lock:
            self.boot = 'mock-boot-2'
            self.started = time.monotonic()
            self.seq = 0
            self.owner = ''
            self.lock_until = 0.0
            self.fan = self.buzzer = False
            return time.monotonic()

    def run(self):
        pending = b''
        sent = 0.0
        try:
            while not self.stop.is_set():
                ready, _, _ = select.select([self.master], [], [], 0.02)
                if ready:
                    try:
                        pending += os.read(self.master, 8192)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        try:
                            msg = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        with self.lock:
                            self.receive(msg)
                now = time.monotonic()
                if now - sent >= 0.1 and now >= self.pause_until:
                    with self.lock:
                        self.write(self.telemetry())
                    sent = now
        except Exception as exc:
            self.errors.append(repr(exc))

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        os.close(self.master)
        os.close(self.slave)


def wait_for(predicate, label, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError('timed out: ' + label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/safeguard_main')
    args = parser.parse_args()
    # Require the same pyserial package used by the real hub.
    import serial  # noqa: F401
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    url = 'http://127.0.0.1:%d' % port
    board = Board()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='safeguard-controller-test-') as temp:
            config = json.loads((ROOT / 'configs/real.json').read_text())
            config['scenario'] = 'SOFTWARE_PTY_MOCK_NOT_HARDWARE'
            config['hardware']['esp32_port'] = board.port
            config['hardware']['uwb_port'] = '/dev/safeguard-test-no-uwb'
            config['actuation']['enabled'] = True
            config['dashboard']['port'] = port
            config_path = Path(temp) / 'config.json'
            config_path.write_text(json.dumps(config))
            log_path = Path(temp) / 'main.txt'
            with log_path.open('w+') as log:
                board.thread.start()
                process = subprocess.Popen([str(args.binary.resolve()), '--config', str(config_path)],
                                           cwd=ROOT, stdout=log, stderr=log)

                def state():
                    try:
                        with urllib.request.urlopen(url + '/api/state', timeout=0.5) as response:
                            data = json.load(response)
                        return data if 'state' in data else {}
                    except (OSError, ValueError):
                        return {}

                def acknowledged():
                    data = state()
                    return data if (data.get('state') == 'PROTECTION' and
                                    data.get('outputs', {}).get('ack_status') ==
                                    'ACK_RECEIVED_NOT_PHYSICAL_FEEDBACK') else None

                def control(action):
                    req = urllib.request.Request(url + '/api/control',
                        data=json.dumps({'action': action}).encode(),
                        headers={'Content-Type': 'application/json'}, method='POST')
                    with urllib.request.urlopen(req, timeout=2) as response:
                        assert response.status == 202

                try:
                    first = wait_for(acknowledged, 'retained ON + controller handover', 12)
                    assert first['occupant'] == 'UNKNOWN', 'recovery must not invent occupant evidence'
                    with board.lock:
                        sent = [x for x in board.commands if x['type'] == 'command']
                        assert sent and all(x['fan'] and x['buzzer'] for x in sent), sent
                    rebooted_at = board.reboot()
                    wait_for(lambda: any(x['type'] == 'command' and x['at'] > rebooted_at and
                                         x['fan'] and x['buzzer'] and x['accepted']
                                         for x in board.commands), 'reassert ON after MCU reboot')
                    wait_for(acknowledged, 'ACK after MCU reboot')

                    with board.lock:
                        board.pause_until = time.monotonic() + 3.2
                    wait_for(lambda: state().get('outputs', {}).get('ack_status') not in
                             (None, 'ACK_RECEIVED_NOT_PHYSICAL_FEEDBACK'), 'stale telemetry invalidates ACK', 3)
                    wait_for(acknowledged, 'fresh controller telemetry re-synchronizes', 6)

                    # Raw switch is already released: only the MCU latch records the pulse.
                    with board.lock:
                        board.latched = True
                        board.fan = board.buzzer = False
                    wait_for(lambda: state().get('state') == 'ESTOP', 'short ESTOP pulse latch')
                    time.sleep(0.4)
                    assert state().get('state') == 'ESTOP', 'release alone must not rearm'
                    control('rearm')
                    wait_for(lambda: state().get('state') in ('INIT', 'FAULT', 'STANDBY'),
                             'manual rearm ACK releases software latch')
                    time.sleep(0.5)
                    assert state().get('state') != 'ESTOP', 'old telemetry must not restore cleared latch'
                    assert not board.errors, board.errors
                    print('PASS: SOFTWARE PTY controller handover / reboot / loss / latched ESTOP / rearm')
                except Exception:
                    log.flush()
                    print(log_path.read_text()[-16000:])
                    raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        board.close()


if __name__ == '__main__':
    main()
