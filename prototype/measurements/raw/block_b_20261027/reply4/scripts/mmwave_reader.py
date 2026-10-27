"""
SafeGuard 블록 B3 - IWR6843ISK-ODS mmWave 수신 확인 스크립트.

S1이 Functional 모드(1 OFF, 2 OFF, 3 ON, 4 ON, 5 OFF)일 때 사용한다. 두 펌웨어를 모두 읽는다:
    - mmWave SDK 3.6 Out-of-Box 데모 (xwr68xx_mmw_demo.bin): 점 구름 TLV 1
    - Radar Toolbox 3D People Tracking (3D_people_track_6843_demo.bin):
      압축 점 구름 TLV 1020, 추적 대상 TLV 1010, 재실 여부 TLV 1021
    - Radar Toolbox Vital Signs With People Tracking (vital_signs_tracking_6843ISK_demo.bin):
      위 추적 TLV + 호흡·심박 TLV 1040
      (형식은 Radar Toolbox 4.00 Industrial Visualizer의 parseFrame.py / parseTLVs.py 기준)

1. CLI 포트(115200)로 .cfg 명령을 한 줄씩 보낸다 (sensorStop ... sensorStart).
2. 데이터 포트(921600)에서 TLV 프레임을 받아 매직워드로 자르고 파싱한다.
3. 1초마다 프레임/초, 마지막 프레임 점 개수, 가장 가까운 점 거리(+ 추적 대상 수)를 출력한다.

src/ 시뮬레이터와 무관한 하드웨어 전용 스크립트다 (pyserial만 필요).
보드 USB 칩이 CP2105라서 포트가 2개 생긴다:
    - Enhanced 포트 = CLI  (Pi: /dev/ttyUSB0 또는 by-id ...-if00, Windows: COM6)
    - Standard 포트 = 데이터 (Pi: /dev/ttyUSB1 또는 by-id ...-if01, Windows: COM7)

사용법:
    python hardware/mmwave/mmwave_reader.py                       # Pi: 포트 자동 탐색
    python hardware/mmwave/mmwave_reader.py --cli COM6 --data COM7 # 노트북
    python hardware/mmwave/mmwave_reader.py --duration 60 --csv mmwave_log.csv

mmWave Demo Visualizer가 열려 있으면 포트를 잡고 있어서 실패한다. 먼저 닫을 것.
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import struct
import sys
import time
from pathlib import Path

try:
    import serial  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError("pyserial이 필요합니다: python -m pip install pyserial") from exc

DEFAULT_CFG = Path(__file__).resolve().parent / "xwr68xx_ods_oob_20261023.cfg"

CLI_BAUD = 115200
DATA_BAUD = 921600

# 프레임 헤더: 매직워드 8바이트 + uint32 8개 (SDK 3.x)
MAGIC = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
HEADER_FMT = "<8I"  # version, totalPacketLen, platform, frameNumber,
                    # timeCpuCycles, numDetectedObj, numTLVs, subFrameNumber
HEADER_LEN = len(MAGIC) + struct.calcsize(HEADER_FMT)  # 40
TLV_HEADER_FMT = "<2I"  # type, length(payload 바이트, TLV 헤더 제외)
TLV_DETECTED_POINTS = 1  # Out-of-Box: float32 x, y, z, doppler (16바이트/점)
TLV_TRACKS = 1010  # People Tracking: uint32 tid + float32 27개 (112바이트/대상)
TLV_COMPRESSED_POINTS = 1020  # People Tracking: 단위 float32 5개 + 점마다 int8 el, az, int16 dop, uint16 rng, snr
TLV_PRESENCE = 1021  # People Tracking: uint32 (1 = 재실 영역 안에 누군가 있음)
TLV_VITALS = 1040  # Vital Signs: uint16 id, rangeBin + float32 breathDeviation, heartRate, breathRate,
                   # 심박 파형 15개, 호흡 파형 15개 (TI parseTLVs.py parseVitalSignsTLV, 136바이트)
TRACK_FMT = "<I27f"
VITALS_FMT = "<2H33f"
# 세 펌웨어가 내보내는 TLV 번호 (Out-of-Box 1~10, People Tracking 1010~1021, Vital Signs 1040)
KNOWN_TLVS = set(range(1, 11)) | {1010, 1011, 1012, 1020, 1021, TLV_VITALS}
POINT_UNIT_FMT = "<5f"  # elevation, azimuth, doppler, range, snr 단위
POINT_FMT = "<2bh2H"
MAX_PACKET_LEN = 64 * 1024  # 이보다 크면 깨진 헤더로 보고 버린다


def find_ports() -> tuple[str | None, str | None]:
    """Pi(리눅스)에서 CP2105 by-id 경로로 CLI/데이터 포트를 찾는다."""
    cli = sorted(glob.glob("/dev/serial/by-id/*CP2105*if00*"))
    data = sorted(glob.glob("/dev/serial/by-id/*CP2105*if01*"))
    if cli and data:
        return cli[0], data[0]
    if Path("/dev/ttyUSB0").exists() and Path("/dev/ttyUSB1").exists():
        return "/dev/ttyUSB0", "/dev/ttyUSB1"
    return None, None


def read_cfg_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("%"):
            lines.append(line)
    return lines


def send_cfg(cli: serial.Serial, lines: list[str]) -> bool:
    """명령을 한 줄씩 보내고 'Done'/'Error' 응답을 확인한다."""
    cli.reset_input_buffer()
    ok = True
    for line in lines:
        cli.write((line + "\n").encode("ascii"))
        timeout_s = 3.0 if line.startswith("sensorStart") else 1.0
        deadline = time.monotonic() + timeout_s
        reply = b""
        while time.monotonic() < deadline:
            reply += cli.read(cli.in_waiting or 1)
            if b"Done" in reply or b"Error" in reply or b"Ignored" in reply:
                break
        text = reply.decode("ascii", errors="replace")
        if "Done" in text or "Ignored" in text:
            continue
        # 센서가 이미 멈춰 있을 때 sensorStop이 에러를 내는 건 무시해도 된다
        if line == "sensorStop":
            continue
        ok = False
        detail = " ".join(text.split()) or "(응답 없음)"
        print(f"  [CFG 실패] {line}\n    -> {detail}")
    return ok


def _parse_compressed_points(payload: bytes) -> list[tuple[float, float, float, float]]:
    """TLV 1020: 압축된 구면 좌표 점을 (x, y, z, doppler)로 바꾼다 (TI parseTLVs.py와 같은 식)."""
    unit_size = struct.calcsize(POINT_UNIT_FMT)
    point_size = struct.calcsize(POINT_FMT)
    if len(payload) < unit_size:
        return []
    el_u, az_u, dop_u, rng_u, _snr_u = struct.unpack_from(POINT_UNIT_FMT, payload, 0)
    points = []
    for off in range(unit_size, len(payload) - point_size + 1, point_size):
        el, az, dop, rng, _snr = struct.unpack_from(POINT_FMT, payload, off)
        r, a, e = rng * rng_u, az * az_u, el * el_u
        points.append((r * math.cos(e) * math.sin(a), r * math.cos(e) * math.cos(a),
                       r * math.sin(e), dop * dop_u))
    return points


def parse_frame(packet: bytes) -> dict:
    """매직워드로 시작하는 완전한 패킷 하나를 파싱한다.

    TLV가 패킷 밖으로 넘어가면(전송 중 깨진 프레임) 거기서 멈추고 bad=True로 표시한다.
    tracks/presence는 People Tracking 펌웨어일 때만 값이 생긴다 (Out-of-Box면 None).
    """
    (_version, total_len, platform, frame_number, _cycles,
     num_obj, num_tlvs, _subframe) = struct.unpack_from(HEADER_FMT, packet, len(MAGIC))
    points = []
    tracks = None
    presence = None
    vitals = None
    bad = False
    track_size = struct.calcsize(TRACK_FMT)
    offset = HEADER_LEN
    for _ in range(num_tlvs):
        if offset + 8 > len(packet):
            bad = True
            break
        tlv_type, tlv_len = struct.unpack_from(TLV_HEADER_FMT, packet, offset)
        offset += 8
        if tlv_type not in KNOWN_TLVS or offset + tlv_len > len(packet):
            # TI Visualizer도 모르는 TLV 번호가 나오면 그 프레임을 버린다 ("Invalid TLV type ... Dropping frame")
            bad = True
            break
        payload = packet[offset:offset + tlv_len]
        if tlv_type == TLV_DETECTED_POINTS:
            for i in range(min(num_obj, tlv_len // 16)):
                points.append(struct.unpack_from("<4f", payload, i * 16))
        elif tlv_type == TLV_COMPRESSED_POINTS:
            points = _parse_compressed_points(payload)
        elif tlv_type == TLV_TRACKS:
            tracks = []
            for i in range(tlv_len // track_size):
                tid, x, y, z = struct.unpack_from("<I3f", payload, i * track_size)
                tracks.append((tid, x, y, z))
        elif tlv_type == TLV_PRESENCE and tlv_len >= 4:
            presence = struct.unpack_from("<I", payload, 0)[0]
        elif tlv_type == TLV_VITALS and tlv_len >= struct.calcsize(VITALS_FMT):
            v = struct.unpack_from(VITALS_FMT, payload, 0)
            vitals = {"id": v[0], "range_bin": v[1], "breath_dev": v[2],
                      "heart_rate": v[3], "breath_rate": v[4]}
        offset += tlv_len
    # TI parseFrame.py와 같은 무결성 검사: 장치는 패킷을 32바이트 배수로 채워 보낸다.
    # TLV 길이 합이 헤더의 totalPacketLen과 안 맞으면 전송 중 바이트가 빠진 프레임이다.
    # 단 Vital Signs 데모는 채우기 없이 딱 맞게 보낸다 (TI도 DEMO_VITALS는 이 검사를 건너뜀).
    # 10/24 Pi 시험: 호흡 TLV가 없는 프레임도 채우기가 없어서, "딱 맞음"도 정상으로 인정한다.
    if not bad and total_len not in (offset, 32 * math.ceil(offset / 32)):
        bad = True
    if presence not in (None, 0, 1):
        bad = True
    if bad:
        # 깨진 프레임의 값은 믿을 수 없으니 기록하지 않는다 (프레임 번호만 남김)
        points, tracks, presence, vitals = [], None, None, None
    return {"frame_number": frame_number, "platform": platform, "num_obj": num_obj,
            "points": points, "tracks": tracks, "presence": presence, "vitals": vitals, "bad": bad}


class FrameReader:
    """데이터 포트 바이트 흐름을 쌓아 두고 완전한 프레임만 꺼낸다."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        self.buf += data
        frames = []
        while True:
            start = self.buf.find(MAGIC)
            if start < 0:
                # 매직워드가 경계에 걸쳐 있을 수 있으니 끝 7바이트는 남긴다
                del self.buf[:-(len(MAGIC) - 1)]
                return frames
            if start > 0:
                del self.buf[:start]
            if len(self.buf) < HEADER_LEN:
                return frames
            total_len = struct.unpack_from("<I", self.buf, len(MAGIC) + 4)[0]
            if total_len < HEADER_LEN or total_len > MAX_PACKET_LEN:
                del self.buf[:len(MAGIC)]  # 깨진 헤더: 다음 매직워드를 찾는다
                continue
            if len(self.buf) < total_len:
                return frames
            frames.append(parse_frame(bytes(self.buf[:total_len])))
            del self.buf[:total_len]


