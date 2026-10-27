"""
SafeGuard 블록 B - Pi 5 + Camera Module 3 프레임 차분 움직임 검출.

picamera2 공식 예제(capture_motion)와 같은 방식: 저해상도 YUV420 스트림의 밝기(Y) 채널만
가져와서 이전 프레임과 비교한다. OpenCV 없이 numpy만 쓴다.

판단 규칙 (1초마다 출력):
    - 밝기 차이가 --pixel-thresh 보다 큰 픽셀의 비율 = 변화 비율
    - 변화 비율 > --ratio-thresh 이면 그 프레임은 "움직임"
    - 마지막 움직임 뒤 --hold 초 동안은 움직임 상태를 유지 (PIR처럼 깜빡이는 걸 막음)
    - 변화 비율 > --light-thresh 이면 화면 전체가 바뀐 것(조명 변화, 카메라 흔들림)으로 보고 무시하고,
      그 뒤 --light-settle 초 동안 판단을 쉼 (자동 노출 안정)
    - --min-frames 프레임 연속으로 바뀌어야 움직임으로 인정 (한 프레임짜리 깜빡임 무시)
    - --roi 로 화면 일부(뒷좌석)만 볼 수 있다. 창문 쪽 밖 사람을 빼는 용도

사용법 (Pi에서):
    python3 hardware/camera/camera_motion.py                    # 1초마다 상태 출력
    python3 hardware/camera/camera_motion.py --duration 120 --csv ~/cam.csv --snap-dir ~/cam_snaps
    python3 hardware/camera/camera_motion.py --roi 0.2 0.3 0.8 1.0   # 가로 20~80%, 세로 30~100%만
    python hardware/camera/camera_motion.py --replay cam.csv          # 녹화 재생 (노트북에서도 됨)

src/ 시뮬레이터와 무관한 하드웨어 전용 스크립트다.
picamera2는 Raspberry Pi OS에 기본 포함 (없으면: sudo apt install -y python3-picamera2).
rpicam-hello 등 다른 카메라 프로그램이 켜져 있으면 카메라를 열 수 없다.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

LORES_SIZE = (320, 240)  # 판단용 저해상도 (가로, 세로)


def motion_ratio(prev: np.ndarray, cur: np.ndarray, pixel_thresh: int,
                 roi: tuple[float, float, float, float] | None = None) -> float:
    """두 흑백 프레임에서 밝기가 pixel_thresh 넘게 바뀐 픽셀의 비율(0~1)."""
    if roi is not None:
        h, w = cur.shape
        x0, y0, x1, y1 = roi
        rows = slice(int(y0 * h), int(y1 * h))
        cols = slice(int(x0 * w), int(x1 * w))
        prev, cur = prev[rows, cols], cur[rows, cols]
    diff = np.abs(cur.astype(np.int16) - prev.astype(np.int16))
    return float(np.count_nonzero(diff > pixel_thresh)) / diff.size


class MotionState:
    """프레임마다 변화 비율을 받아 움직임 여부를 판단한다.

    10/24 Pi 시험에서 조명을 껐다 켤 때 63% 변화 프레임(조명으로 무시됨) 1~3초 앞이나 바로 뒤에
    20~30% 변화 프레임이 1~2개 생겨 짧은 가짜 움직임이 3번 났다 (자동 노출이 따라가는 중간 단계).
    손 흔들기는 1초에 8~10프레임이 연속으로 바뀌었다. 그래서:
      - min_frames 프레임 연속으로 바뀌어야 움직임으로 인정 (짧은 변화는 무시)
      - 조명 변화 프레임 뒤 light_settle_s 초 동안은 판단을 쉼 (자동 노출 안정 시간)
    같은 녹화(cam.csv)를 --replay로 돌린 결과: 2프레임이면 가짜 1번이 남고(85.6~85.8초, 2프레임 연속),
    3프레임이면 가짜 0번 + 진짜 손 흔들기 2번 모두 검출(0.3초 늦음) -> 기본값 3.
    """

    def __init__(self, ratio_thresh: float, light_thresh: float, hold_s: float,
                 min_frames: int = 3, light_settle_s: float = 1.0) -> None:
        self.ratio_thresh = ratio_thresh
        self.light_thresh = light_thresh
        self.hold_s = hold_s
        self.min_frames = min_frames
        self.light_settle_s = light_settle_s
        self.last_motion_t: float | None = None
        self.settle_until = float("-inf")
        self.streak = 0  # 연속으로 바뀐 프레임 수

    def update(self, ratio: float, t: float) -> tuple[bool, str]:
        """(움직임 상태, 이번 프레임 판정: 'motion' / 'candidate' / 'light' / 'settle' / 'still')"""
        if ratio > self.light_thresh:
            kind = "light"  # 화면 전체 변화는 사람 움직임으로 치지 않는다
            self.settle_until = t + self.light_settle_s
            self.streak = 0
        elif t < self.settle_until:
            kind = "settle"  # 조명 변화 직후 자동 노출이 따라가는 중
            self.streak = 0
        elif ratio > self.ratio_thresh:
            self.streak += 1
            if self.streak >= self.min_frames:
                kind = "motion"
                self.last_motion_t = t
            else:
                kind = "candidate"  # 아직 한 프레임뿐
        else:
            kind = "still"
            self.streak = 0
        active = self.last_motion_t is not None and t - self.last_motion_t <= self.hold_s
        return active, kind


def replay(path: Path, state: MotionState) -> int:
    """--csv로 녹화한 프레임별 변화 비율을 다시 넣어 판단만 새로 돌린다 (카메라 없이 튜닝용)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        print("빈 CSV입니다.")
        return 1
    t0 = float(rows[0]["wall_time"])
    was_active = False
    events = 0
    motion_s = 0.0
    prev_t = None
    for r in rows:
        t = float(r["wall_time"]) - t0
        active, _kind = state.update(float(r["ratio"]), t)
        if active and prev_t is not None:
            motion_s += t - prev_t
        if active and not was_active:
            events += 1
            print(f"[{t:6.1f}s] >>> 움직임 시작 (변화 {float(r['ratio']) * 100:.1f}%)")
        elif was_active and not active:
            print(f"[{t:6.1f}s] <<< 움직임 끝")
        was_active, prev_t = active, t
    print(f"움직임 시작 {events}번, 움직임 상태 총 {motion_s:.1f}초 / {prev_t:.1f}초")
    return 0


