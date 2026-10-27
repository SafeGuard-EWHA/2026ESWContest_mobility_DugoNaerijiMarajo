"""레이더(IWR6843ISK-ODS)에 지금 구워진 펌웨어 종류만 확인한다.

CLI 포트에 `version`과 `help`만 보낸다. cfg와 sensorStart는 절대 보내지 않는다.
`help`가 돌려주는 명령 목록으로 펌웨어를 구분한다.
  - vitalsign / VSRangeIdxCfg 있음            -> Vital Signs With People Tracking
  - trackingCfg / presenceBoundaryBox 있음    -> 3D People Tracking
  - guiMonitor 있음 (trackingCfg 없음)        -> SDK Out-of-Box 데모

사용 (레이더 USB를 뺐다 꽂은 직후, 다른 프로그램이 포트를 열고 있지 않을 때):
  Pi:      python3 check_radar_firmware.py
  Windows: python check_radar_firmware.py --cli COM6
"""

import argparse
import glob
import sys
import time

import serial

BOARD_SERIAL = "01E86213"


def find_cli_port() -> str:
    """CP2105 if00(Enhanced = CLI)만 고른다. 후보가 하나가 아니면 중단한다."""
    ports = sorted(glob.glob(f"/dev/serial/by-id/*CP2105*{BOARD_SERIAL}*if00*"))
    if not ports:
        ports = sorted(glob.glob("/dev/serial/by-id/*CP2105*if00*"))
    if len(ports) != 1:
        sys.exit(f"CLI 포트를 하나로 정할 수 없음: {ports or '없음'} -> --cli 로 직접 지정")
    return ports[0]


def ask(port: serial.Serial, cmd: str, wait_s: float) -> str:
    port.reset_input_buffer()
    port.write((cmd + "\n").encode())
    end = time.monotonic() + wait_s
    out = b""
    while time.monotonic() < end:
        out += port.read(4096)
    return out.decode(errors="replace")


def classify(help_text: str) -> str:
    if "vitalsign" in help_text or "VSRangeIdxCfg" in help_text:
        return "Vital Signs With People Tracking"
    if "trackingCfg" in help_text and "presenceBoundaryBox" in help_text:
        return "3D People Tracking"
    if "guiMonitor" in help_text:
        return "SDK Out-of-Box 데모"
    return "알 수 없음 (응답 없음 또는 목록에 아는 명령 없음)"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cli", help="CLI 포트 (Pi: by-id if00, Windows: COM6). 생략하면 Pi에서 자동 탐색")
    args = p.parse_args()

    cli = args.cli or find_cli_port()
    print(f"CLI 포트: {cli}")
    with serial.Serial(cli, 115200, timeout=0.2) as port:
        version = ask(port, "version", 1.5)
        help_text = ask(port, "help", 3.0)

    print("---- version 응답 ----")
    print(version.strip() or "(응답 없음)")
    print("---- help 응답 (앞부분) ----")
    print("\n".join(help_text.strip().splitlines()[:60]) or "(응답 없음)")
    print("----")
    print(f"판정: {classify(help_text)}")


if __name__ == "__main__":
    main()
