# -*- coding: utf-8 -*-
"""TI 'People Tracking & Counting' 데모 형식: 위 = 점 구름 + 추적 경로, 아래 = Gating and Association.

레이더를 위쪽 가운데에 두고 시야각 부채꼴 안에 위에서 본 모습을 그린다 (TI 데모처럼 앞쪽 거리가 아래로 커짐).
연결(association)은 점마다 가장 가까운 추적과의 거리가 GATE 안이면 그 추적 색으로 칠한다
(TI 트래커 내부의 실제 gating 결과가 아니라 출력 좌표로 다시 계산한 시각화).

  python build_radar_tracking.py [--video]
출력: img/final/fig_tracking_assoc.png, SafeGuard_radar_tracking_test3.mp4 (--video)
"""
import csv
import math
import os
import sys
from collections import defaultdict, deque

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter
from matplotlib.patches import Wedge, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
import mmwave_reader as m  # noqa: E402

D = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
T0 = 1793096881.728
H, TILT = 1.2, math.radians(15)
RMAX, FOV = 3.0, 60          # 그림 범위 (m), 좌우 시야각 (도, 한쪽)
GATE = 0.45                  # 연결 거리 (m)
TRAIL = 6.0                  # 경로 꼬리 (초)
BOX = (-0.8, 0.8, 0.3, 2.4)
PHASES = [(0, 178.7, "빈자리"), (178.7, 301.3, "앉아서 가만히"), (301.3, 388.4, "일어나 나간 뒤"), (388.4, 1e9, "다시 앉음")]
TCOL = ["#E040FB", "#E64A19", "#00ACC1", "#43A047", "#FBC02D", "#5E35B1"]
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 9,
                     "animation.ffmpeg_path": imageio_ffmpeg.get_ffmpeg_exe()})


def world(x, y, z):
    return x, y * math.cos(TILT) - z * math.sin(TILT)


frames = m.FrameReader().feed(open(os.path.join(D, "test3_raw.bin"), "rb").read())
rows = list(csv.DictReader(open(os.path.join(D, "test3_radar.csv"), encoding="utf-8")))
assert len(frames) == len(rows)
T = np.array([float(r["wall_time"]) for r in rows]) - T0
PTS = [np.array([world(x, y, z) for x, y, z, _v in f["points"]]).reshape(-1, 2) for f in frames]
TRK = [f["tracks"] or [] for f in frames]


def col(tid):
    return TCOL[tid % len(TCOL)]


