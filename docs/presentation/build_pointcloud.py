# -*- coding: utf-8 -*-
"""시험 3 레이더 원본 바이트(test3_raw.bin)로 점 구름과 추적 위치를 다시 그린다 (Visualizer 화면 재현).

hardware/mmwave/mmwave_reader.py의 파서를 그대로 쓰고, 좌표 변환은 cfg sensorPosition(1.2 m, 15도)을 따른다
(트래커가 같은 값으로 추적 좌표를 내므로 점도 같은 기준으로 맞춤).

출력: img/final/fig_pointcloud.png
"""
import csv
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
import mmwave_reader as m  # noqa: E402

D = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "final")
T0 = 1793096881.728  # 빈자리 시작 안내 (Pi 시각)
H, TILT = 1.2, math.radians(15)
BOX = (-0.8, 0.8, 0.3, 2.4)        # boundaryBox x, y (ODS_sedan_est.cfg)
STATIC = (-0.65, 0.65, 0.5, 2.3)   # staticBoundaryBox x, y
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})


def world(x, y, z):
    return x, y * math.cos(TILT) - z * math.sin(TILT), -y * math.sin(TILT) + z * math.cos(TILT) + H


frames = m.FrameReader().feed(open(os.path.join(D, "test3_raw.bin"), "rb").read())
rows = list(csv.DictReader(open(os.path.join(D, "test3_radar.csv"), encoding="utf-8")))
assert len(frames) == len(rows)
T = [float(r["wall_time"]) - T0 for r in rows]

SNAPS = [(100, "① 빈자리", "점 거의 없음, 추적 0"),
         (250, "② 앉아서 가만히", "사람 1명을 추적 1개로 유지"),
         (345, "③ 일어나 나간 뒤", "사람이 없는데 추적 2개가 남음"),
         (405, "④ 다시 앉음", "남아 있던 추적이 사람 위치로 모임")]
TRACK_COLORS = ["#FFD54F", "#FF7043", "#4FC3F7", "#AED581", "#CE93D8"]

fig, axes = plt.subplots(1, 4, figsize=(15, 4.9), facecolor="#111418")
for ax, (tc, title, note) in zip(axes, SNAPS):
    ax.set_facecolor("#111418")
    sel = [i for i, t in enumerate(T) if tc - 0.5 <= t < tc + 0.5]  # 1초(약 18프레임) 누적
    xs, ys, moving = [], [], []
    for i in sel:
        for x, y, z, v in frames[i]["points"]:
            xw, yw, _ = world(x, y, z)
            xs.append(xw); ys.append(yw); moving.append(abs(v) >= 0.01)
    ax.scatter([a for a, mv in zip(xs, moving) if not mv], [b for b, mv in zip(ys, moving) if not mv], s=9, c="#9AA5B1", alpha=0.7, lw=0)
    ax.scatter([a for a, mv in zip(xs, moving) if mv], [b for b, mv in zip(ys, moving) if mv], s=12, c="#26C6DA", alpha=0.9, lw=0)
    last = next((frames[i]["tracks"] for i in reversed(sel) if frames[i]["tracks"] is not None), []) or []
    for k, (tid, x, y, z) in enumerate(last):
        col = TRACK_COLORS[k % len(TRACK_COLORS)]
        ax.scatter([x], [y], s=520, facecolors="none", edgecolors=col, linewidths=2.5)
        ax.text(x + 0.17, y + 0.12, f"ID {tid}", color=col, fontsize=10, fontweight="bold")
    ax.add_patch(Rectangle((BOX[0], BOX[2]), BOX[1] - BOX[0], BOX[3] - BOX[2], fill=False, ec="#B5C92B", lw=1.2, ls="--"))
    ax.add_patch(Rectangle((STATIC[0], STATIC[2]), STATIC[1] - STATIC[0], STATIC[3] - STATIC[2], fill=False, ec="#5E9335", lw=1, ls=":"))
    ax.scatter([0], [0], marker="^", s=160, c="#E53935")
    ax.text(0.08, -0.12, "레이더", color="#E53935", fontsize=9)
    ax.set_xlim(-1.6, 1.6); ax.set_ylim(-0.3, 3.2); ax.set_aspect("equal")
    ax.tick_params(colors="#9AA5B1", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#3A4048")
    ax.grid(color="#2A3038", lw=0.6)
    ax.set_title(f"{title}  (t = {tc} s)", color="white", fontsize=12.5, fontweight="bold", loc="left")
    ax.text(-1.5, 3.0, note, color="#FFD54F" if "남음" not in note else "#FF7043", fontsize=10.5, fontweight="bold")
    ax.text(1.55, -0.22, f"점 {len(xs)}개 / 추적 {len(last)}개", color="#9AA5B1", fontsize=8.5, ha="right")
    ax.set_xlabel("x (m, 좌우)", color="#9AA5B1", fontsize=9)
axes[0].set_ylabel("y (m, 레이더 앞쪽)", color="#9AA5B1", fontsize=9)
fig.text(0.01, 0.015, "위에서 본 점 구름 (1초 누적). 회색 = 정지 점, 청록 = 움직이는 점, 원 = 추적 대상, 연두 점선 = 차량용 cfg 감지 영역",
         color="#9AA5B1", fontsize=9.5)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(os.path.join(OUT, "fig_pointcloud.png"), dpi=180, facecolor=fig.get_facecolor())
print("frames", len(frames), "saved fig_pointcloud.png")
