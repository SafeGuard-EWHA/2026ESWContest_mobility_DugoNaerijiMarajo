#!/usr/bin/env python3
"""SafeGuard sensor transport. stdout is JSONL; diagnostics go to stderr.

This process does not decide whether an occupant is present or switch sensor
power. The C++ main process owns the FSM. A configured REAL mmWave serial port
must already carry the normalized JSON protocol from the B worker; TI binary
UART and point clouds are deliberately unsupported here.
"""

import argparse
import importlib.util
import json
import math
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


def finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def boolean(value):
    """Accept JSON booleans and the 0/1 values common on MCU serial links."""
    if isinstance(value, bool):
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    return None


def real_esp32_origin(incoming):
    """The raw MCU protocol may omit labels; explicit simulated labels are invalid."""
    return (incoming.get("source", "REAL_ESP32") == "REAL_ESP32"
            and incoming.get("mode", "REAL") == "REAL")


def read_json(line):
    def reject_constant(value):
        raise ValueError("non-finite JSON constant: " + value)

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite JSON number")
        return parsed

    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate JSON key: " + key)
            obj[key] = value
        return obj

    value = json.loads(line, parse_constant=reject_constant, parse_float=finite_float,
                       object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("message must be a JSON object")
    return value


def load_uwb_module():
    path = Path(__file__).resolve().with_name("safeguard_uwb_reader.py")
    spec = importlib.util.spec_from_file_location("safeguard_hub_uwb_reader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("bundled safeguard_uwb_reader.py is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ambient_module():
    path = Path(__file__).resolve().with_name("ambient_weather.py")
    spec = importlib.util.spec_from_file_location("safeguard_hub_ambient_weather", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("bundled ambient_weather.py is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_navigation_ambient_module():
    # Imported by filename so deployment uses the bundled adapter.
    path = Path(__file__).resolve().with_name("navigation_ambient.py")
    spec = importlib.util.spec_from_file_location("safeguard_navigation_ambient", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("bundled navigation_ambient.py is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SensorHub:
    def __init__(self, config, state_file, *, output=None, clock=time.monotonic):
        self.config = config
        self.hardware = config.get("hardware", {})
        self.demo = config.get("demo", {})
        self.mode = str(config.get("mode", "DEMO")).upper()
        if self.mode not in ("DEMO", "REAL"):
            raise ValueError("mode must be DEMO or REAL")
        self.profile = str(config.get("profile", "SIMULATION" if self.mode == "DEMO" else "REAL")).upper()
        if self.profile not in ("SIMULATION", "HARDWARE_DEMO", "REAL"):
            raise ValueError("profile must be SIMULATION, HARDWARE_DEMO or REAL")
        if not ((self.mode == "REAL" and self.profile == "REAL") or
                (self.mode == "DEMO" and self.profile in ("SIMULATION", "HARDWARE_DEMO"))):
            raise ValueError("mode/profile mismatch")
        if self.profile == "SIMULATION" and self.demo.get("live_sensors", False):
            raise ValueError("live_sensors requires HARDWARE_DEMO profile")
        self.simulation = self.profile == "SIMULATION"
        protocol = self.hardware.get("esp32_protocol", "link")
        if protocol not in ("link", "legacy_read_only"):
            raise ValueError("unsupported esp32_protocol")
        self.esp32_read_only = protocol == "legacy_read_only"
        if self.esp32_read_only:
            if (self.mode != "REAL" or self.profile != "REAL"
                    or self.config.get("actuation", {}).get("enabled") is not False
                    or self.config.get("required", {}).get("esp32") is not False
                    or self.demo.get("override_temperature", False) is not False):
                raise ValueError("legacy_read_only requires REAL, actuation=false, required.esp32=false and no overrides")
        if type(self.hardware.get("uwb_enabled", True)) is not bool:
            raise ValueError("hardware.uwb_enabled must be boolean")
        self.live_uwb = (not self.simulation or self.demo.get("live_uwb", False))
        self.live_uwb = self.live_uwb and self.hardware.get("uwb_enabled", True)
        self.temperature_override = (not self.simulation and self.mode == "DEMO"
                                     and self.demo.get("override_temperature", False))
        self.scenario = config.get("scenario", "normal")
        self.state_file = Path(state_file).resolve()
        self.clock = clock
        self.started = clock()
        self.run_id = "hub-" + uuid.uuid4().hex
        self.output = output
        self.output_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.stop = threading.Event()
        self.commands = queue.Queue()
        self.esp_outgoing = queue.Queue(maxsize=100)
        self.threads = []
        self.children = []
        self.dashboard = None
        self.sequences = {}
        self.processing = {"camera": False, "mmwave": False, "state": "STANDBY"}
        self.latest_real = {"telemetry": None, "camera": None, "mmwave": None}
        self.esp_pending = {}
        self.esp_origin = None
        self.esp_retired_boots = set()
        self.mmwave_origin = None
        self.mmwave_retired_runs = set()
        self.last_warning = {}
        self.uwb_module = load_uwb_module()
        self.demo_uwb = self.uwb_module.DistanceState(
            7, 2.0, str(self.hardware.get("anchor_id", "0CA7")).upper(), "DEMO")
        self.demo_last_uwb = -math.inf
        self.ambient_provider = None
        # Simulation and explicit temperature presets never access a live API.
        # An absent/disabled provider preserves the original no-provider behavior.
        if not self.simulation and not self.temperature_override:
            ambient_config = config.get("ambient_provider", {})
            if not isinstance(ambient_config, dict):
                raise ValueError("ambient_provider must be an object")
            if type(ambient_config.get("enabled", False)) is not bool:
                raise ValueError("ambient_provider.enabled must be a boolean")
            if ambient_config.get("enabled", False):
                location_mode = ambient_config.get("location_mode", "fixed")
                if location_mode == "phone":
                    self.ambient_provider = load_navigation_ambient_module().PhoneAmbientProvider(
                        ambient_config, clock=self.clock)
                elif location_mode == "fixed":
                    self.ambient_provider = load_ambient_module().AmbientProvider(
                        ambient_config, clock=self.clock)
                else:
                    raise ValueError("ambient_provider.location_mode must be fixed or phone")

    def warn(self, key, message, interval=5.0):
        now = self.clock()
        if now - self.last_warning.get(key, -math.inf) >= interval:
            self.last_warning[key] = now
            print("sensor_hub: " + message, file=sys.stderr, flush=True)

    def emit(self, message):
        # allow_nan=False also protects stdout against accidental invalid JSON.
        line = json.dumps(message, ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False)
        with self.output_lock:
            if self.output is not None:
                self.output(message)
            else:
                try:
                    print(line, flush=True)
                except BrokenPipeError:
                    self.stop.set()

    def envelope(self, kind, source, now=None):
        with self.state_lock:
            seq = self.sequences.get(kind, 0) + 1
            self.sequences[kind] = seq
        return {"type": kind, "schema_version": 1, "source": source,
                "seq": seq, "run_id": self.run_id,
                "rx_monotonic_s": self.clock() if now is None else now}

    def flags(self):
        with self.state_lock:
            return dict(self.processing)

    def remember(self, kind, now):
        with self.state_lock:
            self.latest_real[kind] = now

    def invalid_telemetry(self, now, reason):
        msg = self.envelope("telemetry", "REAL_ESP32", now)
        msg.update(pir=False, pir_valid=False, temp_c=None, temp_valid=False,
                   humidity=None, humidity_valid=False, estop=False,
                   estop_valid=False, uptime_ms=None, boot_id=None, status=reason,
                   estop_latched=None, fan_cmd=None, buzzer_cmd=None,
                   actuators_enabled=None, active_run=None, heartbeat_fault=None,
                   controller_feedback_valid=False)
        self.emit(msg)

    def normalize_telemetry(self, incoming, now):
        msg = self.envelope("telemetry", "REAL_ESP32", now)
        boot = incoming.get("boot_id")
        board_seq = incoming.get("seq")
        uptime = incoming.get("uptime_ms")
        identity_ok = (isinstance(boot, str) and 0 < len(boot) <= 128
                       and type(board_seq) is int and board_seq >= 0
                       and type(uptime) is int and uptime >= 0)
        status = "ok"
        if not real_esp32_origin(incoming):
            identity_ok = False
            status = "source_or_mode_not_real"
        elif not identity_ok:
            status = "protocol_identity_missing_or_invalid"
        else:
            previous = self.esp_origin
            if previous is not None:
                if previous[0] == boot:
                    if board_seq <= previous[1]:
                        return None  # Do not restamp a duplicate as a fresh PIR positive.
                    if uptime < previous[2]:
                        status = "uptime_regressed"
                elif boot in self.esp_retired_boots:
                    return None
                else:
                    if len(self.esp_retired_boots) >= 128:
                        status = "boot_history_full_restart_required"
                        identity_ok = False
                    else:
                        self.esp_retired_boots.add(previous[0])
            if identity_ok:
                self.esp_origin = (boot, board_seq, uptime)
        protocol_ok = identity_ok and status == "ok"
        pir, estop = boolean(incoming.get("pir")), boolean(incoming.get("estop"))
        temp, humidity = incoming.get("temp_c"), incoming.get("humidity")
        tv = protocol_ok and incoming.get("temp_valid") is True and finite_number(temp)
        hv = (protocol_ok and incoming.get("humidity_valid") is True and finite_number(humidity)
              and 0 <= humidity <= 100)
        msg.update(pir=pir if pir is not None else False,
                   pir_valid=protocol_ok and incoming.get("pir_valid") is True and pir is not None,
                   temp_c=temp if tv else None, temp_valid=tv,
                   humidity=humidity if hv else None, humidity_valid=hv,
                   estop=estop if estop is not None else False,
                   estop_valid=protocol_ok and incoming.get("estop_valid") is True and estop is not None,
                   uptime_ms=uptime if type(uptime) is int and uptime >= 0 else None,
                   boot_id=str(boot)[:128] if isinstance(boot, (str, int)) else None,
                   board_seq=board_seq if type(board_seq) is int else None,
                   status=status)
        # These are controller facts, not requests or estimates. In particular,
        # a missing latch/output value must never be invented as released/OFF.
        feedback_fields = ("estop_latched", "fan_cmd", "buzzer_cmd",
                           "actuators_enabled", "heartbeat_fault")
        for name in feedback_fields:
            value = incoming.get(name)
            msg[name] = value if protocol_ok and type(value) is bool else None
        active_run = incoming.get("active_run")
        session_ok = (isinstance(active_run, str) and len(active_run) <= 64
                      and all(c.isascii() and (c.isalnum() or c in "-_.:")
                              for c in active_run))
        msg["active_run"] = active_run if protocol_ok and session_ok else None
        msg["controller_feedback_valid"] = (protocol_ok and session_ok
                                               and all(msg[name] is not None for name in feedback_fields))
        extra = ("software_stop_latched", "physical_estop_installed", "servo_ready")
        for name in extra:
            msg[name] = incoming.get(name) if protocol_ok and type(incoming.get(name)) is bool else None
        generation = incoming.get("stop_generation")
        nonce = incoming.get("stop_nonce")
        servo = incoming.get("servo_cmd")
        msg["software_control_valid"] = (msg["controller_feedback_valid"] and
            type(incoming.get("software_control_version")) is int and incoming.get("software_control_version") == 1 and
            all(type(msg[name]) is bool for name in extra) and
            type(generation) is int and 0 < generation < 2**32 and
            isinstance(nonce, str) and 0 < len(nonce) <= 64 and
            "servo_cmd" in incoming and (servo is None or type(servo) is int and 45 <= servo <= 135))
        msg["stop_generation"] = generation if msg["software_control_valid"] else None
        msg["stop_nonce"] = nonce if msg["software_control_valid"] else None
        msg["servo_cmd"] = servo if msg["software_control_valid"] else None
        return msg

    def normalize_mmwave(self, incoming, now):
        worker_seq, worker_run = incoming.get("seq"), incoming.get("run_id")
        worker_rx = incoming.get("rx_monotonic_s")
        protocol_ok = (type(incoming.get("schema_version")) is int
                       and incoming.get("schema_version") == 1
                       and incoming.get("source") == "REAL_MMWAVE"
                       and type(worker_seq) is int and worker_seq >= 0
                       and isinstance(worker_run, str) and 0 < len(worker_run) <= 128
                       and finite_number(worker_rx))
        status = "worker_protocol_invalid"
        if protocol_ok:
            previous = self.mmwave_origin
            if previous is not None:
                if previous[0] == worker_run:
                    if worker_seq <= previous[1]:
                        return None
                elif worker_run in self.mmwave_retired_runs:
                    return None
                elif len(self.mmwave_retired_runs) >= 128:
                    protocol_ok = False
                    status = "worker_history_full_restart_required"
                else:
                    self.mmwave_retired_runs.add(previous[0])
            if protocol_ok:
                self.mmwave_origin = (worker_run, worker_seq)
                timeout = self.config.get("fsm", {}).get("mmwave_timeout_s", 2.0)
                if not finite_number(timeout) or timeout <= 0:
                    timeout = 2.0
                protocol_ok = 0 <= now - worker_rx < timeout
                status = "normalized_worker" if protocol_ok else "worker_timestamp_stale_or_future"
        msg = self.envelope("mmwave", "REAL_MMWAVE", worker_rx if finite_number(worker_rx) else now)
        enabled = self.flags()["mmwave"]
        validated = (protocol_ok and self.hardware.get("mmwave_validated") is True
                     and incoming.get("validated") is True)
        health = incoming.get("health", "unknown")
        if health not in ("ok", "fault", "unknown"):
            health = "unknown"
        kind = incoming.get("evidence_kind", "presence")
        evidence = boolean(incoming.get("evidence"))
        valid = (enabled and validated and incoming.get("valid") is True
                 and kind in ("presence", "micro_motion") and evidence is not None
                 and health == "ok")
        if not protocol_ok and enabled:
            health = "fault"
        elif not enabled or not validated:
            health = "unknown"
        msg.update(valid=valid, health=health, evidence=evidence if valid else False,
                   evidence_kind=kind if kind in ("presence", "micro_motion") else "presence",
                   validated=validated, processing=enabled,
                   worker_seq=worker_seq if type(worker_seq) is int else None,
                   worker_run_id=worker_run if isinstance(worker_run, str) else None,
                   worker_rx_monotonic_s=worker_rx if finite_number(worker_rx) else None,
                   status=status if not protocol_ok else "normalized_worker" if validated else "worker_not_validated")
        return msg

    def operator(self, action):
        stop_id = action.get("stop_request_id") if isinstance(action, dict) else None
        if isinstance(action, dict):
            action = action.get("action")
        if action in ("manual_stop", "manual_resume"):
            if self.config.get("manual_control", {}).get("enabled") is not True:
                return False
            try:
                state = json.loads(self.state_file.read_text())
                age = self.clock() - state["rx_monotonic_s"]
                if state.get("stopped") or not 0 <= age < 2.0:
                    return False
                if action == "manual_resume" and (not isinstance(stop_id, str) or
                    state.get("manual_control", {}).get("stop_request_id") != stop_id or
                    state.get("manual_control", {}).get("resume_available") is not True):
                    return False
            except (OSError, ValueError, KeyError, TypeError):
                return False
        if action in ("clear", "rearm", "manual_stop", "manual_resume"):
            msg = self.envelope("operator", "LOCAL_OPERATOR")
            msg["action"] = action
            if action == "manual_resume":
                msg["stop_request_id"] = stop_id
            self.emit(msg)
            return True
        return False

    def dispatch(self, command):
        kind = command.get("type")
        if kind == "processing":
            with self.state_lock:
                for key in ("camera", "mmwave"):
                    if isinstance(command.get(key), bool):
                        self.processing[key] = command[key]
                if isinstance(command.get("state"), str):
                    self.processing["state"] = command["state"]
            return
        if kind == "shutdown":
            self.stop.set()
            return
        if kind not in ("command", "heartbeat", "rearm", "manual_stop"):
            return
        if self.esp32_read_only:
            # Suppress ALL MCU writes, including heartbeat and rearm. Legacy
            # local AUTO is not the main application's REAL/DEMO mode.
            return
        if kind == "manual_stop":
            if (self.config.get("manual_control", {}).get("enabled") is not True or
                self.config.get("actuation", {}).get("enabled") is not True or self.simulation):
                return
            # Drop queued ON/rearm before the stop, preserving the serial worker's
            # ownership. A command already on the wire is handled by the MCU latch.
            while True:
                try: self.esp_outgoing.get_nowait()
                except queue.Empty: break
            with self.state_lock:
                self.esp_pending.clear()
        run_id, ident = command.get("run_id"), command.get("id")
        if not isinstance(run_id, str) or not run_id:
            self.warn("bad-control", "ignored control without run_id")
            return
        enabled = self.config.get("actuation", {}).get("enabled") is True
        is_command = kind == "command"
        if is_command and (not isinstance(command.get("fan"), bool)
                           or not isinstance(command.get("buzzer"), bool)):
            self.fake_ack(command, "DEMO" if self.simulation else "DRY_RUN", False)
            return
        if self.simulation or (is_command or kind == "rearm") and not enabled:
            if is_command or kind == "rearm":
                self.fake_ack(command, "DEMO" if self.simulation else "DRY_RUN",
                              self.simulation,
                              reason="simulated" if self.simulation else "actuation_disabled")
            return
        if not self.hardware.get("esp32_port"):
            self.warn("no-esp", "ESP32 port is not configured; no command was delivered")
            return
        if kind in ("command", "rearm"):
            if not isinstance(ident, (str, int)) or isinstance(ident, bool):
                self.warn("bad-command-id", "ignored command without string/integer id")
                return
            with self.state_lock:
                pending = dict(command)
                pending["_expected_boot_id"] = self.esp_origin[0] if self.esp_origin is not None else None
                self.esp_pending[(run_id, ident)] = pending
                # A malfunctioning peer must not grow this map indefinitely.
                if len(self.esp_pending) > 200:
                    self.esp_pending.pop(next(iter(self.esp_pending)))
        try:
            self.esp_outgoing.put_nowait(command)
        except queue.Full:
            self.warn("esp-tx-full", "ESP32 transmit queue is full; command not sent")

    def fake_ack(self, command, source, accepted, reason="invalid_command"):
        msg = self.envelope("ack", source)
        msg.update(id=command.get("id"), run_id=command.get("run_id"),
                   accepted=accepted, fan_cmd=command.get("fan", False),
                   buzzer_cmd=command.get("buzzer", False),
                   dry_run=source == "DRY_RUN", command_type=command.get("type"),
                   reason=reason)
        self.emit(msg)

    def accept_esp_ack(self, incoming, now):
        key = (incoming.get("run_id"), incoming.get("id"))
        if (not isinstance(key[0], str) or not isinstance(key[1], (str, int))
                or isinstance(key[1], bool)):
            self.warn("bad-ack-id", "ignored ESP32 acknowledgement with invalid id")
            return
        if not real_esp32_origin(incoming):
            self.warn("bad-ack-source", "ignored non-real ESP32 acknowledgement")
            return
        with self.state_lock:
            pending = self.esp_pending.get(key)
        if pending is None:
            self.warn("unmatched-ack", "ignored ESP32 acknowledgement with unknown id/run_id")
            return
        expected_boot = pending.get("_expected_boot_id")
        if (not expected_boot or incoming.get("boot_id") != expected_boot
                or self.esp_origin is None or self.esp_origin[0] != expected_boot):
            self.warn("old-boot-ack", "ignored ESP32 acknowledgement without matching controller boot")
            return
        with self.state_lock:
            self.esp_pending.pop(key, None)
        fan, buzzer = boolean(incoming.get("fan_cmd")), boolean(incoming.get("buzzer_cmd"))
        accepted = incoming.get("accepted") is True and fan is not None and buzzer is not None
        msg = self.envelope("ack", "REAL_ESP32", now)
        msg.update(id=key[1], run_id=key[0], accepted=accepted,
                   fan_cmd=fan if fan is not None else False,
                   buzzer_cmd=buzzer if buzzer is not None else False,
                   boot_id=incoming.get("boot_id"), command_type=pending["type"],
                   reason=str(incoming.get("reason", ""))[:256])
        for name in ("servo_cmd", "software_stop_latched", "stop_generation"):
            if name in incoming:
                msg[name] = incoming[name]
        self.emit(msg)

    def stdin_worker(self):
        try:
            for line in sys.stdin:
                if self.stop.is_set():
                    return
                try:
                    self.commands.put(read_json(line))
                except (ValueError, json.JSONDecodeError) as exc:
                    self.warn("stdin-json", "invalid main input: " + str(exc))
        finally:
            # Main owns this subprocess. An EOF means its control channel closed.
            self.stop.set()

    def spawn_thread(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        self.threads.append(thread)
        thread.start()

    def uwb_port(self):
        port = self.hardware.get("uwb_port", "auto")
        if port and str(port).lower() != "auto":
            return str(port)
        from serial.tools import list_ports
        target = str(self.hardware.get("uwb_serial", "000760217939")).lstrip("0")
        matches = [p.device for p in list_ports.comports()
                   if str(p.serial_number or "").lstrip("0") == target]
        if len(matches) != 1:
            raise RuntimeError("vehicle UWB serial %s: expected one port, found %d"
                               % (target, len(matches)))
        return matches[0]

    def invalid_uwb(self, status):
        state = self.uwb_module.DistanceState(
            7, 2.0, str(self.hardware.get("anchor_id", "0CA7")).upper(), "unavailable")
        state.invalidate(status)
        row = state.snapshot(self.clock())
        self.emit(self.uwb_module.main_message(row, window=7, timeout_s=2.0,
                                              run_id=self.run_id + "-uwb-unavailable"))

    def uwb_worker(self):
        child = None
        try:
            port = self.uwb_port()
            args = [sys.executable, "-u", str(Path(__file__).with_name("safeguard_uwb_reader.py")),
                    "--port", port, "--anchor-id", str(self.hardware.get("anchor_id", "0CA7")),
                    "--json", "--log-dir", str(self.state_file.parent / "uwb_logs")]
            # Intentionally no --start-lec: never toggle or configure the UWB.
            child = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=sys.stderr,
                                     stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     bufsize=1)
            with self.state_lock:
                self.children.append(child)
            for line in child.stdout:
                if self.stop.is_set():
                    break
                try:
                    message = read_json(line)
                    if message.get("type") == "uwb" and message.get("source") == "REAL_UWB":
                        self.emit(message)
                except (ValueError, json.JSONDecodeError) as exc:
                    self.warn("uwb-json", "reader emitted invalid JSON: " + str(exc))
            if not self.stop.is_set():
                self.invalid_uwb("reader_stopped")
                self.warn("uwb-exit", "UWB reader stopped; check power, UART stream and port")
        except Exception as exc:
            self.invalid_uwb("unavailable")
            self.warn("uwb-start", "UWB unavailable: " + str(exc))
        finally:
            if child is not None and child.poll() is None:
                child.terminate()

    def serial_worker(self, role, port, baud):
        if role == "esp32" and self.esp32_read_only:
            raise RuntimeError("legacy_read_only must never use the writable serial worker")
        try:
            import serial
        except ImportError:
            self.warn(role + "-module", "pyserial is required for " + role)
            return
        while not self.stop.is_set():
            connection = None
            try:
                connection = serial.Serial(port, baudrate=int(baud), timeout=0.1,
                                           write_timeout=0.5, rtscts=False, dsrdtr=False, exclusive=True)
                buffer = bytearray()
                while not self.stop.is_set():
                    if role == "esp32":
                        # Do not let a busy command producer starve serial RX.
                        for _ in range(8):
                            try:
                                outgoing = self.esp_outgoing.get_nowait()
                            except queue.Empty:
                                break
                            encoded = json.dumps(outgoing, separators=(",", ":"),
                                                 allow_nan=False).encode("utf-8") + b"\n"
                            connection.write(encoded)
                            connection.flush()
                    chunk = connection.read(min(max(connection.in_waiting, 1), 4096))
                    buffer.extend(chunk)
                    if len(buffer) > 65536:
                        buffer.clear()
                        self.warn(role + "-overflow", role + " line too long; discarded")
                    while b"\n" in buffer:
                        raw, _, tail = buffer.partition(b"\n")
                        buffer[:] = tail
                        try:
                            incoming = read_json(raw.decode("utf-8").strip())
                            now = self.clock()
                            if role == "esp32":
                                if incoming.get("type") == "telemetry":
                                    normalized = self.normalize_telemetry(incoming, now)
                                    if normalized is not None:
                                        self.remember("telemetry", now)
                                        self.emit(normalized)
                                elif incoming.get("type") == "ack":
                                    self.accept_esp_ack(incoming, now)
                            elif incoming.get("type") == "mmwave":
                                normalized = self.normalize_mmwave(incoming, now)
                                if normalized is not None:
                                    self.remember("mmwave", normalized["rx_monotonic_s"])
                                    self.emit(normalized)
                        except (UnicodeError, ValueError, json.JSONDecodeError, TypeError) as exc:
                            self.warn(role + "-json", role + " rejected line: " + str(exc))
            except Exception as exc:
                self.warn(role + "-serial", role + " serial unavailable: " + str(exc))
            finally:
                if connection is not None:
                    connection.close()
                if role == "esp32":
                    # A reconnect must never replay an old ON or REARM command.
                    while True:
                        try:
                            self.esp_outgoing.get_nowait()
                        except queue.Empty:
                            break
                    with self.state_lock:
                        self.esp_pending.clear()
            self.stop.wait(2.0)

    def camera_worker(self):
        camera = None
        try:
            import cv2
            import numpy as np
            from picamera2 import Picamera2
            width = int(self.hardware.get("camera_width", 320))
            height = int(self.hardware.get("camera_height", 240))
            roi_box = self.hardware.get("camera_roi", [0.0, 0.0, 1.0, 1.0])
            area = self.hardware.get("camera_area", 400)
            frames = self.hardware.get("camera_frames", 3)
            fps = self.hardware.get("camera_fps", 5)
            if (not isinstance(roi_box, list) or len(roi_box) != 4
                    or not all(finite_number(x) for x in roi_box)
                    or not 0 <= roi_box[0] < roi_box[2] <= 1
                    or not 0 <= roi_box[1] < roi_box[3] <= 1
                    or not 32 <= width <= 1920 or not 32 <= height <= 1080
                    or not finite_number(area) or area < 1
                    or type(frames) is not int or frames < 1
                    or not finite_number(fps) or not 1 <= fps <= 30):
                raise ValueError("invalid camera resolution, ROI, area, frames or fps")
            camera = Picamera2()
            camera.configure(camera.create_preview_configuration(
                main={"size": (width, height), "format": "RGB888"}))
            camera.start()
            previous = None
            streak = 0
            while not self.stop.is_set():
                if not self.flags()["camera"]:
                    previous = None
                    streak = 0
                    self.stop.wait(0.1)
                    continue
                frame = camera.capture_array()
                # Picamera2 RGB888 arrays are [B,G,R], per its official manual.
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape[:2]
                x0, y0, x1, y1 = roi_box
                roi = cv2.GaussianBlur(gray[int(h*y0):int(h*y1), int(w*x0):int(w*x1)], (5, 5), 0)
                motion = False
                valid = previous is not None
                if valid:
                    changed = cv2.absdiff(roi, previous) > 20
                    streak = streak + 1 if np.count_nonzero(changed) >= area else 0
                    motion = streak >= frames
                previous = roi
                now = self.clock()
                self.remember("camera", now)
                msg = self.envelope("camera", "REAL_CAMERA", now)
                msg.update(valid=valid, motion=motion, processing=True,
                           method="roi_frame_difference", status="motion_only_not_presence")
                self.emit(msg)
                self.stop.wait(1.0 / fps)
        except Exception as exc:
            self.warn("camera", "camera unavailable: " + str(exc))
        finally:
            if camera is not None:
                try:
                    camera.stop()
                    camera.close()
                except Exception:
                    pass

    def demo_tick(self, now):
        elapsed = now - self.started
        flags = self.flags()
        if not self.live_uwb and now - self.demo_last_uwb >= 0.5:
            self.demo_last_uwb = now
            self.demo_uwb.accept(1.0 if elapsed < 1.0 else 6.0, now)
            msg = self.uwb_module.main_message(self.demo_uwb.snapshot(now), window=7,
                                              timeout_s=2.0, run_id=self.run_id)
            msg["source"] = "DEMO"
            self.emit(msg)
        temp = self.demo.get("temperature_c", 34.0)
        ambient = self.demo.get("ambient_c", 45.0)
        if not finite_number(temp) or not finite_number(ambient):
            raise ValueError("DEMO temperature_c and ambient_c must be finite numbers")
        if self.scenario == "api_fault":
            temp = 36.0
        telemetry = self.envelope("telemetry", "DEMO", now)
        telemetry.update(pir=elapsed >= 2.0, pir_valid=True, temp_c=float(temp),
                         temp_valid=True, humidity=50.0, humidity_valid=True,
                         estop=self.scenario == "estop" and 8.0 <= elapsed < 10.0,
                         estop_valid=True, uptime_ms=int(elapsed * 1000), boot_id=self.run_id)
        self.emit(telemetry)
        camera = self.envelope("camera", "DEMO", now)
        camera.update(valid=flags["camera"], processing=flags["camera"],
                      motion=flags["camera"] and elapsed >= 2.0 and self.scenario != "unknown")
        self.emit(camera)
        mmwave = self.envelope("mmwave", "DEMO", now)
        fault = self.scenario in ("mmwave_fault", "unknown")
        mmwave.update(valid=flags["mmwave"] and not fault,
                      health=("fault" if fault else "ok") if flags["mmwave"] else "unknown",
                      evidence=flags["mmwave"] and not fault and elapsed >= 3.0,
                      evidence_kind="presence", validated=True,
                      processing=flags["mmwave"], status="simulated_not_hardware_validation")
        self.emit(mmwave)
        ambient_msg = self.envelope("ambient", "DEMO", now)
        ambient_msg.update(valid=self.scenario != "api_fault",
                           temp_c=float(ambient) if self.scenario != "api_fault" else None)
        self.emit(ambient_msg)

    def demo_temperature_tick(self, now):
        temp, ambient = self.demo.get("temperature_c", 34.0), self.demo.get("ambient_c", 45.0)
        if not finite_number(temp) or not finite_number(ambient):
            raise ValueError("DEMO temperature presets must be finite numbers")
        temperature = self.envelope("temperature", "DEMO", now)
        temperature.update(valid=True, temp_c=float(temp), status="preset_not_measured")
        self.emit(temperature)
        ambient_msg = self.envelope("ambient", "DEMO", now)
        ambient_msg.update(valid=True, temp_c=float(ambient), status="preset_not_api")
        self.emit(ambient_msg)

    def real_watchdog_tick(self, now):
        flags = self.flags()
        with self.state_lock:
            last = dict(self.latest_real)
        if last["telemetry"] is None or now - last["telemetry"] >= 2.0:
            reason = "port_not_configured" if not self.hardware.get("esp32_port") else "missing_or_stale"
            self.invalid_telemetry(now, reason)
        for kind, source in (("camera", "REAL_CAMERA"), ("mmwave", "REAL_MMWAVE")):
            if not flags[kind] or last[kind] is None or now - last[kind] >= 2.0:
                msg = self.envelope(kind, source, now)
                msg.update(valid=False, processing=flags[kind])
                if kind == "camera":
                    msg.update(motion=False, status="disabled" if not flags[kind] else "unavailable")
                else:
                    msg.update(health="fault" if flags[kind] else "unknown", evidence=False,
                               evidence_kind="presence", validated=False,
                               status="disabled" if not flags[kind] else "worker_unavailable")
                self.emit(msg)
        if not self.simulation and not self.temperature_override:
            ambient = self.envelope("ambient", "REAL_AMBIENT", now)
            if self.ambient_provider is None:
                ambient.update(valid=False, temp_c=None, status="ambient_provider_not_configured")
            else:
                # The provider expires by the weather value's original valid
                # time, not this republish time. RX is the local hub transport
                # timestamp; provenance retains API valid/receive/expiry times.
                ambient.update(self.ambient_provider.snapshot(now))
                self.write_ambient_status(ambient)
            self.emit(ambient)

    def write_ambient_status(self, message):
        path = self.state_file.with_name("ambient_status.json")
        temporary = path.with_name("ambient_status." + self.run_id + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(message, ensure_ascii=False,
                                             allow_nan=False) + "\n", encoding="utf-8")
            temporary.replace(path)
        except (OSError, ValueError) as exc:
            self.warn("ambient-log", "ambient status could not be saved: " + str(exc))
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def ambient_worker(self):
        # HTTP timeouts and retries cannot block the main sensor/FSM loop.
        while not self.stop.is_set() and self.ambient_provider is not None:
            try:
                self.ambient_provider.refresh()
            except Exception as exc:
                # Normal network errors are handled by the provider itself.
                # Even an unexpected worker exception must leave expiry active.
                self.warn("ambient-worker", "ambient refresh failed: " + str(exc))
            self.stop.wait(getattr(self.ambient_provider, "worker_poll_interval_s",
                                   self.ambient_provider.poll_interval_s))

    def start(self):
        self.spawn_thread(self.stdin_worker)
        if self.config.get("dashboard", {}).get("enabled", True):
            try:
                from dashboard import start_dashboard
                self.dashboard = start_dashboard(str(self.state_file), self.config, self.operator)
            except Exception as exc:
                self.warn("dashboard", "dashboard unavailable: " + str(exc))
        if self.live_uwb:
            self.spawn_thread(self.uwb_worker)
        elif not self.simulation:
            self.invalid_uwb("disabled_for_input_check")
        if not self.simulation:
            if not self.temperature_override and self.ambient_provider is not None:
                self.spawn_thread(self.ambient_worker)
            if self.hardware.get("esp32_port"):
                if self.esp32_read_only:
                    path = Path(__file__).with_name("block_a_legacy_readonly.py")
                    spec = importlib.util.spec_from_file_location("block_a_legacy_readonly", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self.spawn_thread(module.run, self, self.hardware["esp32_port"])
                else:
                    self.spawn_thread(self.serial_worker, "esp32", self.hardware["esp32_port"],
                                      self.hardware.get("esp32_baud", 115200))
            if self.hardware.get("mmwave_json_port"):
                self.spawn_thread(self.serial_worker, "mmwave", self.hardware["mmwave_json_port"],
                                  self.hardware.get("mmwave_baud", 115200))
            if self.hardware.get("camera_enabled", False):
                self.spawn_thread(self.camera_worker)

    def close(self):
        self.stop.set()
        with self.state_lock:
            children = list(self.children)
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=1.0)
        for thread in self.threads:
            if thread is not threading.current_thread():
                thread.join(timeout=0.5)
        if self.dashboard is not None:
            try:
                if hasattr(self.dashboard, "shutdown"):
                    self.dashboard.shutdown()
                    if hasattr(self.dashboard, "server_close"):
                        self.dashboard.server_close()
                elif hasattr(self.dashboard, "stop"):
                    self.dashboard.stop()
            except Exception as exc:
                self.warn("dashboard-close", str(exc))

    def run(self):
        rate = self.demo.get("rate_hz", 10)
        if not finite_number(rate) or not 1 <= rate <= 100:
            raise ValueError("demo.rate_hz must be between 1 and 100")
        period = 1.0 / rate if self.mode == "DEMO" else 0.1
        last_watchdog = -math.inf
        self.start()
        try:
            while not self.stop.is_set():
                tick_start = self.clock()
                for _ in range(100):
                    try:
                        self.dispatch(self.commands.get_nowait())
                    except queue.Empty:
                        break
                if self.simulation:
                    self.demo_tick(tick_start)
                else:
                    if self.temperature_override:
                        self.demo_temperature_tick(tick_start)
                    if tick_start - last_watchdog >= 1.0:
                        self.real_watchdog_tick(tick_start)
                        last_watchdog = tick_start
                self.stop.wait(max(0, period - (self.clock() - tick_start)))
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--state-file", required=True)
    args = parser.parse_args()
    try:
        config = read_json(Path(args.config).read_text(encoding="utf-8"))
        hub = SensorHub(config, args.state_file)
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, lambda _s, _f: hub.stop.set())
        hub.run()
    except Exception as exc:
        print("sensor_hub: fatal: " + str(exc), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