def run(args: argparse.Namespace) -> int:
    if args.replay:
        return replay(args.replay, MotionState(args.ratio_thresh, args.light_thresh, args.hold,
                                               args.min_frames, args.light_settle))
    try:
        from picamera2 import Picamera2  # type: ignore
    except ImportError:
        print("picamera2가 없습니다: sudo apt install -y python3-picamera2")
        return 1

    try:
        picam2 = Picamera2()
    except (IndexError, RuntimeError) as exc:
        print(f"카메라를 찾을 수 없습니다: {exc}")
        print("케이블 연결, rpicam-hello --list-cameras, 다른 카메라 프로그램이 켜져 있는지 확인하세요.")
        return 1

    w, h = LORES_SIZE
    config = picam2.create_video_configuration(
        main={"size": (1280, 720)},  # 스냅샷용
        lores={"size": LORES_SIZE, "format": "YUV420"},
        controls={"FrameRate": args.fps},
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(2.0)  # 자동 노출이 자리 잡을 때까지 (켜자마자 밝기가 크게 바뀜)

    if args.snap_dir:
        args.snap_dir.mkdir(parents=True, exist_ok=True)
    csv_file = open(args.csv, "w", newline="", encoding="utf-8") if args.csv else None
    writer = csv.writer(csv_file) if csv_file else None
    if writer:
        writer.writerow(["wall_time", "ratio", "kind", "motion_active"])

    state = MotionState(args.ratio_thresh, args.light_thresh, args.hold,
                        args.min_frames, args.light_settle)
    prev = None
    was_active = False
    t_start = time.monotonic()
    t_report = t_start
    frames = 0
    max_ratio = 0.0
    motion_frames = 0
    try:
        while args.duration <= 0 or time.monotonic() - t_start < args.duration:
            yuv = picam2.capture_array("lores")
            cur = yuv[:h, :w]  # YUV420의 앞부분 = 밝기(Y)
            now = time.monotonic()
            if prev is None:
                prev = cur.copy()
                continue
            ratio = motion_ratio(prev, cur, args.pixel_thresh, args.roi)
            prev = cur.copy()
            active, kind = state.update(ratio, now)
            frames += 1
            max_ratio = max(max_ratio, ratio)
            motion_frames += kind == "motion"
            if writer:
                writer.writerow([f"{time.time():.3f}", f"{ratio:.4f}", kind, int(active)])
            if active and not was_active:
                print(f"[{now - t_start:6.1f}s] >>> 움직임 시작 (변화 {ratio * 100:.1f}%)")
                if args.snap_dir:
                    path = args.snap_dir / f"motion_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    picam2.capture_file(str(path))
                    print(f"          사진 저장: {path}")
            elif was_active and not active:
                print(f"[{now - t_start:6.1f}s] <<< 움직임 끝")
            was_active = active

            if now - t_report >= 1.0:
                fps = frames / (now - t_report)
                status = "움직임" if active else "정지"
                print(f"[{now - t_start:6.1f}s] {fps:4.1f} 프레임/초 | {status} | "
                      f"최대 변화 {max_ratio * 100:5.1f}% | 움직임 프레임 {motion_frames}")
                frames, max_ratio, motion_frames = 0, 0.0, 0
                t_report = now
    except KeyboardInterrupt:
        print("\n중단 (Ctrl+C)")
    finally:
        picam2.stop()
        if csv_file:
            csv_file.close()
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pi 5 카메라 프레임 차분 움직임 검출")
    p.add_argument("--fps", type=float, default=10.0, help="카메라 프레임/초 (기본 10)")
    p.add_argument("--pixel-thresh", type=int, default=25, help="밝기 차이 기준 0~255 (기본 25)")
    p.add_argument("--ratio-thresh", type=float, default=0.01,
                   help="움직임으로 볼 변화 픽셀 비율 (기본 0.01 = 1%%)")
    p.add_argument("--light-thresh", type=float, default=0.6,
                   help="이보다 크면 조명 변화로 보고 무시 (기본 0.6 = 60%%)")
    p.add_argument("--hold", type=float, default=2.0, help="마지막 움직임 뒤 유지 시간(초)")
    p.add_argument("--min-frames", type=int, default=3,
                   help="움직임으로 인정할 연속 프레임 수 (기본 3, 1이면 예전 동작)")
    p.add_argument("--light-settle", type=float, default=1.0,
                   help="조명 변화 뒤 판단을 쉬는 시간(초) (기본 1.0, 0이면 예전 동작)")
    p.add_argument("--replay", type=Path,
                   help="--csv로 녹화한 파일을 다시 재생해 판단만 돌림 (카메라 불필요)")
    p.add_argument("--roi", type=float, nargs=4, metavar=("X0", "Y0", "X1", "Y1"),
                   help="볼 영역 (0~1 비율, 왼쪽 위 X0 Y0 ~ 오른쪽 아래 X1 Y1)")
    p.add_argument("--duration", type=float, default=0, help="실행 시간(초), 0이면 Ctrl+C까지")
    p.add_argument("--csv", type=Path, help="프레임별 기록 CSV 경로")
    p.add_argument("--snap-dir", type=Path, help="움직임이 시작될 때 사진을 저장할 폴더")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(run(_parse_args()))
