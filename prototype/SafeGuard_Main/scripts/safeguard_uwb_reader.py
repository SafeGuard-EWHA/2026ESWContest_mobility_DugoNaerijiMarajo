#!/usr/bin/env python3
r"""SafeGuard C블록: PANS 거리 수신 및 메인 연결용 JSON 출력.

차량에 고정한 TAG 1대와 보호자가 휴대하는 Initiator ANCHOR 1대의 같은 PAN 설정,
차량 TAG의 nmt 설정,
업데이트 속도 후보 aurs 5 5 설정은 공식 가이드에 따라 먼저 완료하세요.
태그 USB UART의 PANS 쉘(115200, 8N1, 흐름 제어 없음)을 읽습니다.
--anchor-id에는 실제 lec 출력에서 확인한 앵커의 4자리 ID를 넣으세요.
아래 COM7, /dev/ttyACM0, A1B2는 예시이므로 실제 포트와 앵커 ID로 바꾸세요.

Windows PowerShell:
  py -m pip install pyserial
  py safeguard_uwb_reader.py --list
  py .\safeguard_uwb_reader.py --port COM7 --anchor-id A1B2 --start-lec
Raspberry Pi:
  sudo apt install python3-serial
  python3 safeguard_uwb_reader.py --list
  python3 safeguard_uwb_reader.py --port /dev/ttyACM0 --anchor-id A1B2 --start-lec
PC 독립 검사: py safeguard_uwb_reader.py --self-test

메인 연결용 출력 (현재 Windows 연결):
  py safeguard_uwb_reader.py --port COM3 --anchor-id 0CA7 --json
--json을 붙이면 stdout에는 JSON 한 줄씩만 출력하고 안내문은 stderr로 보냅니다.
메인 프로그램은 이 stdout을 입력 스트림으로 읽으면 됩니다.
peer_id는 거리 측정 상대인 보호자측 ANCHOR의 ID입니다. 차량측 ID가 아닙니다.
distance_m는 valid와 filter_ready가 모두 참일 때만 제공하며 나머지는 null입니다.
valid는 수신 신선도이고 usable_for_fsm는 신선한 7개 평균 확보 여부입니다.
이 값들은 정확도 보증이나 보호자 이탈 판정이 아닙니다. 최종 FSM은 메인 담당입니다.
소비자도 메시지 수신 중단을 자체 단조시계로 감시해야 합니다. 기본 timeout은 2초입니다.
프로세스 강제 종료/PC 정지 때에는 invalid 메시지도 전송되지 않을 수 있습니다.
rx_monotonic_s는 같은 호스트와 부팅 세션에서만 비교하세요. 다른 PC 간 비교는 금지합니다.
--json이 없어도 같은 메시지를 실행별 telemetry.jsonl에 추가 저장합니다.

기본 모드는 수신만 합니다. Tera Term에서 lec 스트림을 켠 뒤 포트를 닫으세요.
새 부팅 후 lec가 꺼져 있을 때만 위 실행 명령 끝에 --start-lec를 추가하세요.
이 옵션은 쉘 진입 후 lec를 한 번 보냅니다. lec는 토글 명령이므로,
이미 켜진 스트림에 사용하면 꺼질 수 있습니다. 리셋/설정 명령은 보내지 않습니다.

uwb_logs/<UTC 시각>/raw.jsonl: 모든 수신 줄과 파싱 결과.
telemetry.csv: raw_distance_m=실측 거리, filtered_distance_m=이동평균,
sample_count=현재 평균 표본 수, filter_ready=7개 확보 여부(기본값),
valid=구조상 정상인 마지막 거리 줄의 수신 신선도, age_ms=그 줄 수신 후 경과시간.
valid는 거리 정확도/가시선(LOS)을 보증하지 않습니다. lec에는 거리별 품질 보증이나
측정 순번이 없습니다. 펌웨어가 이전 거리를 반복 출력할 가능성을 배제하려면,
상대 보드 전원 분리 및 거리 변경 실험으로 출력과 timeout 동작을 확인해야 합니다.
유효 표본이 timeout 동안 없으면 valid=False, 거리 칸은 빈칸(결측),
평균 창도 비웁니다. 0m로 대체하지 않습니다. 새 표본부터 평균을 다시 쌓습니다.
기본 window=7, timeout=2초는 >=2Hz 설정을 전제로 한 초기 후보값입니다.
실측 빈도/누락을 확인하고 조정하세요. 이 코드는 이탈/보호 동작을 결정하지 않습니다.
USB 오류 시 종료합니다. 케이블/포트/PANS 설정 확인 후 직접 다시 실행하세요.
공식 가이드: https://forum.qorvo.com/uploads/short-url/jT6U3NQKKCCsDP0Zjh6QFMiZ3jW.pdf
"""

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.1.0"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def normalize_id(value):
    value = value.strip().upper()
    if value.startswith("0X"):
        value = value[2:]
    if not re.fullmatch(r"[0-9A-F]{4}", value):
        raise ValueError("anchor ID must be 4 hexadecimal digits observed in lec output")
    return value


