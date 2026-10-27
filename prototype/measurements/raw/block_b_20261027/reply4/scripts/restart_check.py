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

from mmwave_reader import CLI_BAUD, DATA_BAUD, MAGIC, read_cfg_lines


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


def count_frames(data: serial.Serial, seconds: float) -> tuple[int, int]:
    """seconds 동안 데이터 포트를 듣고 (매직워드 수, 받은 바이트 수)를 돌려준다."""
    data.reset_input_buffer()
    buf = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        buf += data.read(data.in_waiting or 1)
    return buf.count(MAGIC), len(buf)


def send_cfg(log: CliLog, lines: list[str], start_wait_s: float) -> bool:
    ok = True
    for line in lines:
        wait = start_wait_s if line.startswith("sensorStart") else 1.0
        reply = log.send(line, wait)
        if "Done" in reply or "Ignored" in reply:
            continue
        ok = False
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
        if not send_cfg(log, lines, args.wait):
            log.note("처음 시작 실패 -> USB를 뺐다 꽂고 다시 실행")
            return 1
        frames, nbytes = count_frames(data, 5)
        log.note(f"프레임 확인 5초: 매직워드 {frames}개, {nbytes} B")

        log.note("--- 2. sensorStop")
        log.send("sensorStop", 3.0)
        frames, nbytes = count_frames(data, 2)
        log.note(f"멈춤 확인 2초: 매직워드 {frames}개, {nbytes} B")

        log.note(f"--- 3. 재시작 ({args.mode})")
        if args.mode == "start0":
            reply = log.send("sensorStart 0", args.wait)
            started = "Done" in reply
        else:
            started = send_cfg(log, lines, args.wait)
        frames, nbytes = count_frames(data, 5)
        log.note(f"재시작 뒤 5초: 매직워드 {frames}개, {nbytes} B")
        # 응답이 늦게 오는 경우를 보려고 남은 CLI 출력도 한 번 더 받는다
        late = cli.read(cli.in_waiting or 0)
        if late:
            log.note(f"<< (늦게 온 출력) {late!r}")

        result = "성공" if started and frames > 0 else "실패"
        log.note(f"결과: {args.mode} 재시작 {result} (Done={started}, 프레임 {frames}개)")
        return 0 if result == "성공" else 2
    finally:
        # 다음 사람을 위해 멈춰 둔다. 재시작이 실패했다면 다음 실행 전 USB 재연결 필요.
        try:
            log.send("sensorStop", 3.0)
        except serial.SerialException:
            pass
        cli.close()
        data.close()
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
