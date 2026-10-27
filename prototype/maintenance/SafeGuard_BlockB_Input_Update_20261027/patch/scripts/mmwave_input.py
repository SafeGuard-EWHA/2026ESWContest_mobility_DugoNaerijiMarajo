#!/usr/bin/env python3
"""People Tracking UART -> SafeGuard hub. No actuator commands, no auto-reflash.

Format baseline: B reader at c6e3f60 (Radar Toolbox 4.00).
Frame samples are raw presence evidence. The C++ FSM owns the 5s negative window.
Hardware validation is deliberately separate from packet syntax validation.
"""
import contextlib
import hashlib
import math
from pathlib import Path
import struct
import time

MAGIC = bytes.fromhex('02 01 04 03 06 05 08 07')
HEADER = 40
MAX_PACKET = 65536
KNOWN = set(range(1, 11)) | {1010, 1011, 1012, 1020, 1021}
SERIAL = '01E86213'
PORT_BASE = '/dev/serial/by-id/usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_'


def parse_packet(packet):
    """Reject incomplete/ambiguous records instead of flooring record counts."""
    if len(packet) < HEADER or packet[:8] != MAGIC:
        raise ValueError('bad_header')
    version, size, platform, number, cycles, objects, count, subframe = struct.unpack_from('<8I', packet, 8)
    if size != len(packet) or not HEADER <= size <= MAX_PACKET or count > (size-HEADER)//8:
        raise ValueError('bad_packet_length')
    if platform & 0xffff != 0x6843 or subframe != 0:
        raise ValueError('unexpected_platform_or_subframe')
    offset, seen, tracks, presence = HEADER, set(), None, None
    for _ in range(count):
        if offset + 8 > size:
            raise ValueError('truncated_tlv_header')
        kind, length = struct.unpack_from('<II', packet, offset)
        offset += 8
        if kind == 1040:
            raise ValueError('vital_signs_firmware_not_supported')
        if kind not in KNOWN or kind in seen or offset + length > size:
            raise ValueError('bad_or_duplicate_tlv')
        seen.add(kind)
        payload = packet[offset:offset+length]
        if kind == 1010:
            if length % 112:
                raise ValueError('truncated_track_record')
            tracks, ids = [], set()
            for start in range(0, length, 112):
                record = struct.unpack_from('<I27f', payload, start)
                if record[0] in ids or not all(math.isfinite(v) for v in record[1:]):
                    raise ValueError('bad_track_value')
                ids.add(record[0]); tracks.append(record[:4])
        elif kind == 1021:
            if length != 4:
                raise ValueError('bad_presence_length')
            presence = struct.unpack('<I', payload)[0]
            if presence not in (0, 1):
                raise ValueError('bad_presence_value')
        elif kind == 1020:
            if length < 20 or (length-20) % 8:
                raise ValueError('truncated_compressed_point')
            if not all(math.isfinite(x) and x > 0 for x in struct.unpack_from('<5f', payload)):
                raise ValueError('bad_point_units')
        elif kind == 1:
            if length != objects*16:
                raise ValueError('bad_point_length')
            if not all(math.isfinite(x) for x in struct.unpack('<'+'f'*(length//4), payload)):
                raise ValueError('bad_point_value')
        offset += length
    if size not in (offset, ((offset+31)//32)*32):
        raise ValueError('bad_padding_length')
    return {'frame_number': number, 'tracks': tracks, 'presence': presence,
            'tracks_tlv_present': 1010 in seen, 'presence_tlv_present': 1021 in seen,
            'num_tracks': None if tracks is None else len(tracks), 'version': version}


class Stream:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk):
        self.buffer.extend(chunk)
        events = []
        while True:
            start = self.buffer.find(MAGIC)
            if start < 0:
                self.buffer[:] = self.buffer[-7:]
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < HEADER:
                break
            size = struct.unpack_from('<I', self.buffer, 12)[0]
            if not HEADER <= size <= MAX_PACKET:
                del self.buffer[:8]
                events.append((None, 'bad_packet_length'))
                continue
            if len(self.buffer) < size:
                break
            packet = bytes(self.buffer[:size]); del self.buffer[:size]
            try:
                events.append((parse_packet(packet), None))
            except ValueError as exc:
                events.append((None, str(exc)))
        return events

    def clear(self):
        self.buffer.clear()


class Evidence:
    def __init__(self, timeout_s=2.0, allow_omitted_empty_tracks=False):
        self.timeout = timeout_s
        self.allow_omitted = allow_omitted_empty_tracks
        self.number = None
        self.last_rx = None
        self.frame = None
        self.reason = 'awaiting_first_frame'
        self.evidence = None
        self.restart_required = False
        self.epoch = 0

    def accept(self, frame, now):
        if self.restart_required:
            return
        number = frame['frame_number']
        if self.number is not None:
            delta = (number-self.number) & 0xffffffff
            if delta == 0:
                self.invalidate('duplicate_frame'); return
            if delta >= 0x80000000:
                self.restart_required = True
                self.invalidate('frame_regression_restart_required'); return
        previous = self.evidence
        self.number, self.last_rx, self.frame = number, now, frame
        tracks, presence = frame['num_tracks'], frame['presence']
        if presence == 1 or (tracks is not None and tracks > 0):
            self.evidence, self.reason = True, 'positive_frame'
        elif presence == 0 and (tracks == 0 or (tracks is None and self.allow_omitted)):
            self.evidence, self.reason = False, 'negative_frame_not_empty_verdict'
        else:
            self.evidence, self.reason = None, 'occupancy_fields_incomplete'

        if self.evidence != previous:
            self.epoch += 1

    def invalidate(self, reason):
        self.epoch += 1
        self.evidence, self.reason = None, reason

    def snapshot(self, now):
        fresh = self.last_rx is not None and 0 <= now-self.last_rx < self.timeout
        reason = self.reason if fresh or self.last_rx is None else 'frame_timeout'
        valid = fresh and self.evidence is not None and not self.restart_required
        unknown = reason in ('awaiting_first_frame', 'occupancy_fields_incomplete')
        return dict(valid=valid, evidence=self.evidence if valid else False,
                    health='ok' if valid else 'unknown' if unknown else 'fault',
                    status=reason, continuity_epoch=self.epoch, rx_monotonic_s=self.last_rx if valid else now,
                    frame_number=self.number, **({k: self.frame[k] for k in
                    ('num_tracks','presence','tracks_tlv_present','presence_tlv_present')} if self.frame else {}))


def checked_settings(settings, hardware, fsm):
    if not isinstance(settings, dict) or settings.get('enabled') is not True:
        raise ValueError('radar input is not enabled')
    if settings.get('profile') != 'people_tracking_ods' or settings.get('firmware_confirmed') is not True:
        raise ValueError('People Tracking ODS firmware must be confirmed before opening UART')
    if hardware.get('mmwave_json_port'):
        raise ValueError('choose native radar or JSON serial, not both')
    if settings.get('usb_serial') != SERIAL:
        raise ValueError('unexpected CP2105 identity')
    for key in ('configure_on_start','allow_omitted_empty_tracks','validated'):
        if type(settings.get(key)) is not bool:
            raise ValueError(key+' must be boolean')
    timeout = fsm.get('mmwave_timeout_s', 2.0)
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0.5 <= timeout <= 5:
        raise ValueError('invalid mmWave timeout')
    observe = fsm.get('mmwave_observe_s', 2.0)
    if isinstance(observe,bool) or not isinstance(observe,(int,float)) or not math.isfinite(observe) or not 5 <= observe <= 600:
        raise ValueError('set FSM mmwave_observe_s >= 5; do not duplicate this hold in worker')
    return timeout


def checked_ports(settings):
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    paths = [PORT_BASE+SERIAL+'-if00-port0', PORT_BASE+SERIAL+'-if01-port0']
    for path in paths:
        real = str(Path(path).resolve())
        matches = [p for p in ports if p.device == real and p.vid == 0x10c4 and
                   p.pid == 0xea70 and p.serial_number == SERIAL]
        if not Path(path).exists() or len(matches) != 1:
            raise ValueError('verified CP2105 port missing: '+path)
    return paths


def cfg_lines(settings):
    p = Path(settings.get('cfg_path',''))
    if not p.is_absolute() or not p.is_file():
        raise ValueError('cfg_path must be an existing absolute path')
    data = p.read_bytes()
    if hashlib.sha256(data).hexdigest() != settings.get('cfg_sha256'):
        raise ValueError('cfg hash changed; review configuration first')
    lines = [s.strip() for s in data.decode('utf-8-sig').splitlines()
             if s.strip() and not s.lstrip().startswith('%')]
    verbs = [s.split()[0] for s in lines]
    required = {'trackingCfg','presenceBoundaryBox','antGeometry0','antGeometry1','sensorPosition'}
    if not required.issubset(verbs) or lines[-1:] != ['sensorStart'] or verbs.count('sensorStart') != 1:
        raise ValueError('not the reviewed People Tracking configuration')
    return lines


def send_cfg(port, lines, stop, clock=time.monotonic):
    for line in lines:
        if stop.is_set():
            raise RuntimeError('shutdown_during_cfg')
        port.reset_input_buffer()
        port.write((line+'\n').encode('ascii'))
        deadline, response = clock()+(4 if line == 'sensorStart' else 2), bytearray()
        while clock() < deadline and not stop.is_set():
            response.extend(port.read(min(port.in_waiting or 1,4096)))
            if len(response) > 32768:
                raise RuntimeError('cfg response overflow: '+line)
            text = response.decode('ascii', errors='replace').replace('\r','')
            if any(word in text.lower() for word in ('error','exception','assert','not recognized','ignored')):
                # sensorStop must also be acknowledged; ambiguous response fails closed.
                raise RuntimeError('cfg rejected: '+line+' / '+text[-200:])
            if any(s.strip() == 'Done' for s in text.splitlines()):
                break
        else:
            raise RuntimeError('cfg timeout: '+line)
        if stop.is_set():
            raise RuntimeError('shutdown_during_cfg')


def run(hub, settings):
    """One thread owns UART, continuously reads even when FSM processing is false."""
    from serial import Serial
    fsm, hw = hub.config.get('fsm',{}), hub.hardware
    def publish(sample):
        now = hub.clock()
        enabled = hub.flags()['mmwave']
        validated = settings.get('validated') is True and hw.get('mmwave_validated') is True
        msg = hub.envelope('mmwave','REAL_MMWAVE', sample.pop('rx_monotonic_s',now))
        sample.setdefault('continuity_epoch', 0)
        msg.update(sample, processing=enabled, validated=validated, evidence_kind='presence',
                   method='people_tracking_raw_evidence_fsm_hold', adapter_version=1)
        msg['valid'] = msg['valid'] and enabled and validated
        if not enabled:
            msg.update(valid=False,evidence=False,health='unknown',status='processing_disabled')
        elif not validated:
            msg.update(valid=False,evidence=False,health='unknown',status='profile_not_validated')
        hub.remember('mmwave',now)  # Worker liveness; sample keeps actual RX age.
        hub.emit(msg)
    try:
        timeout = checked_settings(settings,hw,fsm)
        lines = cfg_lines(settings) if settings.get('configure_on_start') else None
        cli_path,data_path = checked_ports(settings)
        with contextlib.ExitStack() as stack:
            cli = stack.enter_context(Serial(cli_path,115200,timeout=.05,write_timeout=1,exclusive=True))
            data = stack.enter_context(Serial(data_path,921600,timeout=.05,write_timeout=1,exclusive=True))
            try:
                if lines is not None:
                    send_cfg(cli,lines,hub.stop)
                data.reset_input_buffer()
                stream = Stream()
                state = Evidence(timeout,settings['allow_omitted_empty_tracks'])
                next_report = 0.0
                timed_out = False
                while not hub.stop.is_set():
                    now = hub.clock()
                    stale = state.last_rx is not None and now-state.last_rx >= timeout
                    if stale and not timed_out:
                        stream.clear()  # Discard partial packets from before an outage.
                        state.invalidate('frame_timeout')
                        publish(state.snapshot(now))
                    timed_out = stale
                    events = stream.feed(data.read(min(data.in_waiting or 1,65536)))
                    for frame,error in events:
                        now = hub.clock()
                        if error:
                            state.invalidate(error)
                            publish(state.snapshot(now))
                        else:
                            previous_number = state.number
                            previous_evidence = state.evidence
                            if previous_number is not None:
                                delta = (frame['frame_number']-previous_number) & 0xffffffff
                                if 1 < delta < 0x80000000:
                                    state.invalidate('frame_gap')
                                    publish(state.snapshot(now))
                            state.accept(frame,now)
                            if (not state.snapshot(now)['valid'] or previous_number is None
                                    or state.evidence != previous_evidence):
                                publish(state.snapshot(now))
                    now = hub.clock()
                    if now >= next_report:
                        publish(state.snapshot(now)); next_report = now+.2
            finally:
                # Only application exit, never FSM transitions. B observed restart may need USB power cycle.
                try: cli.write(b'sensorStop\n')
                except Exception: pass
    except Exception as exc:
        hub.warn('native-radar',str(exc))
        # No auto retry/reconfiguration against a potentially stopped board.
        while not hub.stop.is_set():
            publish(dict(valid=False,evidence=False,health='fault',status='radar_unavailable',detail=str(exc)))
            hub.stop.wait(.2)