def parse_line(line, target_id):
    """Return (status, target distance or None); never use a trailing POS value."""
    line = re.sub(r"^(?:\s*dwm>\s*)+", "", line).strip()
    if not line.startswith("DIST,"):
        return "ignored", None
    parts = [part.strip() for part in line.split(",")]
    try:
        if not re.fullmatch(r"\d+", parts[1]):
            raise ValueError("invalid count")
        count = int(parts[1])
        if not 0 <= count <= 32:
            raise ValueError("unsupported count")
        end = 2 + 6 * count
        # PANS lec: DIST,N,(ANi,id,x,y,z,range)*N[,POS,x,y,z,quality].
        # POS is optional; its coordinates and quality never become distance.
        if len(parts) != end:
            if len(parts) != end + 5 or parts[end] != "POS":
                raise ValueError("wrong number of fields")
        found, labels, ids = None, set(), set()
        for offset in range(2, end, 6):
            label, ident, x, y, z, distance = parts[offset:offset + 6]
            ident = normalize_id(ident)
            if not re.fullmatch(r"AN\d+", label) or label in labels or ident in ids:
                raise ValueError("invalid/duplicate anchor")
            labels.add(label)
            ids.add(ident)
            values = [float(item) for item in (x, y, z, distance)]
            if not all(math.isfinite(item) for item in values) or values[3] < 0:
                raise ValueError("invalid numeric value")
            if ident == target_id:
                found = values[3]
        return ("ok", found) if found is not None else ("no_target", None)
    except (ValueError, IndexError):
        return "malformed", None


class DistanceState:
    def __init__(self, window, timeout, anchor_id="", serial_port=""):
        self.window, self.timeout = window, timeout
        self.anchor_id, self.serial_port = anchor_id, serial_port
        self.samples = deque(maxlen=window)
        self.last_time = self.raw = None
        self.valid, self.status, self.seq = False, "waiting", 0

    def accept(self, distance, now):
        self.expire(now)  # A resumed stream must not reuse an old averaging window.
        self.samples.append(distance)
        self.last_time, self.raw = now, distance
        self.valid, self.status = True, "fresh"

    def invalidate(self, status):
        self.samples.clear()
        self.raw, self.valid, self.status = None, False, status

    def expire(self, now):
        if self.valid and now - self.last_time >= self.timeout:
            self.invalidate("stale")
            return True
        return False

    def snapshot(self, now):
        self.seq += 1
        return dict(seq=self.seq, utc=utc_now(), monotonic_s=round(now, 6),
                    anchor_id=self.anchor_id, serial_port=self.serial_port,
                    rx_monotonic_s=self.last_time,
                    raw_distance_m=self.raw if self.valid else None,
                    filtered_distance_m=(sum(self.samples) / len(self.samples)
                                         if self.valid and self.samples else None),
                    sample_count=len(self.samples),
                    filter_ready=self.valid and len(self.samples) == self.window,
                    valid=self.valid,
                    age_ms=(round(1000 * (now - self.last_time), 1)
                            if self.last_time is not None else None), status=self.status)


def main_message(row, *, window, timeout_s, run_id):
    """Create the C -> main contract; never turn an unavailable range into zero."""
    usable = bool(row["valid"] and row["filter_ready"])
    return dict(type="uwb", schema_version=1, version=VERSION, source="REAL_UWB",
                run_id=run_id, seq=row["seq"], peer_id=row["anchor_id"],
                serial_port=row["serial_port"], utc=row["utc"],
                published_monotonic_s=row["monotonic_s"],
                rx_monotonic_s=row["rx_monotonic_s"],
                raw_distance_m=row["raw_distance_m"],
                filtered_distance_m=row["filtered_distance_m"],
                distance_m=row["filtered_distance_m"] if usable else None,
                sample_count=row["sample_count"], window=window,
                filter_ready=row["filter_ready"], valid=row["valid"],
                usable_for_fsm=usable, age_ms=row["age_ms"],
                timeout_s=timeout_s, status=row["status"])