def frame_axes(ax, title):
    ax.set_facecolor("white")
    ax.add_patch(Wedge((0, 0), RMAX, -90 - FOV, -90 + FOV, fill=False, ec="#555", lw=1.4))
    for r in (1, 2):
        ax.add_patch(Wedge((0, 0), r, -90 - FOV, -90 + FOV, fill=False, ec="#CCC", lw=0.7, ls="--"))
    ax.add_patch(Rectangle((BOX[0], -BOX[3]), BOX[1] - BOX[0], BOX[3] - BOX[2], fill=False, ec="#9E9D24", lw=1, ls=":"))
    ax.scatter([0], [0], marker="v", s=120, c="#D32F2F", zorder=5)
    ax.set_xlim(RMAX * 0.95, -RMAX * 0.95)      # TI 데모처럼 좌우를 뒤집어 레이더에서 본 방향
    ax.set_ylim(-RMAX - 0.1, 0.3)
    ax.set_aspect("equal")
    ax.set_xticks([-2, -1, 0, 1, 2]); ax.set_yticks([0, -1, -2, -3]); ax.set_yticklabels(["0", "1", "2", "3"])
    ax.grid(color="#EEE", lw=0.6)
    ax.tick_params(labelsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold")


def draw(ax1, ax2, i, trails):
    w = [j for j in range(max(0, i - 9), i + 1)]                 # 약 0.5초 누적 점
    P = np.vstack([PTS[j] for j in w]) if w else np.empty((0, 2))
    tracks = TRK[i]
    arts = []
    arts.append(ax1.scatter(P[:, 0], -P[:, 1], s=6, c="#9E9E9E", lw=0))
    for tid, pts in trails.items():
        if len(pts) > 1:
            a = np.array(pts)
            arts += ax1.plot(a[:, 0], -a[:, 1], color=col(tid), lw=2.2)
    for tid, x, y, _z in tracks:
        arts.append(ax1.scatter([x], [-y], s=40, c=col(tid), zorder=6))
    # 연결: 점마다 가장 가까운 추적
    if len(P) and tracks:
        C = np.array([(x, y) for _t, x, y, _z in tracks])
        dist = np.linalg.norm(P[:, None, :] - C[None, :, :], axis=2)
        k = dist.argmin(1); ok = dist.min(1) <= GATE
        arts.append(ax2.scatter(P[~ok, 0], -P[~ok, 1], s=6, c="#BDBDBD", lw=0))
        for n, (tid, _x, _y, _z) in enumerate(tracks):
            s = ok & (k == n)
            arts.append(ax2.scatter(P[s, 0], -P[s, 1], s=10, c=col(tid), lw=0))
    elif len(P):
        arts.append(ax2.scatter(P[:, 0], -P[:, 1], s=6, c="#BDBDBD", lw=0))
    for tid, x, y, _z in tracks:
        arts.append(ax2.add_patch(plt.Circle((x, -y), GATE, fill=False, ec=col(tid), lw=2)))
        arts.append(ax2.text(x, -y, str(tid), ha="center", va="center", fontsize=10, fontweight="bold", color=col(tid)))
    return arts


def update_trails(trails, i):
    live = set()
    for tid, x, y, _z in TRK[i]:
        live.add(tid)
        trails[tid].append((x, y, T[i]))
    for tid in list(trails):
        while trails[tid] and trails[tid][0][2] < T[i] - TRAIL:
            trails[tid].popleft()
        if tid not in live or not trails[tid]:
            del trails[tid]
    return {tid: [(a, b) for a, b, _t in d] for tid, d in trails.items()}


def make_fig():
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="white")
    ax1 = fig.add_axes([0.42, 0.52, 0.56, 0.42])
    ax2 = fig.add_axes([0.42, 0.04, 0.56, 0.42])
    frame_axes(ax1, "Point Cloud + 추적 경로")
    frame_axes(ax2, "Gating and Association (점이 붙은 추적)")
    fig.text(0.03, 0.92, "SafeGuard 레이더 사람 추적", fontsize=18, fontweight="bold")
    fig.text(0.03, 0.875, "IWR6843ISK-ODS, TI 3D People Tracking, 2026.10.27 시험 3", fontsize=10.5, color="#555")
    info = fig.text(0.03, 0.83, "", fontsize=14, fontweight="bold", va="top")
    ph = fig.add_axes([0.03, 0.27, 0.36, 0.42])
    ph.imshow(plt.imread(os.path.join(HERE, "img", "final", "radar_test_setup.jpg"))); ph.axis("off")
    ph.set_title("시험 배치 사진 (2026.10.27)", fontsize=10, fontweight="bold")
    fig.text(0.03, 0.235, "레이더(빨간 삼각형)에서 내려다본 방향, 좌우 반전\n"
             "회색 점 = 0.5초 점 구름, 색 선 = 최근 6초 추적 경로\n"
             "아래: 추적 0.45 m 안의 점을 그 추적 색으로 표시\n"
             "점선 사각형 = 차량용 cfg 감지 영역\n\n"
             "원본 바이트 재생 (연결은 출력 좌표로 다시 계산)", fontsize=10, color="#444", va="top")
    return fig, ax1, ax2, info


def phase(t):
    return next(lab for a, b, lab in PHASES if a <= t < b)


def figure():
    fig, ax1, ax2, info = make_fig()
    trails = defaultdict(deque)
    i_end = int(np.argmin(np.abs(T - 250)))
    for i in range(max(0, i_end - 120), i_end + 1):
        tr = update_trails(trails, i)
    draw(ax1, ax2, i_end, tr)
    info.set_text(f"t = {T[i_end]:.1f} s\n{phase(T[i_end])}\n추적 {len(TRK[i_end])}개")
    out = os.path.join(HERE, "img", "final", "fig_tracking_assoc.png")
    fig.savefig(out, dpi=150)
    print("saved", out)


def video(out, start=150.0, end=425.0, step=4):
    fig, ax1, ax2, info = make_fig()
    trails = defaultdict(deque)
    idx = [i for i in range(len(T)) if start <= T[i] <= end]
    arts = []
    writer = FFMpegWriter(fps=20, bitrate=3000)
    with writer.saving(fig, out, dpi=100):
        for n, i in enumerate(idx):
            tr = update_trails(trails, i)
            if n % step:
                continue
            for a in arts:
                a.remove()
            arts = draw(ax1, ax2, i, tr)
            ph = phase(T[i])
            info.set_text(f"t = {T[i]:5.1f} s\n{ph}\n추적 {len(TRK[i])}개")
            info.set_color("#C62828" if ph == "일어나 나간 뒤" else "#1B5E20")
            writer.grab_frame()
    print("saved", out)


if __name__ == "__main__":
    figure()
    if "--video" in sys.argv:
        video(os.path.join(HERE, "SafeGuard_radar_tracking_test3.mp4"))
