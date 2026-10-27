"""Sensor observation bridge for the team's AUTO/MANUAL sketch, never a controller.

Only Pi receipt time and hub ordering are known. No MCU boot/sequence/uptime,
ESTOP, command acknowledgement or physical output feedback is fabricated.
This cannot validate capture-time freshness, MCU restarts or duplicate samples.
Production actuation with this protocol is prohibited by the hub's config guard.
"""
import json
import math
import os
from pathlib import Path
import uuid

BLOCKED = {(0x1366, 0x0105), (0x10C4, 0xEA70)}


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def bit(x):
    if type(x) is bool:
        return x
    if type(x) is int and x in (0, 1):
        return bool(x)
    raise ValueError("expected bool or 0/1")


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def reject(x):
        raise ValueError("nonfinite JSON constant")
    def number(x):
        result = float(x)
        if not math.isfinite(result):
            raise ValueError("nonfinite number")
        return result
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                        parse_constant=reject, parse_float=number)
    if not isinstance(result, dict):
        raise ValueError("expected JSON object")
    return result


class Framer:
    def __init__(self):
        self.buf, self.discard = bytearray(), False

    def feed(self, chunk):
        for byte in chunk:
            if byte == 10:
                if not self.discard:
                    yield "line", bytes(self.buf)
                self.buf.clear()
                self.discard = False
            elif not self.discard:
                if len(self.buf) >= 2048:
                    yield "oversized", bytes(self.buf)
                    self.buf.clear()
                    self.discard = True
                else:
                    self.buf.append(byte)


def fields(data):
    if data.get("source", "REAL_ESP32") != "REAL_ESP32":
        raise ValueError("unexpected source")
    kind = data.get("type")
    if kind in ("ack", "error", "status") and "sensor_ok" not in data:
        return None
    if kind not in (None, "telemetry") or type(data.get("sensor_ok")) is not bool:
        raise ValueError("not the observed A sensor protocol")
    mode = data.get("mode")
    if mode not in (None, "AUTO", "MANUAL"):
        raise ValueError("invalid local control mode")
    valid = data["sensor_ok"]
    temp, humidity, pir = None, None, False
    if valid:
        temp, humidity = data.get("temp"), data.get("hum")
        if (not finite(temp) or not -40 <= temp <= 125 or not finite(humidity)
                or not 0 <= humidity <= 100):
            raise ValueError("invalid temperature/humidity")
        pir = bit(data.get("pir"))
    servo = data.get("servo")
    if servo is not None and (type(servo) is not int or not 45 <= servo <= 135):
        raise ValueError("invalid servo command angle")
    reported = {"control_mode": mode, "servo_angle_command": servo,
                "sensor_ok": valid}
    for key in ("fan", "buzzer", "alarm"):
        reported[key + "_reported"] = bit(data[key]) if key in data else None
    return {"pir": pir, "pir_valid": valid, "temp_c": temp, "temp_valid": valid,
            "humidity": humidity, "humidity_valid": valid,
            "estop": None, "estop_valid": False,
            "boot_id": None, "board_seq": None, "uptime_ms": None,
            "estop_latched": None, "fan_cmd": None, "buzzer_cmd": None,
            "actuators_enabled": None, "heartbeat_fault": None, "active_run": None,
            "controller_feedback_valid": False, "legacy_reported": reported,
            "protocol": "LEGACY_READ_ONLY", "timestamp_basis": "pi_receive_only",
            "mcu_identity_available": False, "output_transport_enabled": False,
            "status": "legacy_sensor_observation" if valid else "legacy_sensor_invalid"}


def verify_port(name, ports):
    matches = [p for p in ports if str(p.device) == name or
               os.path.realpath(str(p.device)) == os.path.realpath(name)]
    if any((p.vid, p.pid) in BLOCKED for p in matches):
        raise ValueError("refusing UWB/mmWave port")
    if not matches:
        raise ValueError("ESP port not enumerated; reconnect and confirm by-id")


def run(hub, name, *, serial_module=None, ports_fn=None):
    if not hub.esp32_read_only or hub.config.get("actuation", {}).get("enabled") is not False:
        raise ValueError("read-only guard not satisfied")
    if serial_module is None:
        import serial as serial_module
    if ports_fn is None:
        from serial.tools import list_ports
        ports_fn = list_ports.comports
    log_path = Path(hub.state_file).with_name("block_a_serial.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        def record(event, session, raw=None, error=None):
            item = {"rx_monotonic_s": hub.clock(), "event": event,
                    "usb_connection_id": session, "uart_payload_bytes_sent": 0}
            if raw is not None:
                item.update(hex=raw.hex(), text=raw.decode("utf-8", errors="replace"))
            if error is not None:
                item["error"] = str(error)[:300]
            log.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
            log.flush()
        while not hub.stop.is_set():
            connection, session = None, uuid.uuid4().hex
            try:
                verify_port(name, list(ports_fn()))
                options = dict(port=None, baudrate=115200, timeout=0.1,
                               xonxoff=False, rtscts=False, dsrdtr=False)
                if os.name == "posix":
                    options["exclusive"] = True
                connection = serial_module.Serial(**options)
                connection.dtr = connection.rts = False
                connection.port = name
                connection.open()
                # Discard bytes pending from before this observation session.
                connection.reset_input_buffer()
                record("opened", session)
                hub.invalid_telemetry(hub.clock(), "legacy_waiting_new_sample")
                framer = Framer()
                while not hub.stop.is_set():
                    chunk = connection.read(min(connection.in_waiting or 1, 4096))
                    for event, raw in framer.feed(chunk):
                        record(event, session, raw)
                        if event == "oversized":
                            hub.invalid_telemetry(hub.clock(), "legacy_oversized_line")
                            continue
                        if not raw.strip():
                            continue
                        # Known startup banner also resets old positive PIR evidence.
                        if not raw.lstrip().startswith(b"{"):
                            if raw.lstrip().startswith((b"Commands:", b"ets ", b"rst:")):
                                hub.invalid_telemetry(hub.clock(), "legacy_startup_text")
                            continue
                        try:
                            values = fields(parse_json(raw))
                            if values is None:
                                continue
                            now = hub.clock()
                            msg = hub.envelope("telemetry", "REAL_ESP32", now)
                            msg.update(values, usb_connection_id=session)
                            hub.remember("telemetry", now)
                            hub.emit(msg)
                        except (ValueError, TypeError, UnicodeError) as error:
                            record("rejected", session, error=error)
                            hub.invalid_telemetry(hub.clock(), "legacy_rejected_sample")
            except Exception as error:
                record("connection_error", session, error=error)
                hub.invalid_telemetry(hub.clock(), "legacy_serial_unavailable")
                hub.warn("legacy-serial", "A read-only serial: " + str(error))
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass
                hub.invalid_telemetry(hub.clock(), "legacy_connection_closed")
                record("closed", session)
            hub.stop.wait(2)