def self_test():
    target = "1A2B"
    line = "DIST,2,AN0,4321,0,0,0,8.2,AN1,0x1a2b,1,2,3,4.5,POS,90,80,70,99"
    assert parse_line("dwm> " + line, target) == ("ok", 4.5)
    assert parse_line("DIST,1,AN0,1A2B,0,0,0,0", target) == ("ok", 0.0)
    assert parse_line("DIST,1,AN0,1111,0,0,0,2.0", target)[0] == "no_target"
    for bad in (line + ",EXTRA", line.replace("DIST,2", "DIST,3"),
                line.replace("4.5", "nan"), line.replace("4.5", "inf"),
                line.replace("4.5", "-1"), line.replace("4321", "1A2B"),
                line.replace("AN1", "AN0"), "DIST,x", "DIST,1,AN0,1A2B"):
        assert parse_line(bad, target)[0] == "malformed", bad
    assert parse_line("PANS shell", target)[0] == "ignored"
    state = DistanceState(3, 2.0)
    assert state.snapshot(0)["raw_distance_m"] is None
    for now, distance in ((1.0, 1), (1.1, 2), (1.2, 3)):
        state.accept(distance, now)
    row = state.snapshot(1.3)
    assert row["filter_ready"] and row["filtered_distance_m"] == 2
    assert not state.expire(3.19)
    assert state.expire(3.21)
    row = state.snapshot(3.21)
    assert not row["valid"] and row["raw_distance_m"] is None
    assert row["filtered_distance_m"] is None and row["sample_count"] == 0
    state.accept(9, 4)
    assert state.snapshot(4)["filtered_distance_m"] == 9
    assert not state.snapshot(4)["filter_ready"]
    state.accept(7, 8)  # Stale gap without an intervening timeout callback.
    assert list(state.samples) == [7]
    message = main_message(state.snapshot(8), window=3, timeout_s=2, run_id="test")
    assert message["valid"] and not message["usable_for_fsm"]
    assert message["distance_m"] is None
    state.accept(8, 8.1)
    state.accept(9, 8.2)
    message = main_message(state.snapshot(8.2), window=3, timeout_s=2, run_id="test")
    assert message["usable_for_fsm"] and message["distance_m"] == 8
    assert state.expire(10.3)
    message = main_message(state.snapshot(10.3), window=3, timeout_s=2, run_id="test")
    assert not message["valid"] and message["distance_m"] is None
    assert message["raw_distance_m"] is None and message["sample_count"] == 0
    print("PASS: parser, multiple anchors/POS, malformed data, freshness, window reset.")
    print("PASS: main JSON contract, warm-up gating, missing distance stays null.")


