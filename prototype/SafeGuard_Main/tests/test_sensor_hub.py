"""Protocol/fault tests; these do not certify physical sensors or actuators."""
import importlib.util
import io
import json
import pathlib
import sys
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sensor_hub", ROOT / "scripts" / "sensor_hub.py")
hub_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub_module)


class HubTests(unittest.TestCase):
    def test_mode_profile_mismatch_is_rejected(self):
        for mode,profile in (("DEMO","REAL"),("REAL","SIMULATION"),("REAL","HARDWARE_DEMO")):
            with self.assertRaises(ValueError):
                self.make_hub(mode=mode,profile=profile)
        with self.assertRaises(ValueError):
            self.make_hub(demo={"live_sensors":True})

    def make_hub(self, **updates):
        config = {"mode": "DEMO", "profile": "SIMULATION", "scenario": "normal",
                  "hardware": {"anchor_id": "0CA7", "mmwave_validated": False},
                  "actuation": {"enabled": False}, "dashboard": {"enabled": False},
                  "demo": {"live_uwb": False, "rate_hz": 10,
                           "temperature_c": 34.0, "ambient_c": 45.0}}
        config.update(updates)
        messages = []
        hub = hub_module.SensorHub(config, ROOT / "runs" / "test" / "state.json",
                                   output=messages.append, clock=lambda: 100.0)
        return hub, messages

    def test_simulation_reuses_real_filter_and_labels_every_sensor(self):
        hub, messages = self.make_hub()
        hub.dispatch({"type": "processing", "camera": True, "mmwave": True})
        for offset in range(7):
            hub.demo_tick(100.0 + offset * 0.5)
        uwb = [m for m in messages if m["type"] == "uwb"]
        self.assertIsNone(uwb[5]["distance_m"])
        self.assertTrue(uwb[6]["usable_for_fsm"])
        self.assertEqual(uwb[6]["sample_count"], 7)
        self.assertAlmostEqual(uwb[6]["distance_m"], (2 + 5*6)/7)
        self.assertTrue(all(m["source"] == "DEMO" for m in messages))

    def test_hardware_demo_missing_sensors_never_become_simulated_positives(self):
        hub, messages = self.make_hub(profile="HARDWARE_DEMO",
                                     demo={"live_uwb": True, "live_sensors": True,
                                           "override_temperature": True,
                                           "temperature_c": 34.0, "ambient_c": 45.0})
        self.assertFalse(hub.simulation)
        self.assertTrue(hub.live_uwb)
        hub.dispatch({"type": "processing", "camera": True, "mmwave": True})
        hub.real_watchdog_tick(120.0)
        hub.demo_temperature_tick(120.0)
        typed = {m["type"]: m for m in messages}
        self.assertFalse(typed["telemetry"]["pir_valid"])
        self.assertFalse(typed["telemetry"]["pir"])
        self.assertFalse(typed["camera"]["valid"])
        self.assertFalse(typed["camera"]["motion"])
        self.assertFalse(typed["mmwave"]["valid"])
        self.assertFalse(typed["mmwave"]["evidence"])
        self.assertEqual(typed["telemetry"]["source"], "REAL_ESP32")
        self.assertEqual(typed["temperature"]["source"], "DEMO")
        self.assertEqual(typed["temperature"]["temp_c"], 34.0)
        self.assertFalse(any(m["type"] == "uwb" for m in messages))

    def test_hybrid_simulation_does_not_also_emit_fake_uwb(self):
        hub, messages = self.make_hub(demo={"live_uwb": True})
        hub.demo_tick(120.0)
        self.assertFalse(any(m["type"] == "uwb" for m in messages))

    def test_real_missing_ambient_and_inputs_are_explicitly_invalid(self):
        hub, messages = self.make_hub(mode="REAL", profile="REAL")
        hub.real_watchdog_tick(100.0)
        ambient = next(m for m in messages if m["type"] == "ambient")
        self.assertFalse(ambient["valid"])
        self.assertIsNone(ambient["temp_c"])
        self.assertEqual(ambient["source"], "REAL_AMBIENT")

    def test_telemetry_does_not_trust_source_timestamp_or_missing_validity(self):
        hub, _ = self.make_hub()
        message = hub.normalize_telemetry({"type": "telemetry", "source": "DEMO",
                                          "rx_monotonic_s": 9999999, "pir": True,
                                          "temp_c": float("nan"), "temp_valid": True,
                                          "humidity": 101, "humidity_valid": True,
                                          "estop": False, "boot_id": "boot-A",
                                          "uptime_ms": 123, "seq": 9}, 101.0)
        self.assertEqual(message["source"], "REAL_ESP32")
        self.assertEqual(message["rx_monotonic_s"], 101.0)
        self.assertFalse(message["pir_valid"])
        self.assertFalse(message["temp_valid"])
        self.assertIsNone(message["temp_c"])
        self.assertFalse(message["humidity_valid"])
        self.assertFalse(message["estop_valid"])
        self.assertEqual(message["boot_id"], "boot-A")
        self.assertEqual(message["board_seq"], 9)

    def test_explicit_demo_telemetry_cannot_be_promoted_to_real(self):
        base = {"type": "telemetry", "boot_id": "boot-a", "seq": 1,
                "uptime_ms": 500, "pir": True, "pir_valid": True,
                "temp_c": 36.0, "temp_valid": True,
                "estop": False, "estop_valid": True}
        for conflicting in ({"source": "DEMO"}, {"mode": "DEMO"},
                            {"source": None}, {"mode": None},
                            {"source": "REAL_CAMERA"}):
            hub, _ = self.make_hub(mode="REAL", profile="REAL")
            row = hub.normalize_telemetry(dict(base, **conflicting), 100.0)
            self.assertFalse(row["pir_valid"])
            self.assertFalse(row["temp_valid"])
            self.assertFalse(row["estop_valid"])
            self.assertEqual(row["status"], "source_or_mode_not_real")
            self.assertIsNone(hub.esp_origin)
            # The rejected frame must not consume a legitimate sequence/boot.
            self.assertTrue(hub.normalize_telemetry(base, 100.1)["pir_valid"])

    def test_controller_feedback_is_complete_strict_and_never_fabricated(self):
        base = {"type": "telemetry", "boot_id": "boot-a", "seq": 1,
                "uptime_ms": 500, "pir": False, "pir_valid": True,
                "estop": False, "estop_valid": True,
                "estop_latched": True, "fan_cmd": False, "buzzer_cmd": False,
                "actuators_enabled": True, "active_run": "main-A",
                "heartbeat_fault": False}
        hub, messages = self.make_hub(mode="REAL", profile="REAL")
        row = hub.normalize_telemetry(base, 100.0)
        self.assertTrue(row["controller_feedback_valid"])
        self.assertTrue(row["estop_latched"])
        self.assertFalse(row["estop"])
        for field in ("estop_latched", "fan_cmd", "buzzer_cmd", "actuators_enabled", "heartbeat_fault"):
            for bad in (None, 0, 1, "false"):
                current, _ = self.make_hub(mode="REAL", profile="REAL")
                malformed = current.normalize_telemetry(dict(base, **{field: bad}), 100.0)
                self.assertFalse(malformed["controller_feedback_valid"])
                self.assertIsNone(malformed[field])
        for bad_session in (None, 12, "bad session", "x" * 65):
            current, _ = self.make_hub(mode="REAL", profile="REAL")
            malformed = current.normalize_telemetry(dict(base, active_run=bad_session), 100.0)
            self.assertFalse(malformed["controller_feedback_valid"])
            self.assertIsNone(malformed["active_run"])
        hub.invalid_telemetry(103.0, "missing_or_stale")
        self.assertFalse(messages[-1]["controller_feedback_valid"])
        self.assertIsNone(messages[-1]["estop_latched"])
        self.assertIsNone(messages[-1]["fan_cmd"])
        current, _ = self.make_hub(mode="REAL", profile="REAL")
        no_session_yet = current.normalize_telemetry(dict(base, active_run=""), 100.0)
        self.assertTrue(no_session_yet["controller_feedback_valid"])
        self.assertEqual(no_session_yet["active_run"], "")

    def test_mmwave_unvalidated_worker_never_produces_evidence(self):
        hub, _ = self.make_hub()
        hub.dispatch({"type": "processing", "mmwave": True})
        row = {"valid": True, "health": "ok", "evidence": True,
               "evidence_kind": "presence", "validated": True,
               "schema_version": 1, "source": "REAL_MMWAVE", "seq": 1,
               "run_id": "worker-a", "rx_monotonic_s": 99.5}
        message = hub.normalize_mmwave(row, 100.0)
        self.assertFalse(message["valid"])
        self.assertFalse(message["evidence"])
        self.assertFalse(message["validated"])

    def test_mmwave_both_validations_and_processing_are_required(self):
        hub, _ = self.make_hub(hardware={"mmwave_validated": True})
        row = {"valid": True, "health": "ok", "evidence": True,
               "evidence_kind": "micro_motion", "validated": True,
               "schema_version": 1, "source": "REAL_MMWAVE", "seq": 1,
               "run_id": "worker-a", "rx_monotonic_s": 99.5}
        self.assertFalse(hub.normalize_mmwave(row, 100.0)["valid"])
        hub.dispatch({"type": "processing", "mmwave": True})
        row["seq"] = 2
        self.assertTrue(hub.normalize_mmwave(row, 100.0)["valid"])
        row["evidence_kind"] = "point_cloud"
        row["seq"] = 3
        self.assertFalse(hub.normalize_mmwave(row, 100.0)["valid"])
        row["evidence_kind"] = "presence"
        row["validated"] = False
        row["seq"] = 4
        self.assertFalse(hub.normalize_mmwave(row, 100.0)["valid"])

    def test_esp_replayed_frames_do_not_refresh_positive_evidence(self):
        hub, _ = self.make_hub()
        row = {"seq": 10, "boot_id": "boot-a", "uptime_ms": 1000,
               "pir": True, "pir_valid": True, "estop": False, "estop_valid": True,
               "temp_c": 34.0, "temp_valid": True}
        self.assertTrue(hub.normalize_telemetry(row, 100.0)["pir_valid"])
        self.assertIsNone(hub.normalize_telemetry(row, 101.0))
        row["seq"] = 9
        self.assertIsNone(hub.normalize_telemetry(row, 102.0))
        row.update(seq=11, uptime_ms=50)
        regressed = hub.normalize_telemetry(row, 103.0)
        self.assertFalse(regressed["pir_valid"])
        self.assertFalse(regressed["temp_valid"])
        self.assertEqual(regressed["status"], "uptime_regressed")
        row.update(seq=12, uptime_ms=100)
        self.assertTrue(hub.normalize_telemetry(row, 103.1)["pir_valid"])
        row.update(seq=0, uptime_ms=0, boot_id="boot-b")
        self.assertTrue(hub.normalize_telemetry(row, 104.0)["pir_valid"])
        row.update(seq=99, uptime_ms=9000, boot_id="boot-a")
        self.assertIsNone(hub.normalize_telemetry(row, 105.0))

    def test_esp_missing_identity_cannot_create_valid_fields(self):
        hub, _ = self.make_hub()
        row = {"pir": True, "pir_valid": True, "temp_c": 40.0, "temp_valid": True,
               "estop": False, "estop_valid": True}
        message = hub.normalize_telemetry(row, 100.0)
        self.assertFalse(message["pir_valid"])
        self.assertFalse(message["temp_valid"])
        self.assertFalse(message["estop_valid"])
        self.assertIn("protocol", message["status"])

    def test_mmwave_timestamp_and_worker_sequence_are_not_restamped(self):
        hub, _ = self.make_hub(hardware={"mmwave_validated": True})
        hub.dispatch({"type": "processing", "mmwave": True})
        row = {"valid": True, "health": "ok", "evidence": True,
               "evidence_kind": "presence", "validated": True,
               "schema_version": 1, "source": "REAL_MMWAVE", "seq": 1,
               "run_id": "worker-a", "rx_monotonic_s": 99.5}
        first = hub.normalize_mmwave(row, 100.0)
        self.assertTrue(first["valid"])
        self.assertEqual(first["rx_monotonic_s"], 99.5)
        self.assertIsNone(hub.normalize_mmwave(row, 100.5))
        row["seq"] = 2
        stale = hub.normalize_mmwave(row, 102.0)
        self.assertFalse(stale["valid"])
        self.assertFalse(stale["evidence"])
        self.assertEqual(stale["rx_monotonic_s"], 99.5)
        row.update(seq=3, rx_monotonic_s=200)
        self.assertFalse(hub.normalize_mmwave(row, 102.0)["valid"])
        row.update(seq=4, rx_monotonic_s=102.0)
        self.assertTrue(hub.normalize_mmwave(row, 102.0)["valid"])
        row.update(seq=0, run_id="worker-b")
        self.assertTrue(hub.normalize_mmwave(row, 102.0)["valid"])
        row.update(seq=100, run_id="worker-a")
        self.assertIsNone(hub.normalize_mmwave(row, 102.0))

    def test_mmwave_missing_protocol_or_demo_source_is_never_real_evidence(self):
        hub, _ = self.make_hub(hardware={"mmwave_validated": True})
        hub.dispatch({"type": "processing", "mmwave": True})
        row = {"valid": True, "health": "ok", "evidence": True,
               "evidence_kind": "presence", "validated": True}
        self.assertFalse(hub.normalize_mmwave(row, 100.0)["valid"])
        row.update(schema_version=1, source="DEMO", seq=1, run_id="worker", rx_monotonic_s=100)
        self.assertFalse(hub.normalize_mmwave(row, 100.0)["valid"])

    def test_simulation_ack_is_explicitly_demo(self):
        hub, messages = self.make_hub()
        hub.dispatch({"type": "command", "run_id": "main", "id": "c1",
                      "fan": True, "buzzer": False})
        self.assertEqual(messages[-1]["source"], "DEMO")
        self.assertTrue(messages[-1]["accepted"])
        self.assertTrue(hub.esp_outgoing.empty())

    def test_hardware_disabled_actuation_is_not_an_accepted_ack(self):
        hub, messages = self.make_hub(profile="HARDWARE_DEMO",
                                     hardware={"esp32_port": "/dev/fake"})
        for kind in ("command", "rearm"):
            hub.dispatch({"type": kind, "run_id": "main", "id": "c1",
                          "fan": True, "buzzer": False})
        self.assertTrue(all(m["source"] == "DRY_RUN" and not m["accepted"] for m in messages))
        self.assertTrue(all(m["reason"] == "actuation_disabled" for m in messages))
        self.assertTrue(hub.esp_outgoing.empty())

    def test_real_ack_must_match_run_and_id_and_have_output_values(self):
        hub, messages = self.make_hub(mode="REAL", profile="REAL",
                                     hardware={"esp32_port": "/dev/fake"},
                                     actuation={"enabled": True})
        hub.normalize_telemetry({"boot_id": "boot", "seq": 1, "uptime_ms": 500}, 99.0)
        command = {"type": "command", "run_id": "main", "id": "c1",
                   "fan": True, "buzzer": False}
        hub.dispatch(command)
        self.assertEqual(hub.esp_outgoing.get_nowait(), command)
        hub.accept_esp_ack({"run_id": "old", "id": "c1", "accepted": True,
                            "fan_cmd": True, "buzzer_cmd": False}, 100.0)
        self.assertFalse(messages)
        hub.accept_esp_ack({"run_id": "main", "id": "c1", "accepted": True,
                            "fan_cmd": True, "buzzer_cmd": False, "boot_id": "boot"}, 101.0)
        self.assertEqual(messages[-1]["source"], "REAL_ESP32")
        self.assertTrue(messages[-1]["accepted"])
        self.assertEqual(messages[-1]["run_id"], "main")

    def test_ack_is_bound_to_real_origin_and_current_controller_boot(self):
        hub, messages = self.make_hub(mode="REAL", profile="REAL",
                                     hardware={"esp32_port": "/dev/fake"},
                                     actuation={"enabled": True})
        hub.normalize_telemetry({"boot_id": "boot-a", "seq": 1, "uptime_ms": 500}, 99.0)
        command = {"type": "rearm", "run_id": "main", "id": "r1"}
        hub.dispatch(command)
        ack = {"type": "ack", "run_id": "main", "id": "r1", "accepted": True,
               "fan_cmd": False, "buzzer_cmd": False, "boot_id": "boot-a"}
        for conflicting in ({"source": "DEMO"}, {"mode": "DEMO"}, {"boot_id": "old-boot"}):
            hub.accept_esp_ack(dict(ack, **conflicting), 100.0)
            self.assertFalse(messages)
        hub.normalize_telemetry({"boot_id": "boot-b", "seq": 1, "uptime_ms": 10}, 100.1)
        hub.accept_esp_ack(ack, 100.2)
        hub.accept_esp_ack(dict(ack, boot_id="boot-b"), 100.2)
        self.assertFalse(messages)  # Neither boot may acknowledge the pre-reboot request.
        hub.dispatch(dict(command, id="r2"))
        hub.accept_esp_ack(dict(ack, id="r2", boot_id="boot-b"), 100.3)
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[-1]["accepted"])
        self.assertEqual(messages[-1]["boot_id"], "boot-b")

    def test_watchdog_does_not_restamp_a_stale_positive_sensor(self):
        hub, messages = self.make_hub(mode="REAL", profile="REAL")
        hub.remember("telemetry", 100.0)
        hub.real_watchdog_tick(101.0)
        self.assertFalse(any(m["type"] == "telemetry" for m in messages))
        messages.clear()
        hub.real_watchdog_tick(102.0)
        telemetry = next(m for m in messages if m["type"] == "telemetry")
        self.assertFalse(telemetry["temp_valid"])
        self.assertFalse(telemetry["pir_valid"])

    def test_operator_actions_only_request_clear_or_rearm(self):
        hub, messages = self.make_hub()
        hub.operator("clear")
        hub.operator({"action": "rearm"})
        hub.operator("fan_on")
        self.assertEqual([m["action"] for m in messages], ["clear", "rearm"])
        self.assertTrue(all(m["type"] == "operator" for m in messages))
        self.assertTrue(hub.esp_outgoing.empty())

    def test_real_uwb_child_is_passive(self):
        hub, messages = self.make_hub(mode="REAL", profile="REAL",
                                     hardware={"uwb_port": "COM3", "anchor_id": "0CA7"})
        child = mock.Mock()
        child.stdout = io.StringIO(json.dumps({"type": "uwb", "source": "REAL_UWB",
                                               "distance_m": 1.0}) + "\n")
        child.poll.return_value = 0
        with mock.patch.object(hub_module.subprocess, "Popen", return_value=child) as popen:
            hub.uwb_worker()
        args = popen.call_args[0][0]
        self.assertIn("--json", args)
        self.assertIn("COM3", args)
        self.assertNotIn("--start-lec", args)
        self.assertNotIn("lec", args)
        self.assertTrue(any(m.get("source") == "REAL_UWB" and m.get("distance_m") == 1.0
                            for m in messages))

    def test_read_json_rejects_non_finite_and_non_objects(self):
        for bad in ('{"temp_c":NaN}', '{"temp_c":Infinity}', '{"temp_c":1e999}',
                    '{"seq":1,"seq":2}', "[]", "null"):
            with self.assertRaises(ValueError):
                hub_module.read_json(bad)


if __name__ == "__main__":
    unittest.main()