def nearest_range_m(points: list[tuple[float, float, float, float]]) -> float | None:
    if not points:
        return None
    return min(math.sqrt(x * x + y * y + z * z) for x, y, z, _v in points)


def run(args: argparse.Namespace) -> int:
    cli_port, data_port = args.cli, args.data
    if not (cli_port and data_port):
        cli_port, data_port = find_ports()
    if not (cli_port and data_port):
        print("mmWave 포트를 못 찾았습니다. 보드 USB 연결을 확인하거나 --cli/--data로 지정하세요.")
        return 1
    print(f"CLI  포트: {cli_port} ({CLI_BAUD})")
    print(f"데이터 포트: {data_port} ({DATA_BAUD})")

    try:
        cli = serial.Serial(cli_port, CLI_BAUD, timeout=0.1)
        data = serial.Serial(data_port, DATA_BAUD, timeout=0.1)
        # Windows 드라이버 수신 버퍼 기본값(4 KB)은 People Tracking 프레임 몇 개면 넘친다.
        # 10/23 노트북 15분 시험에서 프레임 약 7%가 깨지거나 빠졌다. (리눅스에는 이 함수가 없음)
        if hasattr(data, "set_buffer_size"):
            data.set_buffer_size(rx_size=1 << 20)
    except serial.SerialException as exc:
        print(f"포트를 열 수 없습니다: {exc}")
        print("mmWave Demo Visualizer나 UniFlash가 켜져 있으면 닫고 다시 실행하세요.")
        return 1

    csv_file = None
    writer = None
    raw_file = None
    raw_idx_file = None
    raw_idx = None
    raw_offset = 0
    try:
        if not args.no_cfg:
            lines = read_cfg_lines(args.cfg)
            print(f"설정 전송: {args.cfg.name} ({len(lines)}줄)")
            if not send_cfg(cli, lines):
                print("설정 전송 실패. S1이 Functional 모드인지, 보드를 다시 꽂았는지 확인하세요.")
                return 1
            print("설정 완료 -> sensorStart\n")
        data.reset_input_buffer()

        if args.csv:
            csv_file = open(args.csv, "w", newline="", encoding="utf-8")
            writer = csv.writer(csv_file)
            writer.writerow(["wall_time", "frame_number", "num_points", "nearest_range_m",
                             "num_tracks", "presence", "bad_frame",
                             "breath_rate", "heart_rate", "breath_dev", "range_bin"])

        if args.raw:
            # 데이터 포트에서 받은 바이트를 해석 전 그대로 저장한다 (메인 쪽 파서 대조용).
            # .idx.csv에는 읽은 묶음마다 수신 시각과 raw 파일 안의 위치를 남긴다.
            raw_file = open(args.raw, "wb")
            raw_idx_file = open(args.raw.with_name(args.raw.name + ".idx.csv"), "w",
                                newline="", encoding="utf-8")
            raw_idx = csv.writer(raw_idx_file)
            raw_idx.writerow(["monotonic_s", "wall_time", "byte_offset", "num_bytes"])

        reader = FrameReader()
        t_start = time.monotonic()
        t_report = t_start
        frames_in_window = 0
        total_frames = 0
        dropped = 0
        bad_frames = 0
        tracker_fw = False  # People Tracking 펌웨어 TLV를 한 번이라도 봤는지
        last_frame_no = None
        last = None
        last_vitals = None  # Vital Signs: 마지막으로 받은 호흡·심박 값

        while args.duration <= 0 or time.monotonic() - t_start < args.duration:
            chunk = data.read(data.in_waiting or 1)
            if raw_file and chunk:
                raw_file.write(chunk)
                raw_idx.writerow([f"{time.monotonic():.6f}", f"{time.time():.3f}",
                                  raw_offset, len(chunk)])
                raw_offset += len(chunk)
            for frame in reader.feed(chunk):
                total_frames += 1
                frames_in_window += 1
                if last_frame_no is not None and frame["frame_number"] > last_frame_no + 1:
                    dropped += frame["frame_number"] - last_frame_no - 1
                last_frame_no = frame["frame_number"]
                last = frame
                bad_frames += frame["bad"]
                # 추적 대상이 0명인 프레임은 TLV 1010이 아예 없을 수 있어서, 펌웨어 종류로 판단한다
                if frame["tracks"] is not None or frame["presence"] is not None:
                    tracker_fw = True
                vit = frame["vitals"]
                if vit is not None:
                    tracker_fw = True  # Vital Signs 펌웨어도 사람 추적을 함께 한다
                    last_vitals = vit
                if writer:
                    near = nearest_range_m(frame["points"])
                    writer.writerow([f"{time.time():.3f}", frame["frame_number"],
                                     len(frame["points"]), "" if near is None else f"{near:.3f}",
                                     len(frame["tracks"] or []) if tracker_fw else "",
                                     "" if frame["presence"] is None else frame["presence"],
                                     int(frame["bad"]),
                                     "" if vit is None else f"{vit['breath_rate']:.1f}",
                                     "" if vit is None else f"{vit['heart_rate']:.1f}",
                                     "" if vit is None else f"{vit['breath_dev']:.4f}",
                                     "" if vit is None else vit["range_bin"]])
                if args.show_points and frame["tracks"]:
                    for tid, x, y, z in frame["tracks"]:
                        print(f"    추적 #{tid}: x={x:+.2f} y={y:+.2f} z={z:+.2f} m")
                if args.show_points:
                    for x, y, z, v in frame["points"]:
                        print(f"    x={x:+.2f} y={y:+.2f} z={z:+.2f} m  v={v:+.2f} m/s")

            now = time.monotonic()
            if now - t_report >= 1.0:
                fps = frames_in_window / (now - t_report)
                if last is None:
                    print(f"[{now - t_start:5.1f}s] 프레임 없음 - 데이터 포트/설정 확인")
                else:
                    near = nearest_range_m(last["points"])
                    near_txt = "-" if near is None else f"{near:.2f} m"
                    track_txt = f"추적 {len(last['tracks'] or [])}명 | " if tracker_fw else ""
                    vit_txt = ""
                    if last_vitals is not None:
                        # TI Visualizer와 같은 표시 규칙: 흔들림 0 = 값 없음, 0.02 미만 = 숨 참음
                        dev = last_vitals["breath_dev"]
                        breath = ("-" if dev == 0 else "숨참음" if dev < 0.02
                                  else f"{last_vitals['breath_rate']:.1f}/분")
                        vit_txt = (f"호흡 {breath} | 심박 {last_vitals['heart_rate']:.1f} | "
                                   f"거리칸 {last_vitals['range_bin']} | ")
                    print(f"[{now - t_start:5.1f}s] {fps:4.1f} 프레임/초 | "
                          f"프레임 #{last['frame_number']} | {track_txt}{vit_txt}점 {len(last['points'])}개 | "
                          f"가장 가까운 점 {near_txt} | 누락 {dropped} | 깨짐 {bad_frames}")
                frames_in_window = 0
                t_report = now
    except serial.SerialException as exc:
        # USB가 빠지면 여기로 온다 (상태기계의 FAIL_SAFE 입력 후보)
        print(f"\nmmWave 포트 끊김: {exc}")
        return 2
    except KeyboardInterrupt:
        print("\n중단 (Ctrl+C)")
    finally:
        try:
            cli.write(b"sensorStop\n")
        except serial.SerialException:
            pass
        cli.close()
        data.close()
        if csv_file:
            csv_file.close()
        if raw_file:
            raw_file.close()
            raw_idx_file.close()

    print(f"총 {total_frames} 프레임, 누락 {dropped}, 깨짐 {bad_frames}")
    if args.raw:
        print(f"원본 바이트 {raw_offset} B 저장: {args.raw}")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IWR6843ISK-ODS mmWave 수신 확인")
    p.add_argument("--cli", help="CLI 포트 (예: /dev/ttyUSB0, COM6). 생략하면 자동 탐색")
    p.add_argument("--data", help="데이터 포트 (예: /dev/ttyUSB1, COM7). 생략하면 자동 탐색")
    p.add_argument("--cfg", type=Path, default=DEFAULT_CFG, help="보낼 .cfg 파일")
    p.add_argument("--no-cfg", action="store_true", help="설정을 보내지 않고 수신만 (이미 동작 중일 때)")
    p.add_argument("--duration", type=float, default=0, help="실행 시간(초), 0이면 Ctrl+C까지")
    p.add_argument("--csv", type=Path, help="프레임별 기록 CSV 경로")
    p.add_argument("--raw", type=Path, help="데이터 포트 원본 바이트 저장 경로 (예: raw.bin, 옆에 .idx.csv 생김)")
    p.add_argument("--show-points", action="store_true", help="추적 대상과 점 좌표를 모두 출력")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(run(_parse_args()))
