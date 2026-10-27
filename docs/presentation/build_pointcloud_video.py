# -*- coding: utf-8 -*-
"""시험 3 레이더 원본 바이트로 점 구름이 움직이는 영상(MP4)을 만든다 (Visualizer 화면 재현).

build_pointcloud.py와 같은 파서, 같은 좌표 변환. 실제 시간 150~425초를 약 4.4배속으로 재생.
출력: SafeGuard_mmwave_pointcloud_test3.mp4 (1280×720, 20 fps)

  python build_pointcloud_video.py [출력.mp4]
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
from matplotlib.animation import FFMpegWriter
from matplotlib.patches import Rectangle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
import mmwave_reader as m  # noqa: E402

D = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "SafeGuard_mmwave_pointcloud_test3.mp4")
T0 = 1793096881.728          # 빈자리 시작 안내 (Pi 시각)
H, TILT = 1.2, math.radians(15)
BOX = (-0.8, 0.8, 0.3, 2.4)
STATIC = (-0.65, 0.65, 0.5, 2.3)
START, END = 150.0, 425.0     # 재생 구간 (초)
STEP = 4                      # 출력 1프레임 = 원본 4프레임 (약 0.22초) → 20 fps면 약 4.4배속
PERSIST = 0.5                 # 점 잔상 (초)
TRAIL = 3.0                   # 추적 꼬리 (초)
PHASES = [(0, 178.7, "빈자리", "#9AA5B1"), (178.7, 301.3, "앉아서 가만히", "#7CB342"),
          (301.3, 388.4, "일어나 나간 뒤 (빈자리)", "#FF7043"), (388.4, 1e9, "다시 앉음", "#7CB342")]
TRACK_COLORS = ["#FFD54F", "#FF7043", "#4FC3F7", "#AED581", "#CE93D8"]
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False,
                     "animation.ffmpeg_path": imageio_ffmpeg.get_ffmpeg_exe()})


def world(x, y, z):
    return x, y * math.cos(TILT) - z * math.sin(TILT), -y * math.sin(TILT) + z * math.cos(TILT) + H


def phase_at(t):
    return next(p for p in PHASES if p[0] <= t < p[1])


frames = m.FrameReader().feed(open(os.path.join(D, "test3_raw.bin"), "rb").read())
rows = list(csv.DictReader(open(os.path.join(D, "test3_radar.csv"), encoding="utf-8")))
assert len(frames) == len(rows)
T = [float(r["wall_time"]) - T0 for r in rows]
PTS = []
for f in frames:
    pts = []
    for x, y, z, v in f["points"]:
        xw, yw, _ = world(x, y, z)
        pts.append((xw, yw, abs(v) >= 0.01))
    PTS.append(pts)
NTR = [len(f["tracks"]) if f["tracks"] is not None else 0 for f in frames]

fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#111418")
ax = fig.add_axes([0.035, 0.08, 0.5, 0.84], facecolor="#111418")
ax.set_xlim(-1.6, 1.6); ax.set_ylim(-0.3, 3.2); ax.set_aspect("equal")
ax.tick_params(colors="#9AA5B1", labelsize=9)
for sp in ax.spines.values():
    sp.set_color("#3A4048")
ax.grid(color="#2A3038", lw=0.6)
ax.set_xlabel("x (m, 좌우)", color="#9AA5B1"); ax.set_ylabel("y (m, 레이더 앞쪽)", color="#9AA5B1")
ax.add_patch(Rectangle((BOX[0], BOX[2]), BOX[1] - BOX[0], BOX[3] - BOX[2], fill=False, ec="#B5C92B", lw=1.3, ls="--"))
ax.add_patch(Rectangle((STATIC[0], STATIC[2]), STATIC[1] - STATIC[0], STATIC[3] - STATIC[2], fill=False, ec="#5E9335", lw=1, ls=":"))
ax.scatter([0], [0], marker="^", s=200, c="#E53935", zorder=5)
ax.text(0.1, -0.15, "레이더", color="#E53935", fontsize=10)
sc_static = ax.scatter([], [], s=10, c="#9AA5B1", alpha=0.75, lw=0)
sc_move = ax.scatter([], [], s=14, c="#26C6DA", alpha=0.95, lw=0)
track_art = []

fig.text(0.57, 0.88, "SafeGuard  |  60 GHz 레이더 점 구름", color="white", fontsize=17, fontweight="bold")
fig.text(0.57, 0.835, "IWR6843ISK-ODS, 2026.10.27 시험 3 원본 바이트 재생, 약 4배속", color="#9AA5B1", fontsize=11)
t_txt = fig.text(0.57, 0.73, "", color="white", fontsize=30, fontweight="bold")
ph_txt = fig.text(0.57, 0.66, "", color="white", fontsize=20, fontweight="bold")
cnt_txt = fig.text(0.57, 0.60, "", color="#FFD54F", fontsize=15, fontweight="bold")
fig.text(0.57, 0.53, "회색 = 정지 점   청록 = 움직이는 점   원 = 추적 대상\n연두 점선 = 차량용 cfg 감지 영역", color="#9AA5B1", fontsize=10.5)

tl = fig.add_axes([0.58, 0.12, 0.39, 0.3], facecolor="#111418")
for a, b, _lab, col in PHASES:
    tl.axvspan(max(a, START), min(b, END), color=col, alpha=0.12)
tl.step(T, NTR, where="post", color="#E0E0E0", lw=1)
tl.set_xlim(START, END); tl.set_ylim(-0.2, 3.6); tl.set_yticks([0, 1, 2, 3])
tl.tick_params(colors="#9AA5B1", labelsize=9)
for sp in tl.spines.values():
    sp.set_color("#3A4048")
tl.set_xlabel("시간 (초)", color="#9AA5B1"); tl.set_ylabel("추적 수", color="#9AA5B1")
cursor = tl.axvline(START, color="#FFD54F", lw=2)

idx = [i for i, t in enumerate(T) if START <= t <= END][::STEP]
trails = defaultdict(lambda: deque())
writer = FFMpegWriter(fps=20, bitrate=4000)
with writer.saving(fig, OUT, dpi=100):
    for n, i in enumerate(idx):
        t = T[i]
        lo = i
        while lo > 0 and T[lo - 1] >= t - PERSIST:
            lo -= 1
        st, mv = [], []
        for j in range(lo, i + 1):
            for x, y, moving in PTS[j]:
                (mv if moving else st).append((x, y))
        sc_static.set_offsets(st or [(9, 9)])
        sc_move.set_offsets(mv or [(9, 9)])
        for a in track_art:
            a.remove()
        track_art = []
        tracks = frames[i]["tracks"] or []
        live = set()
        for k, (tid, x, y, z) in enumerate(tracks):
            live.add(tid)
            trails[tid].append((t, x, y))
            while trails[tid] and trails[tid][0][0] < t - TRAIL:
                trails[tid].popleft()
            col = TRACK_COLORS[tid % len(TRACK_COLORS)]
            tx = [p[1] for p in trails[tid]]; ty = [p[2] for p in trails[tid]]
            track_art += ax.plot(tx, ty, color=col, lw=1.5, alpha=0.6)
            track_art.append(ax.scatter([x], [y], s=650, facecolors="none", edgecolors=col, linewidths=2.8, zorder=6))
            track_art.append(ax.text(x + 0.18, y + 0.14, f"ID {tid}", color=col, fontsize=12, fontweight="bold", zorder=7))
        for tid in list(trails):
            if tid not in live:
                del trails[tid]
        _a, _b, lab, col = phase_at(t)
        t_txt.set_text(f"t = {t:5.1f} s")
        ph_txt.set_text(lab); ph_txt.set_color(col)
        cnt_txt.set_text(f"추적 {len(tracks)}개   점 {len(st) + len(mv)}개 (0.5초)")
        cursor.set_xdata([t, t])
        writer.grab_frame(facecolor=fig.get_facecolor())
        if n % 200 == 0:
            print(f"{n}/{len(idx)}", flush=True)
print("saved", OUT, len(idx), "frames")