def run_reader(args, serial_module):
    folder = Path(args.log_dir) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    state = DistanceState(args.window, args.timeout, args.anchor_id, args.port)
    metadata = dict(version=VERSION, created_utc=utc_now(), serial_port=args.port,
                    anchor_id=args.anchor_id, window=args.window, timeout_s=args.timeout,
                    start_lec=args.start_lec, hardware_tested=False,
                    json_stdout=args.json,
                    validation_note="v1.0.1 UART/MA7/CSV verified on Windows; new JSON output pending hardware check",
                    settings_status="initial candidates; verify on actual hardware")
    (folder / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    serial_port = None
    info_stream = sys.stderr if args.json else sys.stdout
    with (folder / "raw.jsonl").open("w", encoding="utf-8") as raw_log, \
            (folder / "telemetry.csv").open("w", newline="", encoding="utf-8") as telemetry, \
            (folder / "telemetry.jsonl").open("w", encoding="utf-8") as main_log:
        writer = csv.DictWriter(telemetry, fieldnames=list(state.snapshot(time.monotonic())))
        state.seq = 0
        writer.writeheader()

        def emit(send_stdout=True):
            row = state.snapshot(time.monotonic())
            writer.writerow(row)
            telemetry.flush()
            message = main_message(row, window=args.window, timeout_s=args.timeout,
                                   run_id=folder.name)
            encoded = json.dumps(message, ensure_ascii=False, allow_nan=False)
            main_log.write(encoded + "\n")
            main_log.flush()
            if args.json and send_stdout:
                print(encoded, flush=True)

        def log_line(data, now, forced_status=None):
            line = data.decode("ascii", errors="replace")
            status, distance = parse_line(line, args.anchor_id)
            if forced_status or b"\x00" in data or "\ufffd" in line:
                status, distance = forced_status or "malformed_encoding", None
            raw_log.write(json.dumps(dict(utc=utc_now(), monotonic_s=now,
                                          line=line, parse_status=status), ensure_ascii=False) + "\n")
            raw_log.flush()
            if status == "ok":
                state.accept(distance, now)
                emit()

        emit()
        try:
            serial_port = serial_module.Serial(port=None, baudrate=115200,
                bytesize=serial_module.EIGHTBITS, parity=serial_module.PARITY_NONE,
                stopbits=serial_module.STOPBITS_ONE, timeout=0.1, write_timeout=1,
                xonxoff=False, rtscts=False, dsrdtr=False, exclusive=True)
            serial_port.dtr = False
            serial_port.rts = False
            serial_port.port = args.port
            serial_port.open()
            print(f"Logs: {folder.resolve()}", file=info_stream)
            print("Listening. Close Tera Term. Ctrl+C stops safely.", file=info_stream)
            startup = None
            if getattr(args, "recover_stream", False):
                from uwb_startup import UwbStartup
                startup = UwbStartup(time.monotonic())
                print("Guarded startup: observe first; lec only after shell prompt, once.", file=info_stream)
            elif args.start_lec:
                time.sleep(2.0)  # Let the freshly powered board finish booting.
                serial_port.write(b"\r")
                time.sleep(0.1)
                serial_port.write(b"\r\r")
                time.sleep(1.0)  # Let the shell finish its banner before the command.
                # PANS shell expects human-paced text (LEAPS recommends ~20 ms/char).
                for byte in b"lec\r":
                    serial_port.write(bytes([byte]))
                    serial_port.flush()
                    time.sleep(0.025)
                print("Sent lec ONCE; use this option only when the stream was off.", file=info_stream)
            else:
                print("Passive mode: lec must already be enabled (or use --start-lec after fresh boot).", file=info_stream)
            buffer, dropping = bytearray(), False
            last_check = last_display = time.monotonic()
            while True:
                data = serial_port.read(256)
                now = time.monotonic()
                if startup is not None:
                    startup.feed(data)
                    command = startup.action(now)
                    if command is not None:
                        for ch in command:
                            serial_port.write(bytes([ch]))
                            serial_port.flush()
                            time.sleep(0.05)
                        print("UWB startup sent: " + repr(command), file=info_stream, flush=True)
                for byte in data:
                    if byte in (10, 13):
                        if buffer or dropping:
                            log_line(bytes(buffer), now, "line_too_long" if dropping else None)
                        buffer.clear()
                        dropping = False
                    elif not dropping:
                        buffer.append(byte)
                        if len(buffer) > 8192:
                            dropping = True
                if now - last_check >= 0.2:
                    if state.expire(now):
                        emit()
                    last_check = now
                if not args.json and now - last_display >= 1:
                    mean = sum(state.samples) / len(state.samples) if state.samples else None
                    distance_text = f"{mean:.3f} m" if mean is not None else "missing"
                    print(f"{state.status}: mean={distance_text}, samples={len(state.samples)}/{args.window}")
                    last_display = now
        except BrokenPipeError:
            state.invalidate("consumer_closed")
            emit(send_stdout=False)
            print("Main input pipe closed; logs saved.", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            state.invalidate("stopped")
            emit()
            print("Stopped; telemetry invalidated and logs saved.", file=info_stream)
        except (serial_module.SerialException, OSError) as exc:
            state.invalidate("usb_error")
            emit()
            print(f"Serial error: {exc}", file=sys.stderr)
            print("Check USB cable, port, Tera Term closure and PANS configuration; rerun manually.", file=sys.stderr)
            return 1
        finally:
            if serial_port is not None:
                serial_port.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list serial ports")
    parser.add_argument("--self-test", action="store_true", help="software-only checks; no hardware used")
    parser.add_argument("--port")
    parser.add_argument("--anchor-id", type=normalize_id)
    parser.add_argument("--window", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--log-dir", default="uwb_logs")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start-lec", action="store_true")
    group.add_argument("--recover-stream", action="store_true")
    parser.add_argument("--json", action="store_true", help="main integration: JSON lines only on stdout")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.list and (not args.port or not args.anchor_id):
        parser.error("reader requires --port and --anchor-id (actual observed anchor ID)")
    if args.window < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("window must be >=1; timeout must be finite and >0")
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        parser.error("Install pyserial: py -m pip install pyserial (Pi: sudo apt install python3-serial)")
    if args.list:
        ports = list(list_ports.comports())
        for port in ports:
            print(f"{port.device}: {port.description}; serial={port.serial_number}; hwid={port.hwid}")
        if not ports:
            print("No serial ports found. Check the USB data cable and driver.")
        return 0
    return run_reader(args, serial)


if __name__ == "__main__":
    raise SystemExit(main())
