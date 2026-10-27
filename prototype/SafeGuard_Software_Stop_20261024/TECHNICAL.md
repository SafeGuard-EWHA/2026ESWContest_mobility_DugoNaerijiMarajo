# SafeGuard software manual stop integration 0.3.0

This package extends the reviewed main 0.1.1 plus A legacy-readonly adapter and existing navigation/weather updates. Installer hashes reject unknown source changes. It stages a native C++ build and existing core/parser tests before replacing files, keeps backups, and creates a separate REAL navigation/control config. No ESP flashing, service changes, reboot, or remote hardware operations occur during installation.

## Control path

Local dashboard HTTP (through SSH) → SensorHub LOCAL_OPERATOR envelope → C++ ManualControl → existing SensorHub serial owner → ESP32. The UI does not open serial or directly drive GPIO.

- Starts held on every main and MCU boot. No NVS writes are required because every reboot requires explicit resume.
- `manual_stop` contains `run_id` and a unique `stop_nonce`. It cancels queued command/rearm traffic. Firmware accepts STOP even without heartbeat, switches fan/buzzer OFF, releases servo PWM, and latches.
- Identical STOP retries preserve `stop_generation`; a new STOP changes generation. Fresh telemetry echoes nonce, generation, boot and output commands. The main only confirms the matching request while feedback is fresh.
- Dashboard `manual_resume` includes the currently displayed `stop_request_id`. The hub checks current saved state freshness/identity, and the main independently checks its live nonce. Thus an old browser resume request cannot release a newer stop.
- MCU resume uses the canonical `rearm` request with monotonic request ID, current boot and stop generation. Resume needs heartbeat plus accepted ACK and subsequent matching OFF/unlatched telemetry. ACK alone cannot resume outputs. The FSM resets after success.
- Resume ACK loss retries the same ID. Timeout returns to a new STOP request. STOP wins if stop/resume arrive in one input batch.
- On telemetry loss the main blocks new output commands and reports stop unconfirmed. The MCU retains fan/buzzer requests on heartbeat timeout and releases servo PWM. Reconnection triggers STOP and needs manual resume.
- Software STOP is not a hardware emergency-stop circuit or a guarantee of physical shaft stopping. ESP output reports are not physical feedback.

## Wire extensions

Telemetry adds `software_control_version=1`, `software_stop_latched`, `stop_generation`, `stop_nonce`, `servo_cmd`, `servo_ready`, `physical_estop_installed=false`. Physical `estop_valid` stays false.

Normal commands optionally contain `servo_deg`: null disables PWM, integer 45–135 requests an angle. A normal command without this field preserves the current servo request for compatibility. New main always sends the field when manual control is enabled and validates the corresponding ACK. Protection angle is configured explicitly; default null. There is no calibrated window opening distance or automatic closing command.

Pins follow the provided sketch_oct24b.ino: PIR27, SHT31 SDA32/SCL33, fan25, buzzer26, servo13. Firmware removes the old independent temperature AUTO loop; the Pi owns protection decisions. No physical E-stop GPIO is assigned.

## Scope

Existing UWB/camera/weather configuration and FSM thresholds are preserved. The original core couples `required.esp32` with a physical E-stop; that flag remains false. Independent strict controller/protocol readiness gates every output. This package does not claim that mmWave occupancy validation, thermal-model calibration, actual ESP32 target build, electrical integrity, physical output verification, or full vehicle integration have been completed.

Synthetic UWB/camera and mocked peripherals appear only inside disposable automated test copies. Production scripts have no synthetic input backdoor. Existing SIMULATION/REAL source distinctions remain.

## Installation and rollback

See README_KO.txt. On failure before application, the source project is unchanged. An exception during file replacement restores prior contents. Backups under `backups/software_stop_*` contain replaced files, the prior executable, and a restore manifest listing previously absent files. Do not roll back the main while leaving a mismatched MCU firmware in control; stop outputs and restore a matched pair.

The main is launched manually by `run_control.py`. The existing navigation service continues separately. The dashboard stays bound to localhost with its existing Host/Origin validation; do not expose it publicly.
