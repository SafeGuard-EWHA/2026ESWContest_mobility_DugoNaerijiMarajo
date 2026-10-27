"""
SafeGuard 블록 B - sensorStop 뒤 재시작이 되는지 확인하는 진단 스크립트 (3D People Tracking).

TI 소스(pcount3D_cli.c)상 멈춘 뒤 다시 시작하는 방법은 두 가지다:
    start0  : sensorStop -> "sensorStart 0"            (설정을 다시 보내지 않고 그대로 재시작)
    fullcfg : sensorStop -> 전체 cfg 다시 전송 -> sensorStart  (TI 사용자 가이드는 "새 설정 전에 장치 재시작 필요")
순서: USB를 뺐다 꽂은 직후 실행 → cfg 전송·시작 → 프레임 확인 → sensorStop → 프레임 멈춤 확인
      → 선택한 방법으로 재시작 → --wait초 동안 CLI 응답을 모두 기록 → 프레임 다시 오는지 확인.
CLI로 오가는 바이트는 전부 시각과 함께 --log 파일에 그대로 남긴다 (오류 문구·Exception 줄 확인용).

포트는 by-id 경로를 직접 줘야 한다 (ttyUSB 번호로 대체하지 않음):
    python3 -u hardware/mmwave/restart_check.py --mode start0 \
        --cli  /dev/serial/by-id/usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_01E86213-if00-port0 \
        --data /dev/serial/by-id/usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_01E86213-if01-port0 \
        --cfg hardware/mmwave/people_tracking/ODS_sedan_est.cfg --log ~/restart_start0.log
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import serial  # type: ignore

from mmwave_reader import CLI_BAUD, DATA_BAUD, FrameReader, read_cfg_lines


class CliLog:
    """CLI 포트 입출력을 시각과 함께 화면과 파일에 남긴다."""

    def __init__(self, cli: serial.Serial, path: Path) -> None:
        self.cli = cli
        self.f = open(path, "w", encoding="utf-8")
        self.t0 = time.monotonic()

    def note(self, text: str) -> None:
        line = f"[{time.monotonic() - self.t0:8.3f}s] {text}"
        print(line)
        self.f.write(line + "\n")
        self.f.flush()

    def send(self, cmd: str, wait_s: float) -> str:
        """명령 하나를 보내고 Done/Error/Ignored/Exception이 올 때까지(최대 wait_s) 받은 바이트를 그대로 기록한다."""
        self.cli.write((cmd + "\n").encode("ascii"))
        self.note(f">> {cmd}")
        deadline = time.monotonic() + wait_s
        reply = b""
        while time.monotonic() < deadline:
            chunk = self.cli.read(self.cli.in_waiting or 1)
            if chunk:
                reply += chunk
                self.note(f"<< {chunk!r}")
            if any(k in reply for k in (b"Done", b"Error", b"Ignored", b"Exception")):
                break
        if not reply:
            self.note(f"<< (응답 없음, {wait_s:.0f}초)")
        return reply.decode("ascii", errors="replace")


def check_frames(log: CliLog, data: serial.Serial, seconds: float, label: str) -> bool:
    """seconds 동안 데이터 포트를 듣고 리더 파서로 프레임을 해석한다.
    정상(깨지지 않은) 프레임이 1개 이상이고 그 프레임 번호가 계속 증가해야 True."""
    data.reset_input_buffer()
    reader = FrameReader()
    frames = []
    nbytes = 0
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        chunk = data.read(data.in_waiting or 1)
        nbytes += len(chunk)
        frames += reader.feed(chunk)
    good = [f["frame_number"] for f in frames if not f["bad"]]
    bad = len(frames) - len(good)
    increasing = all(b > a for a, b in zip(good, good[1:]))
    ok = bool(good) and increasing
    span = f"#{good[0]}~#{good[-1]}" if good else "-"
    log.note(f"{label} {seconds:.0f}초: {nbytes} B, 정상 프레임 {len(good)}개, 깨진 프레임 {bad}개, "
             f"프레임 번호 {span}, 계속 증가={increasing} → 수신 {'있음' if ok else '없음'}")
    return ok


def send_cfg(log: CliLog, lines: list[str], start_wait_s: float) -> bool:
    """cfg를 한 줄씩 보낸다. Done이 아닌 응답은 성공으로 치지 않고 따로 표시한다.
    Ignored는 처음 sensorStop("이미 멈춤")일 때만 정상으로 보고, 그 밖의 Ignored는 실패로 센다."""
    ok = True
    for i, line in enumerate(lines):
        wait = start_wait_s if line.startswith("sensorStart") else 1.0
        reply = log.send(line, wait)
        if "Done" in reply:
            continue
        if "Ignored" in reply:
            expected = i == 0 and line == "sensorStop"
            log.note(f"   [IGNORED] {line} ({'예상된 응답: 이미 멈춘 상태' if expected else '예상 밖'})")
            ok &= expected
            continue
        ok = False
        log.note(f"   [실패] {line}")
        if line.startswith("sensorStart"):
            break
    return ok


def run(args: argparse.Namespace) -> int:
    lines = read_cfg_lines(args.cfg)
    cli = serial.Serial(args.cli, CLI_BAUD, timeout=0.1)
    data = serial.Serial(args.data, DATA_BAUD, timeout=0.1)
    log = CliLog(cli, args.log)
    log.note(f"mode={args.mode} cfg={args.cfg.name} ({len(lines)}줄) wait={args.wait}s")
    try:
        log.note("--- 1. 처음 시작 (USB 재연결 직후여야 함)")
        first_ok = send_cfg(log, lines, args.wait)
        first_rx = check_frames(log, data, 5, "처음 시작 뒤")
        log.note(f"[요약] 처음 시작: 응답 정상={first_ok}, 데이터 수신={first_rx}")
        if not (first_ok and first_rx):
            log.note("처음 시작 실패 -> 재시작 시험 안 함. USB를 뺐다 꽂고 다시 실행")
            return 1

        log.note("--- 2. sensorStop")
        stop_reply = log.send("sensorStop", 3.0)
        stopped_rx = check_frames(log, data, 3, "sensorStop 뒤")
        log.note(f"[요약] sensorStop: 응답 Done={'Done' in stop_reply}, 데이터 중단={not stopped_rx}")

        log.note(f"--- 3. 재시작 ({args.mode})")
        if args.mode == "start0":
            reply = log.send("sensorStart 0", args.wait)
            started = "Done" in reply
            if "Done" not in reply:
                log.note("   [실패] sensorStart 0")
        else:
            started = send_cfg(log, lines, args.wait)
        restart_rx = check_frames(log, data, 5, "재시작 뒤")
        # 응답이 늦게 오는 경우를 보려고 남은 CLI 출력도 한 번 더 받는다
        late = cli.read(cli.in_waiting or 0)
        if late:
            log.note(f"<< (늦게 온 출력) {late!r}")
        log.note(f"[요약] 재시작({args.mode}): 응답 정상={started}, 데이터 수신 재개={restart_rx}")

        ok = started and restart_rx
        log.note(f"결과: {args.mode} 재시작 {'성공' if ok else '실패'}")
        return 0 if ok else 2
    finally:
        # 다음 사람을 위해 멈춰 두고, 실제로 데이터가 멈췄는지 확인한 뒤 포트를 닫는다.
        # 재시작이 실패했다면 다음 실행 전 USB 재연결 필요.
        try:
            log.note("--- 4. 종료")
            log.send("sensorStop", 3.0)
            end_rx = check_frames(log, data, 3, "종료 sensorStop 뒤")
            log.note(f"[요약] 종료: 레이더 정지={not end_rx}")
        except serial.SerialException as exc:
            log.note(f"종료 중 포트 오류: {exc}")
        cli.close()
        data.close()
        log.note(f"[요약] 포트 닫힘: CLI={not cli.is_open}, DATA={not data.is_open}")
        log.f.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="sensorStop 뒤 재시작 진단")
    p.add_argument("--mode", choices=["start0", "fullcfg"], required=True)
    p.add_argument("--cli", required=True, help="CLI 포트 by-id 경로 (if00)")
    p.add_argument("--data", required=True, help="데이터 포트 by-id 경로 (if01)")
    p.add_argument("--cfg", type=Path, required=True, help="처음 시작에 쓸 cfg")
    p.add_argument("--wait", type=float, default=15.0, help="sensorStart 응답 대기(초). 리더는 3초였음")
    p.add_argument("--log", type=Path, required=True, help="CLI 입출력 기록 파일")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(run(_parse_args()))
